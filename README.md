# 智能客服知识库系统 — Customer Service RAG System

面向企业技术支持的混合检索智能问答系统。BM25 + Milvus 双路召回，自训练 BERT 产品线分类器，两级问答架构——高频 FAQ 毫秒级响应，复杂问题 RAG 深度推理。

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Docker & Docker Compose（推荐）
- 或手动安装：MySQL 8.0 + Redis 7 + Milvus 2.4
- 8GB+ 内存

### Docker Compose（推荐）

```bash
git clone https://github.com/XiaoHao000/customer-service-rag-system.git
cd customer-service-rag-system

cp .env.example .env
# 编辑 .env：填入 API_KEY，其余用默认值

docker-compose up -d           # MySQL + Redis + Milvus

pip install -r requirements-docker.txt
python init_data.py            # 一键初始化 FAQ + 向量库
python new_main.py             # 混合检索模式 → port 5000
```

### 本地手动运行

```bash
pip install -r requirements-windows.txt   # Windows
# pip install -r requirements-mac.txt     # macOS

cp .env.example .env
python init_data.py
python new_main.py
```

---

## 🏗 架构

```
Web 前端 (SSE / WebSocket)
       ↓
  BERT 查询分类器 → 一般咨询 / 技术问题
       ↓
  策略选择器（4 种策略自适应）
       ↓
  ┌────┼────┐
  ↓    ↓     ↓
BM25  Dense  FAQ 直查
      ↓
   LLM 答案生成（流式推送）
```

## 💡 核心特性

- **BM25 + Milvus 双路召回**：稀疏检索毫秒级 FAQ 命中 + 稠密向量语义深度匹配
- **自训练 BERT 分类器**：CPU 推理 < 10ms，10 产品线自动路由到对应知识库
- **自适应 4 策略路由**：根据置信度自动选择 FAQ 直出 / BM25 / RAG / 混合模式
- **中文双粒度分块**：父块 500 字保上下文 + 子块 50 字精排，提升检索精度
- **WebSocket 流式推送**：长回答逐字实时推送，打字机体验
- **多模态文档解析**：PDF / PPT / Word / PNG 自动加载向量化
- **演示安全**：Redis 每日额度控制 + 输入安全清洗 + Prompt 注入检测

## 📁 项目结构

```
├── rag_qa/                    # RAG 核心
│   ├── core/                  # 检索 / 分类 / 策略 / 向量存储
│   ├── document_loaders/      # PDF/PPT/Word/PNG 文档解析
│   └── text_spliter/          # 中文双粒度分块器
├── mysql_qa/                  # FAQ 快速匹配
│   ├── db/                    # MySQL 连接池
│   ├── retrieval/             # BM25 稀疏检索
│   └── cache/                 # Redis 缓存
├── base/                      # 配置中心 + 日志
├── static/                    # Web 前端
├── init_data.py               # 一键初始化
├── new_main.py                # 混合检索入口
├── docker-compose.yml
└── .env.example
```

## 🛠 技术栈

| 层级 | 技术 |
|---|---|
| 检索 | BM25 + Milvus + BGE-M3 + BGE-Reranker-Large |
| 分类 | BERT-base-chinese 微调（CPU < 10ms） |
| 文档解析 | PyMuPDF + python-pptx + python-docx + EasyOCR |
| 后端 | Flask + WebSocket + SSE |
| 数据库 | MySQL 8.0 + Redis 7 + Milvus 2.4 |
| LLM | Qwen3-Max（OpenAI 兼容接口） |

## 📄 License

MIT
