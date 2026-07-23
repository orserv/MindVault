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
        {\"pages\":[{\"snippet\":\"hxf0619 1自然数 123(一百二十三),是122和124之间的自然数 因数分解 合数(有公约数1,3,41,123) 2自然数 在数学界享有“最简单的数字黑洞”的美称,原因是: 将任意多位自然数按照“偶数数字个数”、“奇数数字个数”、“数字数总数”写法写后,有限次内会得到123。例:818637954--->459--->123 1除以813=0.0012300123001230012300123无限循环下去 3自然数 质数中的第2个。[编辑本段]影视剧里的动物 情景剧《武林外传》中燕小六(肖剑饰)的巡犬 后被郭蔷薇打死。[编辑本段]国际密码 在网游中常被称作“国密”,常在游戏房间中设定密码,即国际密码。123!321即为反国密·。[编辑本段]123的倍数 *2 246 *3 369 *4 492 *5 615 *6 738 *7 861 *8 984 123乘813,等于99999 有用(0)回复\",\"hostname\":\"中关村在线\",\"hostlogo\":\"https://ss0.baidu.com/6ONWsjip0QIZ8tyhnq/it/u=3275015716,579541867&fm=195&app=88&f=JPEG?w=200&h=200\",\"title\":\"123是什么意思啊\",\"url\":\"https://wap.zol.com.cn/ask/details_22049894_231139_3.html\"},{\"snippet\":\"123,又称一百二十三、一二三,是122和124之间的自然数,属奇数、合数、阿拉伯数字与有理数,也是最简单的数列组合。其大写为壹佰贰拾叁、壹贰叁,罗马数字为CXXIII,因数分解3×41。 123在数学领域特质鲜明,是第92个合数、第10个卢卡斯数,还享有“最简单的数字黑洞”美称,任意多位自然数按特定规则书写,有限次内均能得到123;1除以813的结果以123无限循环,123与813相乘得99999,数学特性独特。 此外,123应用场景广泛,网游中是常用的房间密码,衍生出多种变体;儿童游戏、集体活动里可作为统一行动口号;聊天时能提醒他人自己上线,还暗含步步高升寓意,是兼具实用与文化意义的数字符号。\",\"hostname\":\"百度百科\",\"hostlogo\":\"https://mbs1.bdstatic.com/searchbox/mappconsole/image/20200630/db4d874a-872b-4b27-931d-775a91ed0003.png\",\"title\":\"123\",\"url\":\"https://baike.baidu.com/item/123/1674043\"},{\"snippet\":\"解释题:123是什么意思呢,代表着什么? 123是一个自然数,表示一百二十三,在数学中是122和124之间的奇数、合数;在游戏文化中,它也常代表“木头人”游戏的口令(玩家在喊“123”时可行动,喊“木头人”时需静止)。\",\"hostname\":\"百度教育\",\"hostlogo\":\"https://mbs1.bdstatic.com/searchbox/mappconsole/image/20230906/3096e08a-869d-46a7-8d30-5e32adb66fdc.png\",\"title\":\"解释题:123是什么意思呢,代表着什么?\",\"url\":\"https://easylearn.baidu.com/edu-page/tiangong/questiondetail?id=1818069840653323736&fr=search\"},{\"snippet\":\"123表示什么? 123是122和124之间的自然数,是合数,同时也是数学中的“最简单的数字黑洞”。\",\"hostname\":\"百度教育\",\"hostlogo\":\"https://mbs1.bdstatic.com/searchbox/mappconsole/image/20230906/3096e08a-869d-46a7-8d30-5e32adb66fdc.png\",\"title\":\"123表示什么? \",\"url\":\"https://easylearn.baidu.com/edu-page/tiangong/questiondetail?id=1711233613197653054&fr=search\"},{\"snippet\":\"123代表的是什么意思? 自然数:123是位于122和124之间的奇数、合数,属于有理数。日常交流:表示到来或问候。寓意进步:逐步递增,象征持续提升。强调基础:体现“一切从1开始”的起始观念。表示理解:在某些语境中意为“知道”或“明白”。统一行动:儿童游戏或口号中用于同步动作(如“1、2、3,嘿!”)。\",\"hostname\":\"百度教育\",\"hostlogo\":\"https://mbs1.bdstatic.com/searchbox/mappconsole/image/20230906/3096e08a-869d-46a7-8d30-5e32adb66fdc.png\",\"title\":\"123代表的是什么意思?\",\"url\":\"https://easylearn.baidu.com/edu-page/tiangong/questiondetail?id=1818048221841140497&fr=search\"}],\"request_id\":\"6ebb31c4-99de-4325-b096-76663ebc4b34\",\"tools\":[],\"status\":0}
    """

    # {pages:[{snippet,title,url},{},{}]}
    text_dict = json.loads(text)
    web_search_docs = text_dict.get("pages", [])
    # 6. 返回列表即可
    return web_search_docs
