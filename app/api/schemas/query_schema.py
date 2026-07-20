from typing import Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """
    健康检查响应参数
    params: code: 响应码
    params: message: 响应信息
    """
    code: int = Field(200, description="响应码")
    message: str = Field(None, description="响应信息")


class QueryRequest(BaseModel):
    """
    查询请求参数
    params: session_id: 会话ID
    params: query: 原始查询
    params: is_stream: 是否流式返回
    """
    session_id: str = Field(None, description="会话ID")
    query: str | None = Field(..., description="原始查询")
    is_stream: bool = Field(False, description="是否流式返回")


# 错误示范
# class A:
#     lst = []
#
# a1 = A()
# a2 = A()
# a1.lst.append(1)
#
# print(a2.lst)  # 输出 [1] ！！！ 被污染了

class AsyncQueryResponse(BaseModel):
    """
    查询响应参数  异步 流式
    params: session_id: 会话ID
    params: message: 响应信息

    """
    session_id: str = Field(..., description="会话ID")
    message: str = Field(..., description="响应信息")


class QueryResponse(BaseModel):
    """
    查询响应参数 同步 非流式
    params: session_id: 会话ID
    params: message: 响应信息
    params: answer: 回答内容
    params: image_urls: 图片URL列表
    params: done_list: 已完成任务列表

    """
    session_id: str = Field(..., description="会话ID")
    message: str = Field(..., description="响应信息")
    answer: str = Field("", description="回答内容")
    image_urls: list[str] = Field(description="图片URL列表", default_factory=list)
    done_list: list[str] = Field(description="已完成任务列表", default_factory=list)


class ClearHistoryResponse(BaseModel):
    """
    清空聊天记录接口响应体
    params: message: 操作提示信息
    params: deleted_count: 删除的记录数
    """
    message: str = Field(..., description="操作提示信息")
    deleted_count: int = Field(..., description="成功删除的消息条数")


class HistoryItem(BaseModel):
    """
    历史item 
    params: id: 消息ID
    params: session_id: 会话ID
    params: role: 角色
    params: text: 消息内容
    params: rewritten_query: 重写后的查询语句
    params: item_names: 索引名称列表
    params: image_urls: 图片URL列表
    params: ts: 时间戳
    """
    id: str = Field(default="", description="消息ID")
    session_id: str
    role: str
    text: str
    rewritten_query: str
    item_names: list[str] = Field(
        description="关联的item_name", default_factory=list)
    image_urls: list[str] = Field(description="关联的图片地址", default_factory=list)
    ts: Any = None


class HistoryListResponse(BaseModel):
    """
    历史列表接口响应体
    params: session_id: 会话ID
    params: items: 历史列表
    """
    session_id: str
    items: list[HistoryItem] = Field(
        description="查询的记录列表", default_factory=list)
