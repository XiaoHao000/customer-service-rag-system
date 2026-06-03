from fastapi import FastAPI, WebSocket, HTTPException, Query, Depends, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect
from prometheus_fastapi_instrumentator import Instrumentator
import os
from pydantic import BaseModel, Field
import asyncio
import json
import uuid
from typing import Optional, List, Dict, Any
import time
import re

# 导入现有的系统
from new_main import IntegratedQASystem
from base import logger
from base.config import Config
from utils.daily_budget import DailyBudgetMiddleware, check_ws_quota

# 创建应用实例
app = FastAPI(
    title="智能客服知识库系统",
    description="集成 MySQL + RAG + BERT 混合检索的智能问答系统 — 支持 Prometheus 监控"
)

# 配置CORS，允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 每日演示额度中间件：每 IP 每天最多 30 次查询，防止公开演示 Token 被滥用
_conf = Config()
app.add_middleware(
    DailyBudgetMiddleware,
    redis_url=_conf.redis_url,
    max_queries_per_day=_conf.DEMO_DAILY_QUERY_LIMIT,
)

# 创建静态文件目录
os.makedirs("static", exist_ok=True)

# 延迟初始化：启动时才连接各服务，避免模块导入时崩溃
qa_system: Optional[IntegratedQASystem] = None
_startup_errors: list = []
_startup_ok: bool = False


def require_qa_system():
    """API 依赖：确保 QA 系统已就绪，否则返回 503"""
    if not _startup_ok or qa_system is None:
        raise HTTPException(
            status_code=503,
            detail=f"服务尚未就绪。启动错误: {'; '.join(_startup_errors) if _startup_errors else '请稍后重试'}"
        )
    return qa_system


@app.on_event("startup")
async def startup():
    """应用启动时初始化所有服务连接，失败不阻塞启动"""
    global qa_system, _startup_ok, _startup_errors

    # ① 检查 API_KEY
    api_key = os.getenv("API_KEY")
    if not api_key:
        _startup_errors.append("API_KEY 环境变量未设置，LLM 调用将失败。请在 .env 文件或环境变量中设置 API_KEY")
        logger.error("API_KEY 未设置")

    # ② 尝试初始化 QA 系统
    try:
        qa_system = IntegratedQASystem()
        _startup_ok = True
        logger.info("✅ QA 系统初始化完成，所有服务连接正常")
    except Exception as e:
        _startup_errors.append(f"服务连接失败: {e}")
        logger.error(f"QA 系统初始化失败: {e}")
        # 不阻塞启动 — 静态页面和健康检查仍可访问

# 定义日常问候用语模式和回复
GREETING_PATTERNS = [
    {
        "pattern": r"^(你好|您好|hi|hello|嗨|嘿|哟)",
        "response": "你好！我是智能客服知识库系统，基于 BM25 + RAG 双通道混合检索架构，覆盖企业微信、钉钉、CRM、ERP、飞书等多产品线知识库，有什么可以帮你的？"
    },
    {
        "pattern": r"^(你是谁|您是谁|你叫什么|你的名字|who are you)",
        "response": "我是智能客服知识库系统，基于 RAG + BERT 混合检索架构的知识库问答系统。支持 BM25 毫秒级 FAQ 匹配和 RAG 深度推理双通道自动切换。"
    },
    {
        "pattern": r"^(在吗|在不在|有人吗)",
        "response": "我在！我是智能客服知识库系统，随时为你解答企业软件相关问题！"
    },
    {
        "pattern": r"^(谢谢|感谢|thanks|thank you)",
        "response": "不客气！如有其他问题随时问我。"
    },
    {
        "pattern": r"^(再见|拜拜|bye|88)",
        "response": "再见！祝你工作顺利！"
    },
    {
        "pattern": r"^(干嘛呢|你在干嘛|做什么|你(能|可以)做什么|你有什么功能|你会什么)",
        "response": "我可以帮你：\n1. 🎯 FAQ 精确匹配 — 毫秒级返回产品使用问题答案\n2. 🧠 RAG 深度推理 — 复杂问题语义理解 + LLM 生成\n3. 🔀 自动路由 — BERT 模型识别产品线，自动切换知识库\n4. 📚 多产品线覆盖 — 企业微信/钉钉/CRM/ERP/飞书/网络/VPN/邮箱/打印机"
    },
    {
        "pattern": r"^(你(聪明|厉害|好|棒)|不错|很好|赞|牛)",
        "response": "谢谢夸奖！这些都是基于 RAG 检索增强和 BERT 意图分类技术实现的，有什么具体问题我可以帮你解决？"
    },
    # 攻击/越界检测 — 优雅兜底
    {
        "pattern": r".*(SQL|注入|注入攻击|DROP TABLE|DELETE FROM|UNION SELECT).*",
        "response": "抱歉，我检测到你的输入包含不安全的数据库操作请求。作为知识库问答系统，我只处理产品使用相关的问题查询。如有真实的数据库操作需求，请联系系统管理员。"
    },
    {
        "pattern": r".*(忽略|忘记).*(指令|提示|规则|限制|系统).*",
        "response": "我是基于 RAG 架构的知识库系统，专注于企业软件产品问题解答。如果你有产品使用方面的疑问，我很乐意帮你！"
    },
]


# 定义请求模型
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="用户查询")
    source_filter: Optional[str] = Field(None, max_length=50)
    session_id: Optional[str] = Field(None, max_length=36)


# 定义响应模型
class QueryResponse(BaseModel):
    answer: str
    is_streaming: bool
    session_id: str
    processing_time: float


# 添加静态文件服务
app.mount("/static", StaticFiles(directory="static"), name="static")


# 根路径重定向到index.html
@app.get("/")
async def read_root():
    return FileResponse("static/index.html")


# 创建新会话
@app.post("/api/create_session")
async def create_session():
    session_id = str(uuid.uuid4())
    return {"session_id": session_id}


# 查询历史消息
@app.get("/api/history/{session_id}")
async def get_history(session_id: str):
    qa = require_qa_system()
    try:
        history = qa.get_session_history(session_id)
        return {"session_id": session_id, "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史记录失败: {str(e)}")


# 清除历史消息
@app.delete("/api/history/{session_id}")
async def clear_history(session_id: str):
    qa = require_qa_system()
    success = qa.clear_session_history(session_id)
    if success:
        return {"status": "success", "message": "历史记录已清除"}
    else:
        raise HTTPException(status_code=500, detail="清除历史记录失败")


# 检查是否为日常问候用语并返回模板回复
def check_greeting(query: str) -> Optional[str]:
    query_text = query.strip()
    for pattern_info in GREETING_PATTERNS:
        if re.match(pattern_info["pattern"], query_text, re.IGNORECASE):
            return pattern_info["response"]
    return None


# 入参 出参
# 非流式查询接口
@app.post("/api/query")
async def query(request: QueryRequest):
    start_time = time.time()
    session_id = request.session_id or str(uuid.uuid4())

    # ① 输入安全清洗
    from utils.security import sanitize_user_input, is_empty_or_noise
    safe_query, _flagged = sanitize_user_input(request.query)
    if is_empty_or_noise(safe_query):
        return {
            "answer": "抱歉，我无法理解你的输入。请提供一个有意义的查询，例如产品使用问题或技术故障排查。",
            "is_streaming": False,
            "session_id": session_id,
            "processing_time": time.time() - start_time
        }

    # ② 检查是否为日常问候/攻击/越界
    greeting_response = check_greeting(safe_query)
    if greeting_response:
        return {
            "answer": greeting_response,
            "is_streaming": False,
            "session_id": session_id,
            "processing_time": time.time() - start_time
        }

    qa = require_qa_system()
    # ③ 判断是否需要流式处理（基于 BM25 置信度阈值）
    answer, need_rag = qa.bm25_search.search(safe_query, threshold=0.85)
    if need_rag:
        return {
            "answer": "请使用WebSocket接口获取流式响应",
            "is_streaming": True,
            "session_id": session_id,
            "processing_time": time.time() - start_time
        }

    # ④ 非流式查询，直接返回 BM25 检索的答案
    return {
        "answer": answer,
        "is_streaming": False,
        "session_id": session_id,
        "processing_time": time.time() - start_time
    }


# 流式查询WebSocket接口
@app.websocket("/api/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # 检查服务是否就绪
    try:
        qa = require_qa_system()
    except HTTPException as e:
        await websocket.send_json({"type": "error", "error": e.detail})
        await websocket.close()
        return

    # 每日演示额度检查：WebSocket 不走 HTTP 中间件，需单独计数
    client_ip = websocket.client.host if websocket.client else "unknown"
    ws_allowed, ws_count = await check_ws_quota(_conf.redis_url, client_ip, _conf.DEMO_DAILY_QUERY_LIMIT)
    if not ws_allowed:
        await websocket.send_json({
            "type": "error",
            "error": "今日演示额度已用完，请明天再试",
        })
        await websocket.close()
        return

    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            request_data = json.loads(data)

            query = request_data.get("query", "")
            source_filter = request_data.get("source_filter")
            session_id = request_data.get("session_id", str(uuid.uuid4()))

            # ① 输入安全清洗
            from utils.security import sanitize_user_input, is_empty_or_noise
            safe_query, _flagged = sanitize_user_input(query)
            if is_empty_or_noise(safe_query):
                if websocket.client_state == websocket.client_state.CONNECTED:
                    await websocket.send_json({
                        "type": "token",
                        "token": "抱歉，我无法理解你的输入。请提供一个有意义的查询。",
                        "session_id": session_id
                    })
                    await websocket.send_json({
                        "type": "end",
                        "session_id": session_id,
                        "is_complete": True,
                        "processing_time": 0
                    })
                break

            start_time = time.time()

            # 发送开始标志
            if websocket.client_state == websocket.client_state.CONNECTED:
                await websocket.send_json({
                    "type": "start",
                    "session_id": session_id
                })

            # ② 检查是否为日常问候/攻击/越界
            greeting_response = check_greeting(safe_query)
            if greeting_response:
                if websocket.client_state == websocket.client_state.CONNECTED:
                    await websocket.send_json({
                        "type": "token",
                        "token": greeting_response,
                        "session_id": session_id
                    })
                    await websocket.send_json({
                        "type": "end",
                        "session_id": session_id,
                        "is_complete": True,
                        "processing_time": time.time() - start_time
                    })
                break

            # ③ 调用QA系统进行查询，流式返回结果
            collected_answer = ""
            gen = qa.query(safe_query, source_filter=source_filter, session_id=session_id)
            try:
                for token, is_complete in gen:
                    collected_answer += token

                    if is_complete and not collected_answer:
                        if websocket.client_state == websocket.client_state.CONNECTED:
                            await websocket.send_json({
                                "type": "end",
                                "session_id": session_id,
                                "is_complete": True,
                                "processing_time": time.time() - start_time
                            })
                        break

                    if token and websocket.client_state == websocket.client_state.CONNECTED:
                        await websocket.send_json({
                            "type": "token",
                            "token": token,
                            "session_id": session_id
                        })

                    if is_complete:
                        if websocket.client_state == websocket.client_state.CONNECTED:
                            await websocket.send_json({
                                "type": "end",
                                "session_id": session_id,
                                "is_complete": True,
                                "processing_time": time.time() - start_time
                            })
                        break

                    await asyncio.sleep(0.01)

            except WebSocketDisconnect as e:
                print(f"WebSocket disconnected: code={e.code}, reason={e.reason}")
                gen.close()
            except Exception as e:
                print(f"WebSocket error: {str(e)}")
                gen.close()
                if websocket.client_state == websocket.client_state.CONNECTED:
                    await websocket.send_json({
                        "type": "error",
                        "error": str(e)
                    })
            else:
                gen.close()

    except WebSocketDisconnect as e:
        print(f"WebSocket disconnected: code={e.code}, reason={e.reason}")
    except Exception as e:
        print(f"WebSocket handler error: {str(e)}")
    finally:
        try:
            if websocket.client_state == websocket.client_state.CONNECTED:
                await websocket.close()
        except Exception as e:
            print(f"Error closing WebSocket: {str(e)}")


# 健康检查端点 — 返回各组件真实状态
@app.get("/health")
async def health_check():
    return {
        "status": "healthy" if _startup_ok else "degraded",
        "services": {
            "api": True,
            "db": _startup_ok,
            "redis": _startup_ok,
            "milvus": _startup_ok,
            "llm": _startup_ok,
        },
        "errors": _startup_errors if _startup_errors else None,
    }


# 获取有效的产品线
@app.get("/api/sources")
async def get_sources():
    qa = require_qa_system()
    return {"sources": qa.config.VALID_SOURCES}


@app.on_event("shutdown")
async def shutdown():
    """应用关闭时释放所有资源"""
    global qa_system
    if qa_system is not None:
        qa_system.close()


# ==================== Prometheus 监控 ====================
Instrumentator(
    excluded_handlers=["/metrics", "/health"],
    should_group_status_codes=True,
    should_round_latency_decimals=True,
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=True)

print("Prometheus 指标已暴露: /metrics")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8003, reload=False)
