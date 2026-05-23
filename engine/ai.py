from __future__ import annotations

import hashlib
import re
import time
from typing import Any

import httpx
from sqlalchemy.orm import Session

from engine.errors import AIServiceError
from engine.guardrail import guardrail_check
from engine.models import LLMLog, SchemaColumn, SchemaTable

# Built-in heuristic translations to support instant, no-key offline demos
DEMO_TRANSLATIONS = {
    # 用户相关
    "所有用户": "SELECT * FROM users",
    "查询所有用户": "SELECT * FROM users",
    "用户数量": "SELECT COUNT(*) AS total_users FROM users",
    "统计用户数": "SELECT COUNT(*) AS total_users FROM users",
    "管理员列表": "SELECT * FROM users WHERE role = 'admin'",
    # 商品相关
    "商品列表": "SELECT * FROM products WHERE status = 'active'",
    "查询商品": "SELECT * FROM products",
    "库存少于10": "SELECT name, sku, stock FROM products WHERE stock < 10 AND status = 'active'",
    "缺货商品": "SELECT name, sku, stock FROM products WHERE stock = 0",
    "最贵商品": "SELECT name, price FROM products ORDER BY price DESC LIMIT 10",
    # 订单相关
    "所有订单": "SELECT * FROM orders ORDER BY created_at DESC",
    "订单总额": "SELECT SUM(total_amount) AS total_sales FROM orders WHERE status != 'cancelled'",
    "订单数量": "SELECT COUNT(*) AS total_orders FROM orders",
    "张三的订单": "SELECT o.* FROM orders o JOIN users u ON o.user_id = u.id WHERE u.username = 'zhangsan'",
    "订单状态统计": "SELECT status, COUNT(*) AS count, SUM(total_amount) AS amount FROM orders GROUP BY status",
    "最近的订单": "SELECT o.id, u.username, o.total_amount, o.status, o.created_at FROM orders o JOIN users u ON o.user_id = u.id ORDER BY o.created_at DESC LIMIT 10",
    "已取消订单": "SELECT * FROM orders WHERE status = 'cancelled'",
    # 销售分析
    "销售最好的商品": "SELECT p.name, SUM(oi.quantity) AS total_sold FROM order_items oi JOIN products p ON oi.product_id = p.id GROUP BY p.id ORDER BY total_sold DESC LIMIT 5",
    "销量前五": "SELECT p.name, SUM(oi.quantity) AS total_sold FROM order_items oi JOIN products p ON oi.product_id = p.id GROUP BY p.id ORDER BY total_sold DESC LIMIT 5",
    "最高销售额": "SELECT p.name, SUM(oi.price * oi.quantity) AS total_revenue FROM order_items oi JOIN products p ON oi.product_id = p.id GROUP BY p.id ORDER BY total_revenue DESC LIMIT 5",
    "每日订单统计": "SELECT DATE(created_at) AS order_date, COUNT(*) AS order_count FROM orders GROUP BY DATE(created_at) ORDER BY order_date DESC LIMIT 30",
    # 支付相关
    "支付渠道统计": "SELECT payment_method, COUNT(*) AS count, SUM(amount) AS total_paid FROM payments WHERE status = 'success' GROUP BY payment_method",
    "支付状态统计": "SELECT status, COUNT(*), SUM(amount) FROM payments GROUP BY status",
    "退款记录": "SELECT * FROM payments WHERE status = 'refunded'",
    # 评价相关
    "低评分评价": "SELECT r.rating, r.comment, p.name AS product_name, u.username FROM reviews r JOIN products p ON r.product_id = p.id JOIN users u ON r.user_id = u.id WHERE r.rating <= 3",
    "商品评分": "SELECT p.name, AVG(r.rating) AS avg_rating, COUNT(*) AS review_count FROM reviews r JOIN products p ON r.product_id = p.id GROUP BY p.id ORDER BY avg_rating DESC",
    # 购物车
    "购物车加购": "SELECT u.username, p.name AS product_name, c.quantity FROM cart c JOIN users u ON c.user_id = u.id JOIN products p ON c.product_id = p.id",
    # 供应商
    "供应商列表": "SELECT name, contact, phone FROM suppliers",
    # 物流
    "物流状态统计": "SELECT o.id AS order_id, s.tracking_number, s.carrier, s.status FROM shipping s JOIN orders o ON s.order_id = o.id ORDER BY o.created_at DESC LIMIT 20",
    "已妥投订单": "SELECT o.id, u.username, s.carrier, s.tracking_number, s.delivered_at FROM shipping s JOIN orders o ON s.order_id = o.id JOIN users u ON o.user_id = u.id WHERE s.status = 'delivered'",
    # 系统
    "系统配置": "SELECT * FROM system_settings",
    # 推荐
    "商品推荐": "SELECT u.username, p.name, r.score FROM recommendations r JOIN users u ON r.user_id = u.id JOIN products p ON r.product_id = p.id ORDER BY r.score DESC LIMIT 20",
    # 库存
    "库存变更记录": "SELECT p.name, il.change_amount, il.reason, il.created_at FROM inventory_logs il JOIN products p ON il.product_id = p.id ORDER BY il.created_at DESC LIMIT 50",
    # 分类
    "商品分类": "SELECT c.name, COUNT(p.id) AS product_count FROM categories c LEFT JOIN products p ON c.id = p.category_id GROUP BY c.id ORDER BY product_count DESC",
    # 用户地址
    "用户地址": "SELECT u.username, ua.consignee, ua.province, ua.city, ua.address, ua.is_default FROM user_addresses ua JOIN users u ON ua.user_id = u.id",
}

def search_demo_sql(question: str) -> str:
    """Fallback fuzzy matcher to turn Chinese/English inputs into high-quality SQL offline"""
    cleaned = question.strip().lower()

    # Direct matching
    for key, sql in DEMO_TRANSLATIONS.items():
        if key in cleaned or cleaned in key:
            return sql

    # Key-word combination matches
    if "用户" in cleaned:
        if any(w in cleaned for w in ("数", "统计", "总量", "多少人", "几个")):
            return "SELECT COUNT(*) AS total_users FROM users"
        if "角色" in cleaned or "管理员" in cleaned:
            return "SELECT username, role FROM users WHERE role = 'admin'"
        if "地址" in cleaned or "收货" in cleaned:
            return "SELECT u.username, ua.consignee, ua.province, ua.city, ua.address, ua.is_default FROM user_addresses ua JOIN users u ON ua.user_id = u.id"
        return "SELECT * FROM users"

    if "商品" in cleaned or "产品" in cleaned:
        if any(w in cleaned for w in ("库存", "少于", "缺货", "没货")):
            return "SELECT name, sku, stock FROM products WHERE stock < 10 AND status = 'active'"
        if any(w in cleaned for w in ("贵", "最高", "价格", "最便宜", "降序")):
            return "SELECT name, price, stock FROM products ORDER BY price DESC LIMIT 5"
        if "分类" in cleaned or "类别" in cleaned or "品类" in cleaned:
            return "SELECT c.name, COUNT(p.id) AS product_count FROM categories c LEFT JOIN products p ON c.id = p.category_id GROUP BY c.id ORDER BY product_count DESC"
        if "评分" in cleaned or "评价" in cleaned or "口碑" in cleaned:
            return "SELECT p.name, AVG(r.rating) AS avg_rating, COUNT(*) AS review_count FROM reviews r JOIN products p ON r.product_id = p.id GROUP BY p.id ORDER BY avg_rating DESC"
        if "推荐" in cleaned or "个性" in cleaned:
            return "SELECT u.username, p.name, r.score FROM recommendations r JOIN users u ON r.user_id = u.id JOIN products p ON r.product_id = p.id ORDER BY r.score DESC LIMIT 20"
        return "SELECT name, price, stock, status FROM products"

    if "订单" in cleaned:
        if any(w in cleaned for w in ("支付方式", "支付渠道", "付款")):
            return "SELECT payment_method, COUNT(*) AS count, SUM(total_amount) AS total FROM orders WHERE status != 'cancelled' GROUP BY payment_method"
        if any(w in cleaned for w in ("额", "钱", "总计", "汇总", "总销售", "收入")):
            return "SELECT SUM(total_amount) AS total_revenue FROM orders WHERE status = 'completed'"
        if any(w in cleaned for w in ("数", "总量", "统计", "多少单", "每日")):
            return "SELECT status, COUNT(*) AS count FROM orders GROUP BY status"
        if any(w in cleaned for w in ("取消", "失败", "退款")):
            return "SELECT * FROM orders WHERE status = 'cancelled'"
        if any(w in cleaned for w in ("最近", "最新", "近期")):
            return "SELECT o.id, u.username, o.total_amount, o.status, o.created_at FROM orders o JOIN users u ON o.user_id = u.id ORDER BY o.created_at DESC LIMIT 10"
        return "SELECT * FROM orders ORDER BY created_at DESC"

    if "销售" in cleaned or "销量" in cleaned:
        if any(w in cleaned for w in ("最好", "前", "top", "热门", "畅销")):
            return "SELECT p.name, SUM(oi.quantity) AS total_sold FROM order_items oi JOIN products p ON oi.product_id = p.id GROUP BY p.id ORDER BY total_sold DESC LIMIT 5"
        if any(w in cleaned for w in ("额", "收入", "金额")):
            return "SELECT p.name, SUM(oi.price * oi.quantity) AS total_revenue FROM order_items oi JOIN products p ON oi.product_id = p.id GROUP BY p.id ORDER BY total_revenue DESC LIMIT 5"
        return "SELECT * FROM orders ORDER BY created_at DESC"

    if "支付" in cleaned:
        if any(w in cleaned for w in ("渠道", "方式")):
            return "SELECT payment_method, COUNT(*) AS count, SUM(amount) AS total_paid FROM payments WHERE status = 'success' GROUP BY payment_method"
        if "退款" in cleaned:
            return "SELECT * FROM payments WHERE status = 'refunded'"
        return "SELECT status, COUNT(*), SUM(amount) FROM payments GROUP BY status"

    if "评价" in cleaned or "评论" in cleaned or "星级" in cleaned:
        if any(w in cleaned for w in ("低", "差", "不好", "1", "2", "3")):
            return "SELECT r.rating, r.comment, p.name AS product_name, u.username FROM reviews r JOIN products p ON r.product_id = p.id JOIN users u ON r.user_id = u.id WHERE r.rating <= 3"
        if any(w in cleaned for w in ("平均", "统计", "汇总")):
            return "SELECT p.name, AVG(r.rating) AS avg_rating, COUNT(*) AS review_count FROM reviews r JOIN products p ON r.product_id = p.id GROUP BY p.id ORDER BY avg_rating DESC"
        return "SELECT r.rating, r.comment, p.name AS product_name, u.username FROM reviews r JOIN products p ON r.product_id = p.id JOIN users u ON r.user_id = u.id ORDER BY r.created_at DESC LIMIT 20"

    if "物流" in cleaned or "配送" in cleaned or "快递" in cleaned:
        if any(w in cleaned for w in ("妥投", "已送达", "完成")):
            return "SELECT o.id, u.username, s.carrier, s.tracking_number, s.delivered_at FROM shipping s JOIN orders o ON s.order_id = o.id JOIN users u ON o.user_id = u.id WHERE s.status = 'delivered'"
        return "SELECT o.id AS order_id, s.tracking_number, s.carrier, s.status FROM shipping s JOIN orders o ON s.order_id = o.id ORDER BY o.created_at DESC LIMIT 20"

    if "供应商" in cleaned or "供货商" in cleaned:
        if "采购" in cleaned:
            return "SELECT s.name, po.status, po.total_cost, po.created_at FROM purchase_orders po JOIN suppliers s ON po.supplier_id = s.id ORDER BY po.created_at DESC"
        return "SELECT name, contact, phone FROM suppliers"

    if "购物车" in cleaned or "加购" in cleaned:
        return "SELECT u.username, p.name AS product_name, c.quantity FROM cart c JOIN users u ON c.user_id = u.id JOIN products p ON c.product_id = p.id"

    if "优惠券" in cleaned or "折扣" in cleaned:
        if "使用" in cleaned or "记录" in cleaned:
            return "SELECT cu.id, c.code, c.discount_type, c.value, u.username, cu.created_at FROM coupon_usages cu JOIN coupons c ON cu.coupon_id = c.id JOIN users u ON cu.user_id = u.id"
        return "SELECT code, discount_type, value, min_spend, expires_at FROM coupons"

    if "分类" in cleaned or "品类" in cleaned:
        return "SELECT c.name, COUNT(p.id) AS product_count FROM categories c LEFT JOIN products p ON c.id = p.category_id GROUP BY c.id ORDER BY product_count DESC"

    if "库存" in cleaned:
        if "变更" in cleaned or "日志" in cleaned or "记录" in cleaned:
            return "SELECT p.name, il.change_amount, il.reason, il.created_at FROM inventory_logs il JOIN products p ON il.product_id = p.id ORDER BY il.created_at DESC LIMIT 50"
        return "SELECT name, sku, stock FROM products WHERE stock < 10 AND status = 'active'"

    if "系统" in cleaned or "配置" in cleaned or "设置" in cleaned:
        return "SELECT * FROM system_settings"

    if "推荐" in cleaned:
        return "SELECT u.username, p.name, r.score FROM recommendations r JOIN users u ON r.user_id = u.id JOIN products p ON r.product_id = p.id ORDER BY r.score DESC LIMIT 20"

    if "管理员" in cleaned or "审计" in cleaned or "操作日志" in cleaned:
        return "SELECT al.id, u.username, al.action, al.ip, al.created_at FROM admin_logs al JOIN users u ON al.admin_id = u.id ORDER BY al.created_at DESC LIMIT 50"

    if "点击" in cleaned or "浏览" in cleaned or "访问" in cleaned:
        return "SELECT ac.source, COUNT(*) AS click_count FROM analytics_clicks ac GROUP BY ac.source"

    # Default fallback
    return "SELECT * FROM products LIMIT 10"


def generate_schema_context(db: Session, datasource_id: str) -> str:
    """Builds a dense textual context containing table structures, comments, and relationships for LLM consumption"""
    tables = db.query(SchemaTable).filter(SchemaTable.data_source_id == datasource_id).all()
    if not tables:
        return "No schema metadata found. Please sync the data source first."

    context_lines = []
    
    # Load all tables and comments
    for t in tables:
        comment_str = f" -- {t.table_comment}" if t.table_comment else ""
        context_lines.append(f"CREATE TABLE {t.table_name} ({comment_str}")
        
        # Load columns
        for c in t.columns:
            pk_str = " PRIMARY KEY" if c.is_primary_key else ""
            comment_col = f" COMMENT '{c.column_comment}'" if c.column_comment else ""
            fk_str = ""
            if c.is_foreign_key and c.foreign_table_id:
                # Find target table name
                tgt = db.query(SchemaTable).filter(SchemaTable.id == c.foreign_table_id).first()
                if tgt:
                    fk_str = f" REFERENCES {tgt.table_name}(id)"
            
            context_lines.append(f"  {c.column_name} {c.column_type}{pk_str}{fk_str},{comment_col}")
            
        context_lines.append(");\n")
        
    return "\n".join(context_lines)


def generate_sql(
    db: Session, datasource_id: str, question: str, llm_config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Translates a natural language question into standard SQL.
    If no LLM configuration (api_key) is active, automatically falls back
    to the built-in demo offline translator for excellent, worry-free execution.
    """
    start_time = time.time()
    
    # 1. Read parameters
    llm_config = llm_config or {}
    api_key = llm_config.get("api_key", "").strip()
    api_base = llm_config.get("api_base", "https://api.openai.com/v1").strip()
    model_name = llm_config.get("model", "gpt-4o-mini").strip()
    
    schema_context = generate_schema_context(db, datasource_id)
    
    # Ensure standard prompt hash is saved
    prompt_raw = f"Context:\n{schema_context}\n\nQuestion: {question}"
    prompt_hash = hashlib.sha256(prompt_raw.encode("utf-8")).hexdigest()
    
    # 2. Check if we are running in Offline Demo Mode
    if not api_key:
        # Run local heuristic matcher
        generated_query = search_demo_sql(question)
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Guardrail check generated query
        guard_res = guardrail_check(generated_query)
        
        # Log the call
        log_entry = LLMLog(
            request_type="text_to_sql",
            prompt_hash=prompt_hash,
            model_name="databox-local-heuristic",
            latency_ms=latency_ms,
            status="success"
        )
        db.add(log_entry)
        db.commit()
        
        return {
            "sql": generated_query,
            "model": "databox-local-heuristic",
            "latencyMs": latency_ms,
            "guardrail": guard_res,
            "mode": "offline"
        }

    # 3. Connect to Online LLM via httpx
    system_prompt = (
        "You are an expert MySQL developer and data analyst.\n"
        "Your task is to generate a valid, high-performance SELECT statement to answer the user's question "
        "based on the provided schema definitions.\n\n"
        "Guidelines:\n"
        "1. Answer ONLY with the raw SQL code block. Do NOT write any introduction or explanation.\n"
        "2. Only write SELECT queries. DDL or DML statements (like INSERT, UPDATE, DROP, ALTER) are STRICTLY forbidden.\n"
        "3. Use correct table joining paths and reference fields exactly as they are defined.\n"
        "4. Always append a LIMIT clause (default to LIMIT 100) to keep results safe.\n"
        "5. Output must use standard MySQL syntax dialect."
    )
    
    user_prompt = (
        f"Available Database Tables Schema:\n"
        f"```sql\n"
        f"{schema_context}\n"
        f"```\n\n"
        f"User Question: \"{question}\"\n\n"
        f"Generate SQL:"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 800
    }
    
    try:
        response = httpx.post(
            f"{api_base}/chat/completions",
            headers=headers,
            json=payload,
            timeout=15.0
        )
        latency_ms = int((time.time() - start_time) * 1000)
        
        if response.status_code != 200:
            raise AIServiceError(f"LLM API returned an error (HTTP {response.status_code}): {response.text}")
            
        data = response.json()
        response_text = data["choices"][0]["message"]["content"].strip()
        
        # Extract SQL from markdown code fences if present
        sql_match = re.search(r"```sql\s*(.*?)\s*```", response_text, re.DOTALL | re.IGNORECASE)
        if sql_match:
            generated_query = sql_match.group(1).strip()
        else:
            # Fallback to stripping standard block characters
            generated_query = re.sub(r"^```\w*\s*|\s*```$", "", response_text).strip()
            
        # Standard cleaning
        generated_query = generated_query.replace(";", "").strip()
        
        # Enforce Guardrail validation on output SQL
        guard_res = guardrail_check(generated_query)
        
        # Log to db
        log_entry = LLMLog(
            request_type="text_to_sql",
            prompt_hash=prompt_hash,
            model_name=model_name,
            latency_ms=latency_ms,
            status="success"
        )
        db.add(log_entry)
        db.commit()
        
        return {
            "sql": generated_query,
            "model": model_name,
            "latencyMs": latency_ms,
            "guardrail": guard_res,
            "mode": "online"
        }
        
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        # Log failure
        log_entry = LLMLog(
            request_type="text_to_sql",
            prompt_hash=prompt_hash,
            model_name=model_name,
            latency_ms=latency_ms,
            status="failed",
            error_message=str(e)
        )
        db.add(log_entry)
        db.commit()
        raise AIServiceError(f"LLM 接口调用失败: {str(e)}")
