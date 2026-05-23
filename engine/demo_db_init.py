import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DEMO_DB_PATH = str(Path(__file__).resolve().parent.parent / "databox_demo.db")

def init_demo_database(force: bool = False) -> str:
    """
    Initializes a highly realistic local SQLite database file `databox_demo.db` representing
    an E-commerce store backend with 20 tables loaded with complete mock data.
    This enables full out-of-the-box local verification without a real MySQL server.
    """
    if Path(DEMO_DB_PATH).exists() and not force:
        return DEMO_DB_PATH

    conn = sqlite3.connect(DEMO_DB_PATH)
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Create Tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        phone TEXT,
        role TEXT NOT NULL DEFAULT 'user',
        created_at TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        parent_id INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY (parent_id) REFERENCES categories (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        sku TEXT NOT NULL UNIQUE,
        category_id INTEGER NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL,
        FOREIGN KEY (category_id) REFERENCES categories (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        total_amount REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        payment_method TEXT,
        shipping_address TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        price REAL NOT NULL,
        quantity INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        transaction_id TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shipping (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        tracking_number TEXT,
        carrier TEXT,
        status TEXT NOT NULL DEFAULT 'packing',
        shipped_at TEXT,
        delivered_at TEXT,
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        comment TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        change_amount INTEGER NOT NULL,
        reason TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        discount_type TEXT NOT NULL,
        value REAL NOT NULL,
        min_spend REAL NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS coupon_usages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coupon_id INTEGER NOT NULL,
        order_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (coupon_id) REFERENCES coupons (id) ON DELETE CASCADE,
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_addresses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        consignee TEXT NOT NULL,
        phone TEXT NOT NULL,
        province TEXT NOT NULL,
        city TEXT NOT NULL,
        district TEXT,
        address TEXT NOT NULL,
        is_default INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT,
        created_at TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        total_cost REAL NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (supplier_id) REFERENCES suppliers (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchase_order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        cost REAL NOT NULL,
        quantity INTEGER NOT NULL,
        FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders (id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS analytics_clicks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER NOT NULL,
        source TEXT NOT NULL,
        ip TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        description TEXT,
        updated_at TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        ip TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (admin_id) REFERENCES users (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        score REAL NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
    );
    """)

    conn.commit()

    # 2. Populating Mock Data
    now = datetime.now()

    # Users
    users_data = [
        ("admin", "admin@databox.local", "13800000000", "admin", (now - timedelta(days=90)).isoformat()),
        ("staff_jack", "jack@databox.local", "13800000001", "staff", (now - timedelta(days=80)).isoformat()),
        ("staff_lucy", "lucy@databox.local", "13800000002", "staff", (now - timedelta(days=80)).isoformat()),
        ("zhangsan", "zhangsan@outlook.com", "13911112222", "user", (now - timedelta(days=60)).isoformat()),
        ("lisi", "lisi@gmail.com", "13933334444", "user", (now - timedelta(days=55)).isoformat()),
        ("wangwu", "wangwu@qq.com", "13566667777", "user", (now - timedelta(days=50)).isoformat()),
        ("zhaoliu", "zhaoliu@163.com", "13788889999", "user", (now - timedelta(days=45)).isoformat()),
        ("qianqi", "qianqi@foxmail.com", "18600001111", "user", (now - timedelta(days=40)).isoformat()),
        ("sunba", "sunba@yahoo.com", "18622223333", "user", (now - timedelta(days=35)).isoformat()),
        ("zhoujiu", "zhoujiu@hotmail.com", "18544445555", "user", (now - timedelta(days=30)).isoformat()),
        ("wushi", "wushi@databox.com", "17788889999", "user", (now - timedelta(days=15)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO users (username, email, phone, role, created_at) VALUES (?, ?, ?, ?, ?)", users_data)
    
    # Categories
    categories_data = [
        ("数码电器", None, (now - timedelta(days=90)).isoformat()),
        ("智能手机", 1, (now - timedelta(days=90)).isoformat()),
        ("便携电脑", 1, (now - timedelta(days=90)).isoformat()),
        ("精品男装", None, (now - timedelta(days=90)).isoformat()),
        ("潮流外套", 4, (now - timedelta(days=90)).isoformat()),
        ("休闲裤装", 4, (now - timedelta(days=90)).isoformat()),
        ("食品饮料", None, (now - timedelta(days=90)).isoformat()),
        ("生鲜水果", 7, (now - timedelta(days=90)).isoformat()),
        ("休闲零食", 7, (now - timedelta(days=90)).isoformat()),
        ("图书办公", None, (now - timedelta(days=90)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO categories (name, parent_id, created_at) VALUES (?, ?, ?)", categories_data)

    # Products
    products_data = [
        ("iPhone 15 Pro", "SKU_IPHONE_15_PRO", 2, 7999.00, 120, "active", (now - timedelta(days=80)).isoformat()),
        ("Xiaomi 14 Ultra", "SKU_XIAOMI_14_U", 2, 6499.00, 85, "active", (now - timedelta(days=70)).isoformat()),
        ("MacBook Pro 14", "SKU_MBP_14", 3, 12999.00, 45, "active", (now - timedelta(days=80)).isoformat()),
        ("ThinkPad X1 Carbon", "SKU_TP_X1_C", 3, 10999.00, 30, "active", (now - timedelta(days=75)).isoformat()),
        ("时尚无帽冲锋衣", "SKU_JACKET_001", 5, 299.00, 500, "active", (now - timedelta(days=60)).isoformat()),
        ("复古工装休闲裤", "SKU_PANTS_002", 6, 179.00, 350, "active", (now - timedelta(days=60)).isoformat()),
        ("烟台红富士苹果 5kg", "SKU_FRUIT_APPLE", 8, 59.90, 800, "active", (now - timedelta(days=30)).isoformat()),
        ("泰国进口金枕头榴莲 2-3kg", "SKU_FRUIT_DURIAN", 8, 159.00, 150, "active", (now - timedelta(days=20)).isoformat()),
        ("手撕牛肉干 250g", "SKU_SNACK_BEEF", 9, 45.00, 1200, "active", (now - timedelta(days=50)).isoformat()),
        ("算法导论 (原书第3版)", "SKU_BOOK_ALGO", 10, 128.00, 200, "active", (now - timedelta(days=60)).isoformat()),
        ("设计模式的艺术", "SKU_BOOK_DESIGN", 10, 69.00, 0, "inactive", (now - timedelta(days=60)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO products (name, sku, category_id, price, stock, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", products_data)

    # Orders (Create realistic histories for user ids 4 to 11)
    orders_data = [
        (4, 8058.90, "completed", "alipay", "北京市海淀区中关村南大街1号", (now - timedelta(days=25)).isoformat(), (now - timedelta(days=25)).isoformat()),
        (5, 6499.00, "completed", "wechat", "上海市浦东新区张江高科技园区20号", (now - timedelta(days=22)).isoformat(), (now - timedelta(days=22)).isoformat()),
        (6, 478.00, "completed", "credit_card", "广东省深圳市南山区腾讯大厦", (now - timedelta(days=20)).isoformat(), (now - timedelta(days=20)).isoformat()),
        (7, 128.00, "paid", "alipay", "浙江省杭州市余杭区阿里巴巴西溪园区", (now - timedelta(days=15)).isoformat(), (now - timedelta(days=15)).isoformat()),
        (8, 299.00, "shipped", "wechat", "四川省成都市武侯区科华北路99号", (now - timedelta(days=5)).isoformat(), (now - timedelta(days=4)).isoformat()),
        (9, 218.90, "completed", "alipay", "湖北省武汉市东湖高新区光谷广场", (now - timedelta(days=3)).isoformat(), (now - timedelta(days=2)).isoformat()),
        (4, 159.00, "pending", None, "北京市海淀区中关村南大街1号", (now - timedelta(hours=5)).isoformat(), (now - timedelta(hours=5)).isoformat()),
        (10, 45.00, "cancelled", None, "陕西省西安市雁塔区小寨东路", (now - timedelta(days=10)).isoformat(), (now - timedelta(days=10)).isoformat()),
        (5, 12999.00, "completed", "credit_card", "上海市浦东新区张江高科技园区20号", (now - timedelta(days=35)).isoformat(), (now - timedelta(days=35)).isoformat()),
        (6, 59.90, "completed", "wechat", "广东省深圳市南山区腾讯大厦", (now - timedelta(days=12)).isoformat(), (now - timedelta(days=12)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO orders (user_id, total_amount, status, payment_method, shipping_address, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", orders_data)

    # Order Items (corresponds to order IDs 1-10)
    order_items_data = [
        (1, 1, 7999.00, 1, (now - timedelta(days=25)).isoformat()), # Order 1: iPhone + Apple
        (1, 7, 59.90, 1, (now - timedelta(days=25)).isoformat()),
        (2, 2, 6499.00, 1, (now - timedelta(days=22)).isoformat()), # Order 2: Xiaomi
        (3, 5, 299.00, 1, (now - timedelta(days=20)).isoformat()),  # Order 3: Jacket + Pants
        (3, 6, 179.00, 1, (now - timedelta(days=20)).isoformat()),
        (4, 10, 128.00, 1, (now - timedelta(days=15)).isoformat()), # Order 4: Book
        (5, 5, 299.00, 1, (now - timedelta(days=5)).isoformat()),   # Order 5: Jacket
        (6, 7, 59.90, 1, (now - timedelta(days=3)).isoformat()),    # Order 6: Apple + Durian
        (6, 8, 159.00, 1, (now - timedelta(days=3)).isoformat()),
        (7, 8, 159.00, 1, (now - timedelta(hours=5)).isoformat()),  # Order 7: Durian
        (8, 9, 45.00, 1, (now - timedelta(days=10)).isoformat()),   # Order 8: Beef
        (9, 3, 12999.00, 1, (now - timedelta(days=35)).isoformat()),# Order 9: MBP
        (10, 7, 59.90, 1, (now - timedelta(days=12)).isoformat()),  # Order 10: Apple
    ]
    cursor.executemany("INSERT OR IGNORE INTO order_items (order_id, product_id, price, quantity, created_at) VALUES (?, ?, ?, ?, ?)", order_items_data)

    # Payments
    payments_data = [
        (1, 8058.90, "success", "TXN_ALIPAY_89410328", (now - timedelta(days=25)).isoformat()),
        (2, 6499.00, "success", "TXN_WECHAT_77189204", (now - timedelta(days=22)).isoformat()),
        (3, 478.00, "success", "TXN_CC_6619028", (now - timedelta(days=20)).isoformat()),
        (4, 128.00, "success", "TXN_ALIPAY_2290481", (now - timedelta(days=15)).isoformat()),
        (5, 299.00, "success", "TXN_WECHAT_0019283", (now - timedelta(days=4)).isoformat()),
        (6, 218.90, "success", "TXN_ALIPAY_55681920", (now - timedelta(days=2)).isoformat()),
        (7, 159.00, "pending", None, (now - timedelta(hours=5)).isoformat()),
        (8, 45.00, "failed", None, (now - timedelta(days=10)).isoformat()),
        (9, 12999.00, "success", "TXN_CC_98910283", (now - timedelta(days=35)).isoformat()),
        (10, 59.90, "success", "TXN_WECHAT_10283948", (now - timedelta(days=12)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO payments (order_id, amount, status, transaction_id, created_at) VALUES (?, ?, ?, ?, ?)", payments_data)

    # Shipping
    shipping_data = [
        (1, "SF1489028340", "sf", "delivered", (now - timedelta(days=24)).isoformat(), (now - timedelta(days=23)).isoformat()),
        (2, "YT8819208340", "yto", "delivered", (now - timedelta(days=21)).isoformat(), (now - timedelta(days=20)).isoformat()),
        (3, "ZT2009384910", "zto", "delivered", (now - timedelta(days=19)).isoformat(), (now - timedelta(days=18)).isoformat()),
        (4, "SF1002938490", "sf", "delivered", (now - timedelta(days=14)).isoformat(), (now - timedelta(days=13)).isoformat()),
        (5, "YT2009182390", "yto", "transit", (now - timedelta(days=3)).isoformat(), None),
        (6, "ZT9083948293", "zto", "delivered", (now - timedelta(days=2)).isoformat(), (now - timedelta(days=1)).isoformat()),
        (9, "SF1892839482", "sf", "delivered", (now - timedelta(days=34)).isoformat(), (now - timedelta(days=33)).isoformat()),
        (10, "YT9828394819", "yto", "delivered", (now - timedelta(days=11)).isoformat(), (now - timedelta(days=10)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO shipping (order_id, tracking_number, carrier, status, shipped_at, delivered_at) VALUES (?, ?, ?, ?, ?, ?)", shipping_data)

    # Reviews
    reviews_data = [
        (1, 4, 5, "太棒了！屏幕非常清晰，系统非常流畅，苹果品质没得说！", (now - timedelta(days=20)).isoformat()),
        (2, 5, 5, "Xiaomi 14 Ultra 拍照太绝了，徕卡专业光学镜头就是不一样！", (now - timedelta(days=18)).isoformat()),
        (5, 6, 4, "冲锋衣面料还算舒适，防风效果也可以，就是快递稍微慢了点。", (now - timedelta(days=15)).isoformat()),
        (10, 4, 5, "算法导论的圣经！买一本收藏，虽然看起来非常烧脑，但极力推荐！", (now - timedelta(days=10)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO reviews (product_id, user_id, rating, comment, created_at) VALUES (?, ?, ?, ?, ?)", reviews_data)

    # Cart
    cart_data = [
        (4, 9, 2, (now - timedelta(days=1)).isoformat()),
        (5, 1, 1, (now - timedelta(days=2)).isoformat()),
        (6, 10, 1, (now - timedelta(hours=2)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO cart (user_id, product_id, quantity, created_at) VALUES (?, ?, ?, ?)", cart_data)

    # Inventory Logs
    inv_logs_data = [
        (1, 200, "purchase", (now - timedelta(days=80)).isoformat()),
        (1, -80, "sale", (now - timedelta(days=70)).isoformat()),
        (2, 100, "purchase", (now - timedelta(days=70)).isoformat()),
        (3, 50, "purchase", (now - timedelta(days=80)).isoformat()),
        (5, 500, "purchase", (now - timedelta(days=60)).isoformat()),
        (11, 20, "purchase", (now - timedelta(days=60)).isoformat()),
        (11, -20, "adjust", (now - timedelta(days=40)).isoformat()), # Defective/Damaged product adjustment
    ]
    cursor.executemany("INSERT OR IGNORE INTO inventory_logs (product_id, change_amount, reason, created_at) VALUES (?, ?, ?, ?)", inv_logs_data)

    # Coupons
    coupons_data = [
        ("HAPPY_NEW_YEAR", "fixed", 50.00, 300.00, (now + timedelta(days=60)).isoformat(), (now - timedelta(days=20)).isoformat()),
        ("DOUBLE_11_SALE", "discount", 0.90, 100.00, (now - timedelta(days=10)).isoformat(), (now - timedelta(days=20)).isoformat()),
        ("VIP_EXCLUSIVES", "fixed", 100.00, 500.00, (now + timedelta(days=90)).isoformat(), (now - timedelta(days=30)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO coupons (code, discount_type, value, min_spend, expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?)", coupons_data)

    # Coupon Usages (order 1 used a coupon for example)
    coupon_usages_data = [
        (1, 1, 4, (now - timedelta(days=25)).isoformat()),
        (3, 9, 5, (now - timedelta(days=35)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO coupon_usages (coupon_id, order_id, user_id, created_at) VALUES (?, ?, ?, ?)", coupon_usages_data)

    # User Addresses
    addresses_data = [
        (4, "张三", "13911112222", "北京市", "北京市", "海淀区", "中关村南大街1号", 1, (now - timedelta(days=60)).isoformat()),
        (5, "李四", "13933334444", "上海市", "上海市", "浦东新区", "张江高科技园区20号", 1, (now - timedelta(days=55)).isoformat()),
        (6, "王五", "13566667777", "广东省", "深圳市", "南山区", "腾讯大厦", 1, (now - timedelta(days=50)).isoformat()),
        (6, "王小五", "13566667778", "湖北省", "武汉市", "洪山区", "光谷步行街", 0, (now - timedelta(days=40)).isoformat()),
        (7, "赵六", "13788889999", "浙江省", "杭州市", "余杭区", "阿里巴巴西溪园区", 1, (now - timedelta(days=45)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO user_addresses (user_id, consignee, phone, province, city, district, address, is_default, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", addresses_data)

    # Suppliers
    suppliers_data = [
        ("华强北数码供应联盟", "刘经理", "18999990001", "广东省深圳市福田区华强北路", (now - timedelta(days=90)).isoformat()),
        ("北京红星图书出版社", "陈老师", "18999990002", "北京市朝阳区红星街8号", (now - timedelta(days=90)).isoformat()),
        ("南粤生鲜贸易行", "张掌柜", "18999990003", "广东省广州市荔湾区农贸市场", (now - timedelta(days=90)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO suppliers (name, contact, phone, address, created_at) VALUES (?, ?, ?, ?, ?)", suppliers_data)

    # Purchase Orders
    purchase_orders_data = [
        (1, "received", 85000.00, (now - timedelta(days=50)).isoformat()),
        (2, "received", 12000.00, (now - timedelta(days=45)).isoformat()),
        (3, "pending", 3500.00, (now - timedelta(days=2)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO purchase_orders (supplier_id, status, total_cost, created_at) VALUES (?, ?, ?, ?)", purchase_orders_data)

    # Purchase Order Items
    po_items_data = [
        (1, 1, 5500.00, 10), # 10 iPhones bought for cost
        (1, 2, 4500.00, 10), # 10 Xiaomis bought for cost
        (2, 10, 80.00, 150), # 150 Books bought
        (3, 7, 35.00, 100),  # 100 apples ordered
    ]
    cursor.executemany("INSERT OR IGNORE INTO purchase_order_items (purchase_order_id, product_id, cost, quantity) VALUES (?, ?, ?, ?)", po_items_data)

    # Analytics Clicks
    clicks_data = [
        (4, 1, "ios", "192.168.1.10", (now - timedelta(days=1, hours=3)).isoformat()),
        (5, 2, "android", "192.168.1.11", (now - timedelta(days=1, hours=2)).isoformat()),
        (None, 5, "web", "202.108.22.45", (now - timedelta(days=2)).isoformat()),
        (6, 10, "web", "110.12.184.2", (now - timedelta(days=3)).isoformat()),
        (7, 3, "ios", "220.181.108.9", (now - timedelta(days=4)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO analytics_clicks (user_id, product_id, source, ip, created_at) VALUES (?, ?, ?, ?, ?)", clicks_data)

    # System Settings
    settings_data = [
        ("site_name", "DataBox Premium Shop", "在线商城显示名称", (now - timedelta(days=90)).isoformat()),
        ("maintenance_mode", "false", "系统维护开关", (now - timedelta(days=90)).isoformat()),
        ("points_ratio", "10", "消费返积分比例(百分比)", (now - timedelta(days=90)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO system_settings (key, value, description, updated_at) VALUES (?, ?, ?, ?)", settings_data)

    # Admin Logs
    admin_logs_data = [
        (1, "system_setting_change", "192.168.1.100", (now - timedelta(days=88)).isoformat()),
        (1, "audit_pass", "192.168.1.100", (now - timedelta(days=80)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO admin_logs (admin_id, action, ip, created_at) VALUES (?, ?, ?, ?)", admin_logs_data)

    # Recommendations
    recs_data = [
        (4, 2, 0.9850, (now - timedelta(days=1)).isoformat()),
        (4, 5, 0.8820, (now - timedelta(days=1)).isoformat()),
        (5, 1, 0.9540, (now - timedelta(days=1)).isoformat()),
        (6, 3, 0.9120, (now - timedelta(days=2)).isoformat()),
    ]
    cursor.executemany("INSERT OR IGNORE INTO recommendations (user_id, product_id, score, created_at) VALUES (?, ?, ?, ?)", recs_data)

    conn.commit()
    conn.close()
    return DEMO_DB_PATH
