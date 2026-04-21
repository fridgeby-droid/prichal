// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand();
tg.enableClosingConfirmation();

// Получаем данные пользователя
const user = tg.initDataUnsafe?.user;
if (user) {
    document.getElementById('userInfo').innerHTML = `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'Пользователь';
}

// API URL
const API_URL = 'https://prichal59.pythonanywhere.com/api';

// Состояние
let currentCart = {};
let currentShop = null;
let currentSupplier = null;
let productsData = {};

// ========== ЗАГРУЗКА ДАННЫХ ==========
async function loadData() {
    try {
        const response = await fetch(`${API_URL}/get_data`, {
            headers: { 'X-Telegram-InitData': tg.initData }
        });
        const data = await response.json();
        
        // Заполняем выпадающие списки магазинов
        populateShopSelect('shop-select', data.shops);
        populateShopSelect('schedule-shop-select', data.shops);
        
        return data;
    } catch (error) {
        console.error('Ошибка загрузки:', error);
        tg.showPopup({
            title: 'Ошибка',
            message: 'Не удалось загрузить данные',
            buttons: [{type: 'ok'}]
        });
    }
}

function populateShopSelect(selectId, shops) {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    select.innerHTML = '<option value="">Выберите магазин</option>';
    for (const shop of Object.keys(shops).sort()) {
        const option = document.createElement('option');
        option.value = shop;
        option.textContent = shop;
        select.appendChild(option);
    }
}

// ========== ЗАГРУЗКА ДОСТУПНЫХ ПОСТАВЩИКОВ ==========
async function loadAvailableSuppliers(shop) {
    const response = await fetch(`${API_URL}/get_available_suppliers?shop=${encodeURIComponent(shop)}`, {
        headers: { 'X-Telegram-InitData': tg.initData }
    });
    return await response.json();
}

// ========== ЗАГРУЗКА ТОВАРОВ ==========
async function loadProducts(supplier) {
    const response = await fetch(`${API_URL}/get_products?supplier=${encodeURIComponent(supplier)}`, {
        headers: { 'X-Telegram-InitData': tg.initData }
    });
    productsData = await response.json();
    return productsData;
}

// ========== ОТРИСОВКА ТОВАРОВ ==========
function renderProducts(products) {
    const container = document.getElementById('products-list');
    const createBtn = document.getElementById('create-order-btn');
    
    if (!products || products.length === 0) {
        container.innerHTML = '<div class="empty-state" style="padding: 40px;"><div class="empty-text">Нет товаров</div></div>';
        createBtn.style.display = 'none';
        return;
    }
    
    container.innerHTML = '';
    currentCart = {};
    
    products.forEach(product => {
        const name = product.name;
        const unit = product.unit || 'шт';
        const div = document.createElement('div');
        div.className = 'product-item';
        div.innerHTML = `
            <div>
                <span class="product-name">${escapeHtml(name)}</span>
                <span class="product-unit">${unit}</span>
            </div>
            <div class="product-quantity">
                <input type="number" 
                       id="qty_${escapeHtml(name)}" 
                       class="quantity-input" 
                       min="0" 
                       step="${unit === 'шт' ? 1 : 0.1}" 
                       value="0"
                       placeholder="0">
                <span class="quantity-unit">${unit}</span>
            </div>
        `;
        
        const input = div.querySelector('.quantity-input');
        input.addEventListener('change', () => {
            const qty = parseFloat(input.value);
            if (qty > 0) {
                currentCart[name] = { quantity: qty, unit: unit };
            } else {
                delete currentCart[name];
            }
            updateCreateButton();
        });
        
        container.appendChild(div);
    });
    
    createBtn.style.display = 'block';
    updateCreateButton();
}

function updateCreateButton() {
    const btn = document.getElementById('create-order-btn');
    if (btn) {
        const hasItems = Object.keys(currentCart).length > 0;
        btn.style.opacity = hasItems ? '1' : '0.5';
        btn.disabled = !hasItems;
    }
}

// ========== СОЗДАНИЕ ЗАЯВКИ ==========
async function createOrder() {
    if (!currentShop || !currentSupplier || Object.keys(currentCart).length === 0) {
        tg.showPopup({
            title: 'Ошибка',
            message: 'Заполните все поля и добавьте товары',
            buttons: [{type: 'ok'}]
        });
        return;
    }
    
    tg.showPopup({
        title: 'Подтверждение',
        message: `Создать заявку для ${currentShop} от ${currentSupplier}?`,
        buttons: [
            {type: 'cancel', text: 'Отмена'},
            {type: 'default', text: 'Создать'}
        ]
    }, async (buttonId) => {
        if (buttonId === 'default') {
            try {
                const response = await fetch(`${API_URL}/create_order`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Telegram-InitData': tg.initData
                    },
                    body: JSON.stringify({ 
                        shop: currentShop, 
                        supplier: currentSupplier, 
                        items: currentCart 
                    })
                });
                
                const result = await response.json();
                if (result.success) {
                    tg.showPopup({
                        title: 'Успех',
                        message: 'Заявка успешно создана!',
                        buttons: [{type: 'ok'}]
                    });
                    
                    // Сбрасываем форму
                    currentCart = {};
                    document.getElementById('supplier-select').value = '';
                    document.getElementById('supplier-card').style.display = 'none';
                    document.getElementById('products-card').style.display = 'none';
                    document.getElementById('no-suppliers-message').style.display = 'none';
                    document.getElementById('shop-select').value = '';
                    currentShop = null;
                    currentSupplier = null;
                    
                    // Переключаемся на вкладку заявок
                    switchTab('orders');
                    loadOrders();
                }
            } catch (error) {
                tg.showPopup({
                    title: 'Ошибка',
                    message: 'Не удалось создать заявку',
                    buttons: [{type: 'ok'}]
                });
            }
        }
    });
}

// ========== ЗАГРУЗКА ЗАЯВОК ==========
async function loadOrders() {
    try {
        const response = await fetch(`${API_URL}/get_orders`, {
            headers: { 'X-Telegram-InitData': tg.initData }
        });
        const orders = await response.json();
        
        const container = document.getElementById('orders-list');
        const noOrders = document.getElementById('no-orders');
        
        if (!orders || orders.length === 0) {
            container.innerHTML = '';
            noOrders.style.display = 'block';
            return;
        }
        
        noOrders.style.display = 'none';
        container.innerHTML = '';
        
        orders.slice().reverse().forEach(order => {
            const div = document.createElement('div');
            div.className = 'order-item';
            
            let itemsHtml = '';
            for (const [product, data] of Object.entries(order.items)) {
                const qty = data.quantity;
                const unit = data.unit || 'шт';
                const displayQty = Number.isInteger(qty) ? qty : qty.toFixed(1);
                itemsHtml += `
                    <div class="order-item-product">
                        <span class="order-item-name">${escapeHtml(product)}</span>
                        <span class="order-item-qty">${displayQty} ${unit}</span>
                    </div>
                `;
            }
            
            div.innerHTML = `
                <div class="order-header">
                    <div>
                        <div class="order-shop">🏪 ${escapeHtml(order.shop)}</div>
                        <div class="order-supplier">📦 ${escapeHtml(order.supplier)}</div>
                    </div>
                    <div class="order-date">${order.date || ''}</div>
                </div>
                <div class="order-items">${itemsHtml}</div>
            `;
            container.appendChild(div);
        });
    } catch (error) {
        console.error('Ошибка загрузки заявок:', error);
    }
}

// ========== ЗАГРУЗКА ГРАФИКА ==========
async function loadSchedule() {
    const shop = document.getElementById('schedule-shop-select').value;
    const container = document.getElementById('schedule-container');
    const noSchedule = document.getElementById('no-schedule');
    
    if (!shop) {
        container.innerHTML = '';
        noSchedule.style.display = 'block';
        return;
    }
    
    noSchedule.style.display = 'none';
    container.innerHTML = '<div class="loading-spinner">Загрузка...</div>';
    
    try {
        const response = await fetch(`${API_URL}/get_schedule?shop=${encodeURIComponent(shop)}`, {
            headers: { 'X-Telegram-InitData': tg.initData }
        });
        const schedule = await response.json();
        
        container.innerHTML = '';
        
        if (!schedule || Object.keys(schedule).length === 0) {
            container.innerHTML = '<div class="empty-state" style="padding: 40px;"><div class="empty-text">Нет расписания</div></div>';
            return;
        }
        
        for (const [supplier, days] of Object.entries(schedule)) {
            const div = document.createElement('div');
            div.className = 'schedule-item';
            div.innerHTML = `
                <div class="schedule-supplier">📦 ${escapeHtml(supplier)}</div>
                <div class="schedule-days">
                    ${days.map(day => `<span class="day-badge">${escapeHtml(day)}</span>`).join('')}
                </div>
            `;
            container.appendChild(div);
        }
    } catch (error) {
        console.error('Ошибка загрузки графика:', error);
        container.innerHTML = '<div class="empty-state"><div class="empty-text">Ошибка загрузки</div></div>';
    }
}

// ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

// ========== ПЕРЕКЛЮЧЕНИЕ ВКЛАДОК ==========
function switchTab(tabId) {
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });
    document.getElementById(`${tabId}-tab`).classList.add('active');
    
    document.querySelectorAll('.tab-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`.tab-item[data-tab="${tabId}"]`).classList.add('active');
    
    if (tabId === 'orders') {
        loadOrders();
    }
}

// ========== ОБРАБОТЧИКИ СОБЫТИЙ ==========
document.getElementById('shop-select').addEventListener('change', async (e) => {
    const shop = e.target.value;
    currentShop = shop;
    
    const supplierCard = document.getElementById('supplier-card');
    const productsCard = document.getElementById('products-card');
    const noSuppliersMsg = document.getElementById('no-suppliers-message');
    const supplierSelect = document.getElementById('supplier-select');
    
    if (!shop) {
        supplierCard.style.display = 'none';
        productsCard.style.display = 'none';
        noSuppliersMsg.style.display = 'none';
        return;
    }
    
    supplierCard.style.display = 'block';
    supplierSelect.disabled = true;
    supplierSelect.innerHTML = '<option value="">Загрузка...</option>';
    
    const suppliers = await loadAvailableSuppliers(shop);
    
    supplierSelect.innerHTML = '<option value="">Выберите поставщика</option>';
    
    if (!suppliers || suppliers.length === 0) {
        noSuppliersMsg.style.display = 'block';
        supplierCard.style.display = 'none';
        productsCard.style.display = 'none';
        return;
    }
    
    noSuppliersMsg.style.display = 'none';
    suppliers.forEach(supplier => {
        const option = document.createElement('option');
        option.value = supplier;
        option.textContent = supplier;
        supplierSelect.appendChild(option);
    });
    supplierSelect.disabled = false;
});

document.getElementById('supplier-select').addEventListener('change', async (e) => {
    const supplier = e.target.value;
    currentSupplier = supplier;
    const productsCard = document.getElementById('products-card');
    
    if (!supplier) {
        productsCard.style.display = 'none';
        return;
    }
    
    productsCard.style.display = 'block';
    const products = await loadProducts(supplier);
    renderProducts(products);
});

document.getElementById('create-order-btn').addEventListener('click', createOrder);
document.getElementById('schedule-shop-select').addEventListener('change', loadSchedule);

// Переключение вкладок
document.querySelectorAll('.tab-item').forEach(tab => {
    tab.addEventListener('click', () => {
        const tabId = tab.dataset.tab;
        switchTab(tabId);
    });
});

// Инициализация
loadData();
loadOrders();