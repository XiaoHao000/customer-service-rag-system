import configparser
import json
import os


class Config:
    def __init__(self, config_file=None):
        if config_file is None:
            config_file = os.environ.get("CONFIG_PATH", os.path.join(os.path.dirname(__file__), "..", "config.ini"))
            config_file = os.path.abspath(config_file)
        self.config = configparser.ConfigParser()
        self.config.read(config_file, encoding="utf-8")

        # MySQL — 环境变量优先（Docker 部署时覆盖 localhost）
        self.MYSQL_HOST = os.environ.get("MYSQL_HOST",
            self.config.get('mysql', 'host', fallback='localhost'))
        self.MYSQL_PORT = int(os.environ.get("MYSQL_PORT",
            self.config.get('mysql', 'port', fallback='3307')))
        self.MYSQL_USER = os.environ.get("MYSQL_USER",
            self.config.get('mysql', 'user', fallback='root'))
        self.MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD",
            self.config.get('mysql', 'password', fallback=''))
        self.MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE",
            self.config.get('mysql', 'database', fallback='support_kb'))

        # Redis — 环境变量优先
        self.REDIS_HOST = os.environ.get("REDIS_HOST",
            self.config.get('redis', 'host', fallback='localhost'))
        self.REDIS_PORT = int(os.environ.get("REDIS_PORT",
            self.config.get('redis', 'port', fallback='6379')))
        self.REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD",
            self.config.get('redis', 'password', fallback=''))
        self.REDIS_DB = int(os.environ.get("REDIS_DB",
            self.config.get('redis', 'db', fallback='0')))

        # Milvus — 环境变量优先
        self.MILVUS_HOST = os.environ.get("MILVUS_HOST",
            self.config.get('milvus', 'host', fallback='localhost'))
        self.MILVUS_PORT = os.environ.get("MILVUS_PORT",
            self.config.get('milvus', 'port', fallback='19530'))
        # Milvus 数据库名
        self.MILVUS_DATABASE_NAME = self.config.get('milvus', 'database_name', fallback='support_kb')
        # Milvus 集合名
        self.MILVUS_COLLECTION_NAME = self.config.get('milvus', 'collection_name', fallback='support_faq_v1')

        # LLM 配置
        # LLM 模型名
        self.LLM_MODEL = self.config.get('llm', 'model', fallback='qwen3-max')
        # DashScope API 密钥
        # self.DASHSCOPE_API_KEY = self.config.get('llm', 'dashscope_api_key')
        self.DASHSCOPE_API_KEY = os.getenv("API_KEY")
        # DashScope API 地址
        self.DASHSCOPE_BASE_URL = self.config.get('llm', 'dashscope_base_url',
                                                  fallback='https://dashscope.aliyuncs.com/compatible-mode/v1')

        # 检索参数
        # 父块大小
        self.PARENT_CHUNK_SIZE = self.config.getint('retrieval', 'parent_chunk_size', fallback=500)
        # 子块大小
        self.CHILD_CHUNK_SIZE = self.config.getint('retrieval', 'child_chunk_size', fallback=50)
        # 块重叠大小
        self.CHUNK_OVERLAP = self.config.getint('retrieval', 'chunk_overlap', fallback=5)
        # 检索返回数量
        self.RETRIEVAL_K = self.config.getint('retrieval', 'retrieval_k', fallback=3)
        # 最终候选数量
        self.CANDIDATE_M = self.config.getint('retrieval', 'candidate_m', fallback=2)

        # 应用配置
        # 有效来源列表
        self.VALID_SOURCES = json.loads(
            self.config.get('app', 'valid_sources', fallback='["product_a", "product_b"]'))
        # 客服电话
        self.CUSTOMER_SERVICE_PHONE = self.config.get('app', 'customer_service_phone', fallback='12345678')
        # 日志文件路径
        self.LOG_FILE = self.config.get('logger', 'log_file', fallback='logs/app.log')

        # LangSmith 可观测性配置
        self.langsmith_api_key = os.getenv("LANGSMITH_API_KEY", "")
        self.langsmith_project = os.getenv("LANGSMITH_PROJECT", "smart-qa-system")
        if self.langsmith_api_key:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = self.langsmith_api_key
            os.environ["LANGCHAIN_PROJECT"] = self.langsmith_project

        # Demo Budget（演示服务防滥用 — 每个 IP 每天独立额度，用户之间互不影响）
        self.DEMO_DAILY_QUERY_LIMIT = int(os.getenv("DEMO_DAILY_QUERY_LIMIT", "30"))

        # model paths — 使用项目根目录的相对路径，支持环境变量覆盖
        _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _default_models = os.path.join(_project_root, "rag_qa", "models")
        _default_bert = os.path.join(_project_root, "rag_qa", "core", "bert_query_classifier")

        self.nlp_bert_doc_seg = os.environ.get(
            "MODEL_PATH_DOC_SEG",
            os.path.join(_default_models, "nlp_bert_document-segmentation_chinese-base")
        )
        self.bert_intent_cls = os.environ.get(
            "MODEL_PATH_BERT_INTENT",
            os.path.join(_default_bert)
        )

    @property
    def redis_url(self) -> str:
        """构建 Redis URL（用于演示额度计数器）。从已有 Redis 配置字段拼装。"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


if __name__ == '__main__':
    conf = Config()
    print(conf.MYSQL_HOST)
