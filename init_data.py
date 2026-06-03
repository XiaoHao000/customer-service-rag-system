"""
数据初始化脚本 —— 首次部署时执行一次。

用法:
    python init_data.py                    # 全量初始化：FAQ → MySQL，文档 → Milvus
    python init_data.py --faq-only        # 仅初始化 FAQ 数据
    python init_data.py --index-only      # 仅重建 Milvus 索引
"""
import argparse
import os
import sys
import time

# 确保项目根目录在 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import logger, Config
from mysql_qa import MySQLClient, RedisClient
from rag_qa.core.vector_store import VectorStore
from rag_qa.core.document_loader import load_documents_from_directory, process_documents


def init_faq():
    """将 FAQ CSV 导入 MySQL 并预热 BM25 缓存到 Redis。"""
    logger.info("=" * 50)
    logger.info("步骤 1/2: 初始化 FAQ 数据 (MySQL + Redis)")

    conf = Config()
    mysql_client = MySQLClient()
    redis_client = RedisClient()

    # 建表
    mysql_client.cursor.execute("""
        CREATE TABLE IF NOT EXISTS faq_kb (
            id INT AUTO_INCREMENT PRIMARY KEY,
            product_line VARCHAR(50),
            question VARCHAR(1000),
            answer TEXT,
            UNIQUE KEY uk_product_question (product_line(50), question(200))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    mysql_client.connection.commit()

    # 导入 CSV 数据
    csv_path = os.path.join(os.path.dirname(__file__), "mysql_qa", "data", "faq_data.csv")
    if os.path.exists(csv_path):
        import pandas as pd
        df = pd.read_csv(csv_path)
        for _, row in df.iterrows():
            mysql_client.cursor.execute(
                "INSERT IGNORE INTO faq_kb (product_line, question, answer) VALUES (%s, %s, %s)",
                (row.get("product_line", ""), row.get("问题", ""), row.get("答案", ""))
            )
        mysql_client.connection.commit()
        logger.info(f"FAQ CSV 导入完成: {len(df)} 条")

    # 预热 BM25 缓存（触发 BM25Search 的 _load_data，把问题写入 Redis）
    from mysql_qa.retrieval.bm25_search import BM25Search
    bm25 = BM25Search(redis_client, mysql_client)
    bm25._load_data()
    logger.info("BM25 索引缓存已写入 Redis")

    mysql_client.close()
    logger.info("FAQ 初始化完成")


def init_vector_store():
    """加载知识库文档并建 Milvus 索引。"""
    logger.info("=" * 50)
    logger.info("步骤 2/2: 初始化向量知识库 (Milvus)")

    conf = Config()
    store = VectorStore()

    # 检查是否已有数据
    if store.client.has_collection(conf.MILVUS_COLLECTION_NAME):
        stats = store.client.get_collection_stats(conf.MILVUS_COLLECTION_NAME)
        row_count = stats.get("row_count", 0)
        if row_count > 0:
            logger.info(f"Milvus 集合已有 {row_count} 条数据，跳过索引。使用 --force 强制重建。")
            return

    # 加载文档
    data_dir = os.path.join(os.path.dirname(__file__), "rag_qa", "data")
    all_docs = []
    for folder in os.listdir(data_dir):
        folder_path = os.path.join(data_dir, folder)
        if os.path.isdir(folder_path) and folder.endswith("_data"):
            logger.info(f"加载文档目录: {folder}")
            docs = process_documents(
                folder_path,
                conf.PARENT_CHUNK_SIZE,
                conf.CHILD_CHUNK_SIZE,
                conf.CHUNK_OVERLAP,
            )
            all_docs.extend(docs)
            logger.info(f"  → {len(docs)} 个块")

    if not all_docs:
        logger.warning("未找到任何知识库文档，跳过索引")
        return

    # 写入 Milvus
    logger.info(f"总块数: {len(all_docs)}, 开始写入 Milvus...")
    t0 = time.time()
    store.add_documents(all_docs)
    logger.info(f"Milvus 索引完成, 耗时 {time.time() - t0:.1f}s, 共 {len(all_docs)} 块")


def main():
    parser = argparse.ArgumentParser(description="智能客服知识库 数据初始化")
    parser.add_argument("--faq-only", action="store_true", help="仅初始化 FAQ")
    parser.add_argument("--index-only", action="store_true", help="仅初始化向量索引")
    parser.add_argument("--force", action="store_true", help="强制重建向量索引（即使已有数据）")
    args = parser.parse_args()

    if args.force:
        conf = Config()
        store = VectorStore()
        if store.client.has_collection(conf.MILVUS_COLLECTION_NAME):
            store.client.drop_collection(conf.MILVUS_COLLECTION_NAME)
            logger.info("已删除旧 Milvus 集合，将重建索引")

    if args.faq_only:
        init_faq()
    elif args.index_only:
        init_vector_store()
    else:
        init_faq()
        init_vector_store()

    logger.info("=" * 50)
    logger.info("数据初始化全部完成!")


if __name__ == "__main__":
    main()
