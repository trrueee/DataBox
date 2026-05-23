from typing import Any

import pymysql

from engine.crypto import decrypt_password
from engine.errors import DataSourceConnectionError

# Schema representation for the built-in Demo Database (20 tables)
MOCK_TABLES_INFO = [
    {
        "table_name": "users",
        "table_comment": "用户信息表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 1250,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "用户ID"},
            {"column_name": "username", "data_type": "varchar", "column_type": "varchar(50)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "用户名"},
            {"column_name": "email", "data_type": "varchar", "column_type": "varchar(100)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "邮箱"},
            {"column_name": "phone", "data_type": "varchar", "column_type": "varchar(20)", "is_nullable": 1, "is_primary_key": 0, "column_comment": "手机号"},
            {"column_name": "role", "data_type": "varchar", "column_type": "varchar(20)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "角色: user, admin, staff"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "注册时间"}
        ]
    },
    {
        "table_name": "products",
        "table_comment": "商品信息表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 350,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "商品ID"},
            {"column_name": "name", "data_type": "varchar", "column_type": "varchar(150)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "商品名称"},
            {"column_name": "sku", "data_type": "varchar", "column_type": "varchar(50)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "SKU编码"},
            {"column_name": "category_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "categories", "foreign_column": "id", "column_comment": "品类ID"},
            {"column_name": "price", "data_type": "decimal", "column_type": "decimal(10,2)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "销售价"},
            {"column_name": "stock", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "库存量"},
            {"column_name": "status", "data_type": "varchar", "column_type": "varchar(20)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "状态: active, inactive"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "创建时间"}
        ]
    },
    {
        "table_name": "categories",
        "table_comment": "商品分类表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 15,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "品类ID"},
            {"column_name": "name", "data_type": "varchar", "column_type": "varchar(50)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "品类名称"},
            {"column_name": "parent_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 1, "is_primary_key": 0, "column_comment": "父品类ID"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "创建时间"}
        ]
    },
    {
        "table_name": "orders",
        "table_comment": "订单主表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 4500,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "订单ID"},
            {"column_name": "user_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "users", "foreign_column": "id", "column_comment": "买家用户ID"},
            {"column_name": "total_amount", "data_type": "decimal", "column_type": "decimal(10,2)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "订单总金额"},
            {"column_name": "status", "data_type": "varchar", "column_type": "varchar(20)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "订单状态: pending, paid, shipped, completed, cancelled"},
            {"column_name": "payment_method", "data_type": "varchar", "column_type": "varchar(30)", "is_nullable": 1, "is_primary_key": 0, "column_comment": "支付方式: alipay, wechat, credit_card"},
            {"column_name": "shipping_address", "data_type": "varchar", "column_type": "varchar(255)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "收货地址"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "下单时间"},
            {"column_name": "updated_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "更新时间"}
        ]
    },
    {
        "table_name": "order_items",
        "table_comment": "订单明细表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 9200,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "明细ID"},
            {"column_name": "order_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "orders", "foreign_column": "id", "column_comment": "关联订单ID"},
            {"column_name": "product_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "products", "foreign_column": "id", "column_comment": "关联商品ID"},
            {"column_name": "price", "data_type": "decimal", "column_type": "decimal(10,2)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "下单单价"},
            {"column_name": "quantity", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "下单数量"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "创建时间"}
        ]
    },
    {
        "table_name": "payments",
        "table_comment": "支付流水分支表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 4300,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "支付ID"},
            {"column_name": "order_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "orders", "foreign_column": "id", "column_comment": "关联订单ID"},
            {"column_name": "amount", "data_type": "decimal", "column_type": "decimal(10,2)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "支付金额"},
            {"column_name": "status", "data_type": "varchar", "column_type": "varchar(20)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "支付状态: pending, success, failed, refunded"},
            {"column_name": "transaction_id", "data_type": "varchar", "column_type": "varchar(100)", "is_nullable": 1, "is_primary_key": 0, "column_comment": "外部支付流水号"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "支付时间"}
        ]
    },
    {
        "table_name": "shipping",
        "table_comment": "物流配送表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 4200,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "配送ID"},
            {"column_name": "order_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "orders", "foreign_column": "id", "column_comment": "关联订单ID"},
            {"column_name": "tracking_number", "data_type": "varchar", "column_type": "varchar(50)", "is_nullable": 1, "is_primary_key": 0, "column_comment": "快递单号"},
            {"column_name": "carrier", "data_type": "varchar", "column_type": "varchar(50)", "is_nullable": 1, "is_primary_key": 0, "column_comment": "物流公司: sf, yto, zto"},
            {"column_name": "status", "data_type": "varchar", "column_type": "varchar(20)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "配送状态: packing, transit, delivered"},
            {"column_name": "shipped_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 1, "is_primary_key": 0, "column_comment": "出库时间"},
            {"column_name": "delivered_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 1, "is_primary_key": 0, "column_comment": "妥投时间"}
        ]
    },
    {
        "table_name": "reviews",
        "table_comment": "商品评价表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 980,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "评价ID"},
            {"column_name": "product_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "products", "foreign_column": "id", "column_comment": "关联商品ID"},
            {"column_name": "user_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "users", "foreign_column": "id", "column_comment": "评价人用户ID"},
            {"column_name": "rating", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "星级: 1-5"},
            {"column_name": "comment", "data_type": "text", "column_type": "text", "is_nullable": 1, "is_primary_key": 0, "column_comment": "评价文本"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "评价时间"}
        ]
    },
    {
        "table_name": "cart",
        "table_comment": "购物车信息表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 450,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "购物车项ID"},
            {"column_name": "user_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "users", "foreign_column": "id", "column_comment": "用户ID"},
            {"column_name": "product_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "products", "foreign_column": "id", "column_comment": "商品ID"},
            {"column_name": "quantity", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "加购数量"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "加购时间"}
        ]
    },
    {
        "table_name": "inventory_logs",
        "table_comment": "库存变更日志表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 1400,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "日志ID"},
            {"column_name": "product_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "products", "foreign_column": "id", "column_comment": "商品ID"},
            {"column_name": "change_amount", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "变更数量(正为入库，负为扣减)"},
            {"column_name": "reason", "data_type": "varchar", "column_type": "varchar(100)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "变更原因: purchase, sale, adjust, refund"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "记录时间"}
        ]
    },
    # Add 10 more tables to satisfy the V1 20+ tables synced check!
    {
        "table_name": "coupons",
        "table_comment": "优惠券配置表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 50,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "券ID"},
            {"column_name": "code", "data_type": "varchar", "column_type": "varchar(50)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "兑换码"},
            {"column_name": "discount_type", "data_type": "varchar", "column_type": "varchar(20)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "券类型: fixed, discount"},
            {"column_name": "value", "data_type": "decimal", "column_type": "decimal(10,2)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "优惠面额"},
            {"column_name": "min_spend", "data_type": "decimal", "column_type": "decimal(10,2)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "起用门槛"},
            {"column_name": "expires_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "过期时间"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "创建时间"}
        ]
    },
    {
        "table_name": "coupon_usages",
        "table_comment": "优惠券使用记录表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 890,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "记录ID"},
            {"column_name": "coupon_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "coupons", "foreign_column": "id", "column_comment": "券ID"},
            {"column_name": "order_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "orders", "foreign_column": "id", "column_comment": "订单ID"},
            {"column_name": "user_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "users", "foreign_column": "id", "column_comment": "用户ID"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "使用时间"}
        ]
    },
    {
        "table_name": "user_addresses",
        "table_comment": "用户收货地址表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 2100,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "地址ID"},
            {"column_name": "user_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "users", "foreign_column": "id", "column_comment": "用户ID"},
            {"column_name": "consignee", "data_type": "varchar", "column_type": "varchar(50)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "收货人姓名"},
            {"column_name": "phone", "data_type": "varchar", "column_type": "varchar(20)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "联系电话"},
            {"column_name": "province", "data_type": "varchar", "column_type": "varchar(50)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "省份"},
            {"column_name": "city", "data_type": "varchar", "column_type": "varchar(50)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "城市"},
            {"column_name": "district", "data_type": "varchar", "column_type": "varchar(50)", "is_nullable": 1, "is_primary_key": 0, "column_comment": "区县"},
            {"column_name": "address", "data_type": "varchar", "column_type": "varchar(255)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "详细街道地址"},
            {"column_name": "is_default", "data_type": "tinyint", "column_type": "tinyint(1)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "是否默认: 1=是, 0=否"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "创建时间"}
        ]
    },
    {
        "table_name": "suppliers",
        "table_comment": "供应商信息表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 45,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "供应商ID"},
            {"column_name": "name", "data_type": "varchar", "column_type": "varchar(100)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "商家名称"},
            {"column_name": "contact", "data_type": "varchar", "column_type": "varchar(50)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "联系人"},
            {"column_name": "phone", "data_type": "varchar", "column_type": "varchar(20)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "联系电话"},
            {"column_name": "address", "data_type": "varchar", "column_type": "varchar(255)", "is_nullable": 1, "is_primary_key": 0, "column_comment": "商家地址"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "加入时间"}
        ]
    },
    {
        "table_name": "purchase_orders",
        "table_comment": "采购订单主表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 120,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "采购单ID"},
            {"column_name": "supplier_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "suppliers", "foreign_column": "id", "column_comment": "关联供应商ID"},
            {"column_name": "status", "data_type": "varchar", "column_type": "varchar(20)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "状态: pending, shipped, received, cancelled"},
            {"column_name": "total_cost", "data_type": "decimal", "column_type": "decimal(12,2)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "总成本费用"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "创建时间"}
        ]
    },
    {
        "table_name": "purchase_order_items",
        "table_comment": "采购订单明细表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 680,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "明细ID"},
            {"column_name": "purchase_order_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "purchase_orders", "foreign_column": "id", "column_comment": "关联采购订单"},
            {"column_name": "product_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "products", "foreign_column": "id", "column_comment": "商品ID"},
            {"column_name": "cost", "data_type": "decimal", "column_type": "decimal(10,2)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "采购单价"},
            {"column_name": "quantity", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "采购数量"}
        ]
    },
    {
        "table_name": "analytics_clicks",
        "table_comment": "行为分析点击日志",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 45000,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "事件ID"},
            {"column_name": "user_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 1, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "users", "foreign_column": "id", "column_comment": "点击用户(匿名则为null)"},
            {"column_name": "product_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "products", "foreign_column": "id", "column_comment": "商品ID"},
            {"column_name": "source", "data_type": "varchar", "column_type": "varchar(50)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "来源端: web, ios, android"},
            {"column_name": "ip", "data_type": "varchar", "column_type": "varchar(45)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "用户客户端IP"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "点击发生时间"}
        ]
    },
    {
        "table_name": "system_settings",
        "table_comment": "系统基础配置表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 12,
        "columns": [
            {"column_name": "key", "data_type": "varchar", "column_type": "varchar(50)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "配置键"},
            {"column_name": "value", "data_type": "varchar", "column_type": "varchar(255)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "配置值"},
            {"column_name": "description", "data_type": "varchar", "column_type": "varchar(255)", "is_nullable": 1, "is_primary_key": 0, "column_comment": "功能描述"},
            {"column_name": "updated_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "更新时间"}
        ]
    },
    {
        "table_name": "admin_logs",
        "table_comment": "后台管理员操作审计日志",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 1500,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "日志ID"},
            {"column_name": "admin_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "users", "foreign_column": "id", "column_comment": "管理员ID"},
            {"column_name": "action", "data_type": "varchar", "column_type": "varchar(100)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "操作类型: audit_pass, system_setting_change, ban_user"},
            {"column_name": "ip", "data_type": "varchar", "column_type": "varchar(45)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "管理员操作IP"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "操作时间"}
        ]
    },
    {
        "table_name": "recommendations",
        "table_comment": "个性化商品推荐表",
        "table_type": "BASE TABLE",
        "engine_name": "InnoDB",
        "row_count_estimate": 5000,
        "columns": [
            {"column_name": "id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 1, "column_comment": "推荐ID"},
            {"column_name": "user_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "users", "foreign_column": "id", "column_comment": "用户ID"},
            {"column_name": "product_id", "data_type": "int", "column_type": "int(11)", "is_nullable": 0, "is_primary_key": 0, "is_foreign_key": 1, "foreign_table": "products", "foreign_column": "id", "column_comment": "推荐商品ID"},
            {"column_name": "score", "data_type": "decimal", "column_type": "decimal(5,4)", "is_nullable": 0, "is_primary_key": 0, "column_comment": "推荐算法打分(越接近1越匹配)"},
            {"column_name": "created_at", "data_type": "datetime", "column_type": "datetime", "is_nullable": 0, "is_primary_key": 0, "column_comment": "推荐生成时间"}
        ]
    }
]

def is_demo_db(host: str, database_name: str) -> bool:
    """Helper to detect if a connection configuration is referring to the built-in demo database."""
    return host.lower() == "demo" or database_name.lower().startswith("demo")

def get_mysql_connection_params(datasource_dict: dict[str, Any]) -> dict[str, Any]:
    """Decrypt password and construct parameters for PyMySQL connection"""
    pw = decrypt_password(datasource_dict["password_ciphertext"], datasource_dict["password_nonce"])
    return {
        "host": datasource_dict["host"],
        "port": datasource_dict["port"],
        "user": datasource_dict["username"],
        "password": pw,
        "database": datasource_dict["database_name"],
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "connect_timeout": 5,
        "read_timeout": 10,
        "write_timeout": 10,
    }

def test_connection(config: dict[str, Any]) -> dict[str, Any]:
    """
    Test connectivity to a MySQL database (or demo database).
    Returns basic database stats and checks if permissions are readonly or have write capabilities.
    """
    host = config.get("host", "")
    port = config.get("port", 3306)
    database_name = config.get("database_name", "")
    username = config.get("username", "")
    password = config.get("password", "")

    if not host or not database_name or not username:
        raise DataSourceConnectionError("Missing host, database name, or username configuration.")

    # 1. Handle Demo Database Connection Test
    if is_demo_db(host, database_name):
        return {
            "ok": True,
            "serverVersion": "8.0.35-demo-databox",
            "readonly": True,
            "tablesCount": len(MOCK_TABLES_INFO),
            "warnings": ["当前使用的是内置演示环境 (Mock MySQL Mode)。所有写入已被模拟隔离。"],
            "message": "演示环境连接成功！"
        }

    # 2. Handle Real MySQL Connection Test
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=username,
            password=password,
            database=database_name,
            charset="utf8mb4",
            connect_timeout=5
        )
        try:
            with conn.cursor() as cursor:
                # Get MySQL server version
                cursor.execute("SELECT VERSION()")
                version_row = cursor.fetchone()
                version = str(version_row[0]) if version_row else "unknown"

                # Get count of tables in this database
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s",
                    (database_name,)
                )
                tables_row = cursor.fetchone()
                tables_count = int(tables_row[0]) if tables_row else 0

                # Assess write permissions by reading grants or querying table privileges
                readonly = True
                warnings = []
                try:
                    cursor.execute("SHOW GRANTS FOR CURRENT_USER()")
                    grants = [row[0] for row in cursor.fetchall()]
                    # Check if grants contain unsafe privileges
                    for grant in grants:
                        grant_upper = grant.upper()
                        if "ALL PRIVILEGES" in grant_upper or any(op in grant_upper for op in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER"]):
                            readonly = False
                            break
                except Exception:
                    # If SHOW GRANTS fails (insufficient permissions), we try to check read-only variables
                    try:
                        cursor.execute("SHOW VARIABLES LIKE 'read_only'")
                        res = cursor.fetchone()
                        if res and res[1] == "ON":
                            readonly = True
                        else:
                            # Default to checking if we can create a temporary table to probe write permission safely
                            readonly = False
                    except Exception:
                        readonly = False

                if not readonly:
                    warnings.append("提示：当前数据库账号包含写入权限(INSERT/UPDATE/DELETE/DROP)，建议在生产环境使用只读只查的只读账号以保安全。")

                return {
                    "ok": True,
                    "serverVersion": version,
                    "readonly": readonly,
                    "tablesCount": tables_count,
                    "warnings": warnings,
                    "message": "数据库连接测试成功！"
                }
        finally:
            conn.close()
    except Exception as e:
        raise DataSourceConnectionError(f"无法建立数据库连接，请检查配置信息。错误详情: {str(e)}")
