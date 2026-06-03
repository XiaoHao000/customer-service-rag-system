#!/bin/bash
# ============================================
# 智能客服系统 Docker 入口脚本
# 首次启动自动初始化数据（FAQ → MySQL, 文档 → Milvus）
# ============================================
set -e

echo "=== 智能客服系统 Docker 启动 ==="

# 等待 MySQL 就绪
echo "[1/3] 等待 MySQL 就绪..."
RETRIES=30
until mysqladmin ping -h "${MYSQL_HOST:-mysql}" -u root -p"${MYSQL_PASSWORD:-12345678}" --silent 2>/dev/null; do
    RETRIES=$((RETRIES - 1))
    if [ $RETRIES -le 0 ]; then
        echo "ERROR: MySQL 启动超时，跳过数据初始化"
        break
    fi
    echo "  等待 MySQL... (剩余尝试 $RETRIES)"
    sleep 3
done

if [ $RETRIES -gt 0 ]; then
    echo "[2/3] 检查数据是否已初始化..."
    # 检查 faq_kb 表中是否有数据
    FAQ_COUNT=$(mysql -h "${MYSQL_HOST:-mysql}" -u root -p"${MYSQL_PASSWORD:-12345678}" \
        support_kb -sN -e "SELECT COUNT(*) FROM faq_kb;" 2>/dev/null || echo "0")

    if [ "$FAQ_COUNT" = "0" ] || [ -z "$FAQ_COUNT" ]; then
        echo "  数据未初始化，执行数据初始化..."
        python init_data.py
        echo "  数据初始化完成 ($(mysql -h ${MYSQL_HOST:-mysql} -u root -p${MYSQL_PASSWORD:-12345678} support_kb -sN -e 'SELECT COUNT(*) FROM faq_kb;') 条 FAQ)"
    else
        echo "  数据已存在 ($FAQ_COUNT 条 FAQ)，跳过初始化。"
        echo "  如需强制重建，请执行: docker compose exec app python init_data.py --force"
    fi
fi

echo "[3/3] 启动应用服务..."
exec python app.py
