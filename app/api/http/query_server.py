from pathlib import Path
import uuid

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware

from app.shared.runtime.logger import PROJECT_ROOT, logger
from app.infra.config.providers import infra_config
from app.infra.persistence.history_repository import history_repository
from app.process.query.agent.main_graph import query_app as query_graph_app
from app.process.query.agent.state import create_query_default_state, QueryGraphState
from app.shared.utils.sse_utils import SSEEvent, create_sse_queue, push_to_session, sse_generator
from app.shared.utils.task_utils import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PROCESSING,
    clear_task,
    get_done_task_list,
    get_task_result,
    update_task_status,
)
from app.api.schemas.query_schema import HealthResponse, QueryRequest, QueryResponse, AsyncQueryResponse, HistoryItem, HistoryListResponse, ClearHistoryResponse

# 定义fastapi对象
app = FastAPI(
    title=infra_config.settings_config.query_app_name,
    description="描述,进行rag查询的服务对象",
    version="0.2.0"
)

# 跨域处理
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(infra_config.settings_config.cors_origins),
    allow_methods=['*'],
    allow_headers=['*']
)


# 获取查询演示页面
@app.get("/")
def query_html():
    """
    返回查询演示页面。
    Returns:

    """
    query_html_obj: Path = PROJECT_ROOT / "app" / "resources" / "page" / "chat.html"
    return FileResponse(str(query_html_obj), media_type="text/html")


# 健康检查接口
@app.get("/health")
def health_check():
    """
    健康检查接口。
    Returns:
        dict: 返回健康检查结果。
    """
    import datetime
    logger.info(f"完成健康检查！{datetime.datetime.now()}")
    return HealthResponse(code=200, message=(f"完成健康检查！{datetime.datetime.now()}"))


def invoke_query_graph(session_id: str, original_query: str, is_stream: bool) -> QueryGraphState:
    try:
        # 任务整体状态监控!!
        # 需不需要传入第三个参数???

        # 清空task字典! 不管是流式还是非流式都需要!!!
        clear_task(session_id)

        # 如果是流式,我们可以提前创建队列! session_id : queue
        if is_stream:
            create_sse_queue(session_id)

        # 考虑: 可能异步执行 is_stream=True 也可能同步执行 False
        update_task_status(
            session_id, TASK_STATUS_PROCESSING, push_queue=is_stream)

        # 核心
        # 1. 封装成state
        query_state = create_query_default_state(
            session_id=session_id, original_query=original_query, is_stream=is_stream)
        # 2. 执行图对象
        result_state = query_graph_app.invoke(query_state)

        # process ...
        update_task_status(session_id, TASK_STATUS_COMPLETED,
                           push_queue=is_stream)

        # 执行完毕以后 [final - sse - is_stream = True]
        if is_stream:
            push_to_session(
                session_id,
                SSEEvent.FINAL,
                {
                    "answer": result_state.get('answer'),
                    "status": "completed",
                    "image_urls": result_state.get('image_urls', [])
                }
            )

        return result_state
    except Exception as e:
        # 考虑: 可能异步执行 is_stream=True 也可能同步执行 False
        update_task_status(session_id, TASK_STATUS_FAILED,
                           push_queue=is_stream)
        push_to_session(session_id, SSEEvent.ERROR, {
                        "error": f"{session_id}业务失败！原因是{str(e)}"})
        logger.exception(f"执行查询流程报错,错误信息:{str(e)}")

# 查询接口


@app.post("/query")
async def query(background_tasks: BackgroundTasks, query_params: QueryRequest):
    """
     rag查询接口。
    Args:
        background_tasks: 后台任务对象。
        query: 查询参数。

    Returns:
        QueryResponse: 查询结果。
    """
    # 1. 获取参数
    query = query_params.query
    session_id = query_params.session_id or str(uuid.uuid4())
    is_stream = query_params.is_stream
    # 2. 封装执行图对象的方法
    # 3. 判断是不是流式
    if is_stream:
        # 4. 是 异步执行图方法
        background_tasks.add_task(
            invoke_query_graph,
            session_id=session_id,
            original_query=query,
            is_stream=is_stream
        )
        return AsyncQueryResponse(
            message=f"已经开始:{query}任务查询!",
            session_id=session_id
        )
    else:
        # 5. 不是 直接调用执行图方法
        state: QueryGraphState = invoke_query_graph(
            session_id=session_id,
            original_query=query,
            is_stream=is_stream
        )

        # task_utils
        done_list = get_done_task_list(session_id)

        return QueryResponse(
            message=f"完成{query}所有内容检索!",
            session_id=session_id,
            answer=state.get("answer"),
            done_list=done_list,
            image_urls=state.get("image_urls", [])
        )


# 接口4: 流式接口
@app.get("/stream/{session_id}")
def stream(session_id: str, request: Request):

    # request.is_disconnected() 通过request对象可以检查前端是否已经断开!
    return StreamingResponse(
        sse_generator(session_id, request),
        media_type="text/event-stream"
    )


@app.delete("/history/{session_id}")
def clear_history(session_id: str):
    deleted_count = history_repository.clear_session(session_id=session_id)
    return ClearHistoryResponse(
        message=f"session_id:{session_id}历史聊天记录已经清空!",
        deleted_count=deleted_count
    )


@app.get("/history/{session_id}")
def get_history(session_id: str, limit: int = 10):
    history_list: list[dict] = (history_repository.list_recent(
        session_id=session_id, limit=limit))
    print(session_id, history_list)
    return HistoryListResponse(
        session_id=session_id,
        items=[
            HistoryItem(
                id=str(item.get("_id")),
                session_id=session_id,
                role=item.get("role"),
                text=item.get("text"),
                rewritten_query=item.get("rewritten_query"),
                item_names=item.get("item_names", []),
                image_urls=item.get("image_urls", []),
                ts=item.get("ts")
            )
            for item in history_list
        ]  # _id  |  _id ObjectId
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=infra_config.settings_config.app_host,
                port=infra_config.settings_config.query_app_port)

#  python -m app.api.http.query_server
