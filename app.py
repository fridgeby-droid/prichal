import json
import os
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
import requests
import base64
import uuid
import time

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8786900492:AAGPpGPAfvm_AbWiohxKjlayu_wkAJrWMTE')
DAILY_NOTIFICATION_SECRET = os.environ.get('DAILY_NOTIFICATION_SECRET', 'xK9mP2nL5qR7vW3zY8tU4')

# Определяем базовую директорию (для Bothost)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Пути к файлам
SUPPLIERS_FILE = os.path.join(BASE_DIR, "suppliers.json")
PRODUCTS_FILE = os.path.join(BASE_DIR, "products.json")
ORDERS_FILE = os.path.join(BASE_DIR, "orders.json")
SHOPS_FILE = os.path.join(BASE_DIR, "shops.json")
SCHEDULE_FILE = os.path.join(BASE_DIR, "schedule.json")
ADMINS_FILE = os.path.join(BASE_DIR, "admins.json")
ATTACHMENTS_DIR = os.path.join(BASE_DIR, "attachments")
PRICELISTS_DIR = os.path.join(BASE_DIR, "pricelists")
PRICELISTS_FILE = os.path.join(BASE_DIR, "pricelists.json")
MINIAPP_DIR = os.path.join(BASE_DIR, "miniapp")

# Создаем папки
for dir_path in [MINIAPP_DIR, ATTACHMENTS_DIR, PRICELISTS_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)

app = Flask(__name__)

# ========== ЧАСОВОЙ ПОЯС (ПЕРМЬ UTC+5) ==========
PERM_OFFSET = 5

def get_current_day():
    now = datetime.utcnow() + timedelta(hours=PERM_OFFSET)
    days = {0: "Понедельник", 1: "Вторник", 2: "Среда", 3: "Четверг",
            4: "Пятница", 5: "Суббота", 6: "Воскресенье"}
    return days[now.weekday()]

def get_current_time():
    now = datetime.utcnow() + timedelta(hours=PERM_OFFSET)
    return now.strftime("%H:%M")

def get_current_date():
    now = datetime.utcnow() + timedelta(hours=PERM_OFFSET)
    return now.strftime("%d.%m.%Y")

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ФАЙЛАМИ ==========
def load_data(filename, default_data):
    directory = os.path.dirname(filename)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, ensure_ascii=False, indent=4)
            return default_data
    else:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, ensure_ascii=False, indent=4)
        return default_data

def save_data(filename, data):
    directory = os.path.dirname(filename)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Загружаем данные
suppliers = load_data(SUPPLIERS_FILE, {})
products = load_data(PRODUCTS_FILE, {})
orders = load_data(ORDERS_FILE, [])
shops = load_data(SHOPS_FILE, {})
schedule = load_data(SCHEDULE_FILE, {})
admins = load_data(ADMINS_FILE, [317111945])

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def is_admin(user_id):
    return user_id in admins

def extract_user_id_from_init_data(init_data):
    if not init_data:
        return None
    try:
        params = urllib.parse.parse_qs(init_data)
        user_str = params.get('user', [''])[0]
        if user_str:
            user_data = json.loads(user_str)
            return user_data.get('id')
    except:
        pass
    return None

def extract_user_name_from_init_data(init_data):
    if not init_data:
        return "Пользователь"
    try:
        params = urllib.parse.parse_qs(init_data)
        user_str = params.get('user', [''])[0]
        if user_str:
            user_data = json.loads(user_str)
            name = user_data.get('first_name', '')
            if user_data.get('last_name'):
                name += " " + user_data.get('last_name')
            return name if name else "Пользователь"
    except:
        pass
    return "Пользователь"

# ========== API ДЛЯ MINI APP ==========
@app.route('/api/get_data', methods=['GET', 'POST'])
def api_get_data():
    init_data = request.headers.get('X-Telegram-InitData', '')
    user_id = extract_user_id_from_init_data(init_data)
    return jsonify({
        'shops': shops,
        'suppliers': suppliers,
        'is_admin': is_admin(user_id) if user_id else False
    })

@app.route('/api/get_products', methods=['GET'])
def api_get_products():
    supplier = request.args.get('supplier')
    if supplier in products:
        return jsonify(products[supplier])
    return jsonify({"categories": {}})

@app.route('/api/get_orders', methods=['GET'])
def api_get_orders():
    return jsonify(orders)

@app.route('/api/create_order', methods=['POST'])
def api_create_order():
    try:
        data = request.get_json()
        items = data.get('items', {})
        comment = data.get('comment', '').strip()
        attachments = data.get('attachments', [])

        init_data = request.headers.get('X-Telegram-InitData', '')
        user_id = extract_user_id_from_init_data(init_data)
        user_name = extract_user_name_from_init_data(init_data)

        if not items and not comment:
            return jsonify({"success": False, "error": "Укажите комментарий или добавьте товары"}), 400

        new_order = {
            "id": len(orders) + 1,
            "shop": data.get('shop'),
            "supplier": data.get('supplier'),
            "items": items,
            "comment": comment,
            "attachments": attachments,
            "status": "new",
            "date": get_current_date(),
            "day": get_current_day(),
            "time": get_current_time(),
            "user_id": user_id,
            "user_name": user_name
        }

        orders.append(new_order)
        save_data(ORDERS_FILE, orders)
        return jsonify({"success": True, "order_id": new_order["id"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/update_order_status', methods=['POST'])
def api_update_order_status():
    init_data = request.headers.get('X-Telegram-InitData', '')
    user_id = extract_user_id_from_init_data(init_data)

    if not is_admin(user_id):
        return jsonify({"success": False, "error": "Нет прав"}), 403

    data = request.get_json()
    order_id = data.get('order_id')
    new_status = data.get('status')

    for order in orders:
        if order['id'] == order_id:
            order['status'] = new_status
            save_data(ORDERS_FILE, orders)
            return jsonify({"success": True})

    return jsonify({"success": False, "error": "Заявка не найдена"}), 404

@app.route('/api/delete_order', methods=['POST'])
def api_delete_order():
    init_data = request.headers.get('X-Telegram-InitData', '')
    user_id = extract_user_id_from_init_data(init_data)

    if not is_admin(user_id):
        return jsonify({"success": False, "error": "Нет прав"}), 403

    data = request.get_json()
    order_id = data.get('order_id')

    global orders
    orders = [o for o in orders if o['id'] != order_id]
    save_data(ORDERS_FILE, orders)
    return jsonify({"success": True})

@app.route('/api/upload_attachment', methods=['POST'])
def api_upload_attachment():
    init_data = request.headers.get('X-Telegram-InitData', '')
    user_id = extract_user_id_from_init_data(init_data)

    if not is_admin(user_id):
        return jsonify({"success": False, "error": "Нет прав"}), 403

    data = request.get_json()
    file_data = data.get('file_data', '')
    file_name = data.get('file_name', 'file')

    if not file_data:
        return jsonify({"success": False, "error": "Нет данных файла"}), 400

    file_id = str(uuid.uuid4())
    ext = file_name.split('.')[-1] if '.' in file_name else 'png'
    filename = f"{file_id}.{ext}"
    filepath = os.path.join(ATTACHMENTS_DIR, filename)

    try:
        if ',' in file_data:
            file_data = file_data.split(',')[1]
        with open(filepath, 'wb') as f:
            f.write(base64.b64decode(file_data))

        return jsonify({
            "success": True,
            "attachment": {
                "id": file_id,
                "name": file_name,
                "url": f"/attachments/{filename}",
                "type": "file"
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/attachments/<filename>')
def serve_attachment(filename):
    return send_from_directory(ATTACHMENTS_DIR, filename)

@app.route('/api/get_schedule', methods=['GET'])
def api_get_schedule():
    shop = request.args.get('shop')
    if shop in schedule:
        return jsonify(schedule[shop])
    return jsonify({})

@app.route('/api/get_available_suppliers', methods=['GET'])
def api_get_available_suppliers():
    shop = request.args.get('shop')
    current_day = get_current_day()
    available = []
    for supplier in suppliers.keys():
        if shop in schedule and supplier in schedule.get(shop, {}):
            if current_day in schedule[shop][supplier]:
                available.append(supplier)
        else:
            available.append(supplier)
    return jsonify(available)

@app.route('/api/get_suppliers', methods=['GET'])
def api_get_suppliers():
    return jsonify(suppliers)

@app.route('/api/get_shops', methods=['GET'])
def api_get_shops():
    return jsonify(shops)

@app.route('/api/add_supplier', methods=['POST'])
def api_add_supplier():
    init_data = request.headers.get('X-Telegram-InitData', '')
    user_id = extract_user_id_from_init_data(init_data)
    if not is_admin(user_id):
        return jsonify({"success": False, "error": "Нет прав"}), 403

    data = request.get_json()
    name = data.get('name')
    if name and name not in suppliers:
        suppliers[name] = {}
        save_data(SUPPLIERS_FILE, suppliers)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Поставщик уже существует"})

@app.route('/api/add_shop', methods=['POST'])
def api_add_shop():
    init_data = request.headers.get('X-Telegram-InitData', '')
    user_id = extract_user_id_from_init_data(init_data)
    if not is_admin(user_id):
        return jsonify({"success": False, "error": "Нет прав"}), 403

    data = request.get_json()
    name = data.get('name')
    if name and name not in shops:
        shops[name] = {}
        save_data(SHOPS_FILE, shops)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Магазин уже существует"})

@app.route('/api/add_product', methods=['POST'])
def api_add_product():
    init_data = request.headers.get('X-Telegram-InitData', '')
    user_id = extract_user_id_from_init_data(init_data)
    if not is_admin(user_id):
        return jsonify({"success": False, "error": "Нет прав"}), 403

    data = request.get_json()
    supplier = data.get('supplier')
    category = data.get('category', 'Общие')
    name = data.get('name')
    unit = data.get('unit', 'шт')

    if supplier not in products:
        products[supplier] = {"categories": {}}
    if "categories" not in products[supplier]:
        products[supplier]["categories"] = {}
    if category not in products[supplier]["categories"]:
        products[supplier]["categories"][category] = []

    products[supplier]["categories"][category].append({"name": name, "unit": unit})
    save_data(PRODUCTS_FILE, products)
    return jsonify({"success": True})

@app.route('/api/delete_supplier', methods=['POST'])
def api_delete_supplier():
    init_data = request.headers.get('X-Telegram-InitData', '')
    user_id = extract_user_id_from_init_data(init_data)
    if not is_admin(user_id):
        return jsonify({"success": False, "error": "Нет прав"}), 403

    data = request.get_json()
    name = data.get('name')
    if name in suppliers:
        del suppliers[name]
        save_data(SUPPLIERS_FILE, suppliers)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Поставщик не найден"}), 404

@app.route('/api/delete_product', methods=['POST'])
def api_delete_product():
    init_data = request.headers.get('X-Telegram-InitData', '')
    user_id = extract_user_id_from_init_data(init_data)
    if not is_admin(user_id):
        return jsonify({"success": False, "error": "Нет прав"}), 403

    data = request.get_json()
    supplier = data.get('supplier')
    product_name = data.get('product_name')

    if supplier in products and "categories" in products[supplier]:
        for cat in products[supplier]["categories"]:
            products[supplier]["categories"][cat] = [
                p for p in products[supplier]["categories"][cat] 
                if p.get('name') != product_name
            ]
        save_data(PRODUCTS_FILE, products)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Товар не найден"}), 404

@app.route('/api/delete_shop', methods=['POST'])
def api_delete_shop():
    init_data = request.headers.get('X-Telegram-InitData', '')
    user_id = extract_user_id_from_init_data(init_data)
    if not is_admin(user_id):
        return jsonify({"success": False, "error": "Нет прав"}), 403

    data = request.get_json()
    name = data.get('name')
    if name in shops:
        del shops[name]
        save_data(SHOPS_FILE, shops)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Магазин не найден"}), 404

@app.route('/api/get_admins', methods=['GET'])
def api_get_admins():
    init_data = request.headers.get('X-Telegram-InitData', '')
    user_id = extract_user_id_from_init_data(init_data)
    if not is_admin(user_id):
        return jsonify({"success": False, "error": "Нет прав"}), 403
    return jsonify({"success": True, "admins": admins})

@app.route('/api/add_admin', methods=['POST'])
def api_add_admin():
    init_data = request.headers.get('X-Telegram-InitData', '')
    user_id = extract_user_id_from_init_data(init_data)
    if not is_admin(user_id):
        return jsonify({"success": False, "error": "Нет прав"}), 403

    data = request.get_json()
    new_admin_id = data.get('admin_id')
    if new_admin_id and new_admin_id not in admins:
        admins.append(new_admin_id)
        save_data(ADMINS_FILE, admins)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Ошибка"}), 400

@app.route('/api/remove_admin', methods=['POST'])
def api_remove_admin():
    init_data = request.headers.get('X-Telegram-InitData', '')
    user_id = extract_user_id_from_init_data(init_data)
    if not is_admin(user_id):
        return jsonify({"success": False, "error": "Нет прав"}), 403

    data = request.get_json()
    remove_admin_id = data.get('admin_id')
    if remove_admin_id in admins and remove_admin_id != user_id:
        admins.remove(remove_admin_id)
        save_data(ADMINS_FILE, admins)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Ошибка"}), 400

# ========== ВЕБХУК ==========
@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.get_json()
    if not update:
        return jsonify({"status": "ok"})

    if 'message' in update:
        message = update['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')

        if text == '/start':
            keyboard = {
                "inline_keyboard": [[{
                    "text": "🌐 Открыть приложение",
                    "web_app": {"url": f"https://{request.host}/miniapp"}
                }]]
            }
            send_message(chat_id, f"👋 Привет!\n📅 Сегодня: {get_current_day()}\n\nНажмите кнопку, чтобы открыть приложение.", keyboard)
        else:
            send_message(chat_id, "🌐 Нажмите кнопку 'Открыть приложение'", {
                "inline_keyboard": [[{
                    "text": "🌐 Открыть приложение",
                    "web_app": {"url": f"https://{request.host}/miniapp"}
                }]]
            })

    return jsonify({"status": "ok"})

# ========== MINI APP ==========
@app.route('/miniapp')
def miniapp_index():
    return send_from_directory(MINIAPP_DIR, 'index.html')

@app.route('/miniapp/<path:filename>')
def serve_miniapp(filename):
    return send_from_directory(MINIAPP_DIR, filename)

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)