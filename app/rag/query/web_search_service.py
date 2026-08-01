import asyncio
import json
import time

from agents.mcp import MCPServerStreamableHttp

from app.process.query.agent.state import QueryGraphState
from app.shared.runtime.logger import logger
from app.infra.config.providers import infra_config


def get_data_and_validate(state) -> str:
    rewritten_query = state.get("rewritten_query")
    if not rewritten_query:
        logger.error(f"重写的问题为空,业务无法继续,提前终止!")
        raise ValueError(f"重写的问题为空,业务无法继续,提前终止!")
    return rewritten_query


async def search_web_documents_async(rewritten_query):
    """
    异步调用MCP联网搜索工具，获取互联网检索结果
    Args:
        rewritten_query: 标准化检索问句
        count: 返回网页检索结果条数
    Returns:
        联网搜索工具原始返回数据对象
    """
    # 1. 链接mcp服务
    mcp_server = MCPServerStreamableHttp(
        name="Streamable HTTP Python Server",
        params={
            "url": infra_config.mcp_config.mcp_base_url,
            "headers": {"Authorization": f"Bearer {infra_config.mcp_config.api_key}"},
            "timeout": 50,
        },
        cache_tools_list=True,
        max_retry_attempts=3,
    )
    try:
        # 2. mcp服务链接
        await mcp_server.connect()
        # 打印当前可用工具列表，用于调试观测
        # tool_list = await mcp_server.list_tools()
        # logger.info(f"工具列表:{tool_list}")
        # 3. mcp工具调用
        mcp_result = await mcp_server.call_tool(
            tool_name="bailian_web_search",
            arguments={
                "query": rewritten_query,
                "count": 5
            }
        )
        return mcp_result
    except Exception as e:
        logger.exception(f"mcp调用发生问题,问题:{str(e)}")
    finally:
        # 4. 清空链接  无论成功失败，最终释放连接资源，避免连接堆积
        await mcp_server.cleanup()


def search_by_web(state: QueryGraphState) -> QueryGraphState:
    """
    网络搜索服务：
    1. 通过 MCP 协议异步调用百炼联网搜索接口
    2. 将用户的查询转化为实时的、结构化的网络搜索结果
    3. 包含标题、链接和摘要
    4. 回写 web_search_docs
    """
    # 3. 获取并校验参数(state) -> rewritten_query
    rewritten_query = get_data_and_validate(state)
    # 4. async 使用openai提供mcp方式进行调用(rewritten_query) -> 查询结果
    # MCP SDK 的联网调用是异步实现，因此这里使用 asyncio.run() 做同步与异步之间的桥接。
    # mcp_result = asyncio.run(search_web_documents_async(rewritten_query))
    # 5. 结果解析 todo 注意: 外层都是属性,不是字典
    # text = mcp_result.content[0].text
    text = """
        {\"pages\":[{\"snippet\":\"123代表的是什么意思? 自然数:123是位于122和124之间的奇数、合数,属于有理数。日常交流:表示到来或问候。寓意进步:逐步递增,象征持续提升。强调基础:体现“一切从1开始”的起始观念。表示理解:在某些语境中意为“知道”或“明白”。统一行动:儿童游戏或口号中用于同步动作(如“1、2、3,嘿!”)。\",\"hostname\":\"百度教育\",\"hostlogo\":\"https://mbs1.bdstatic.com/searchbox/mappconsole/image/20230906/3096e08a-869d-46a7-8d30-5e32adb66fdc.png\",\"title\":\"123代表的是什么意思?\",\"url\":\"https://easylearn.baidu.com/edu-page/tiangong/questiondetail?id=1818048221841140497&fr=search\"}],\"request_id\":\"6ebb31c4-99de-4325-b096-76663ebc4b34\",\"tools\":[],\"status\":0}
    """
    # {pages:[{snippet,title,url},{},{}]}
    text_dict = json.loads(text)
    web_search_docs = text_dict.get("pages", [])
    # 6. 返回列表即可
    return web_search_docs
