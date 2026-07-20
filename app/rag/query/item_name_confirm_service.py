from langchain_core.output_parsers import JsonOutputParser

from app.process.query.agent.state import QueryGraphState
from app.shared.runtime.logger import logger, step_log
from app.infra.llm.providers import llm_provider
from app.infra.persistence.history_repository import history_repository
from app.infra.vector_store.milvus_gateway import milvus_gateway


# 1.获取并且校验参数(state) -> session_id / original_query
@step_log("get_data_and_validates")
def get_data_and_validates(state: QueryGraphState) -> tuple[str, str]:
    """
    参数校验
    :param state:
    :return: session_id / original_query
    """
    # 获取数据
    session_id = state.get("session_id")
    original_query = state.get("original_query")
    # 非空校验
    if not session_id or not original_query:
        logger.error(f"核心参数session_id或者original_query为空,业务无法继续,提前终止!")
        raise ValueError(f"核心参数session_id或者original_query为空,业务无法继续,提前终止!")
    # 返回结果
    return session_id, original_query


# 2.获取(有效的)历史聊天记录,并且拼接成history_text提示词
step_log("get_history_messages_and_context")


def get_history_messages_and_context(session_id: str) -> str:
    """
    获取(有效的)历史聊天记录,并且拼接成上下文
    :param session_id:
    :return: history_text
    """
    # 获取mongodbclient
    # 根据session_id获取最近聊天录(10)
    messages_list: list[dict] = history_repository.list_recent(
        session_id=session_id, limit=10)
    if not messages_list or len(messages_list) == 0:
        logger.warning(
            f"session_id:{session_id}没有历史聊天记录, 提前跳出，history_text为空!")
        return "无历史对话记录"
    # 2. 有历史记录
    final_messages_list: list[dict] = [
        # 列表推导式推到有效的messages [item_names]
        item for item in messages_list if len(item.get("item_names", [])) > 0
    ]
    # 3. 获取有效的messages
    if not final_messages_list or len(final_messages_list) == 0:
        logger.warning(
            f"session_id:{session_id}没有有效的历史聊天记录, 提前跳出，history_text为空!")
        return "无有效对话记录"
    # 将有效的messages拼接成history_text
    # {id session_id  序号:1 / 2    role [提问还是回答] text [user ->原始问题 -> rewritten_query assistant -> 回答 -> text [:60]]
    # rewritten_query item_names => [主体: x,x,x]  image_urls ts} -> item_name识别和问题重写
    history_text = ""
    for index, item in enumerate(final_messages_list, start=1):
        history_text += (
            f"序号：{index}, {'提问' if item.get('role') == 'user' else '回答'}"
            f"问题：{item.get('rewritten_query') if item.get('role') == 'user' else item.get('text')[:60]},"
            f"关联主体：{item.get('item_names')},"
        )
        # 序号：1 提问：woods, 关联主体：[主体: x,x,x],
        # 序号：2 回答：www, 关联主体：[主体: x,x,x],
    return history_text

# 3.调用模型识别item_names和rewritten_query -> json [item_names不一定准 大模型]


@step_log("confirm_item_name")
def call_llm_item_name_and_rewritten(history_text: str, original_query: str) -> dict:
    """
    调用模型识别item_names和rewritten_query
    """
    # 获取模型对象
    llm = llm_provider.chat(json_mode=True)
    # 加载提示词字符串
    from app.shared.runtime.load_prompt import load_prompt
    system_prompt_text: str = load_prompt(
        "rewritten_query_and_itemnames", history_text=history_text,  query=original_query)
    # 封装提示词对象
    from langchain.messages import HumanMessage
    history_prompt_message = [
        HumanMessage(content=system_prompt_text)
    ]
    # 包装chains -> StrOutput... JsonOutput ->
    # 创建chains
    chains = llm | JsonOutputParser()
    # 执行chains
    result_dict = chains.invoke(history_prompt_message)
    # dict = 执行练获取字典   面试题: 怎么确保大语言模型返回的数据是JSON格式!! 1. 提示词强调返回数据格式提供返回数据示例
    #                                                                     2. 模型的json模式设置
    #                                                                     3. 做好返回值的参数校验 JsonOutputParser ``` json  json dict
    #                                                                     4. 返回字典key的校验 item_names -> 无 -> []
    #                                                                                       rewritten_query -> 无 -> original_query
    # 参数校验
    if "item_names" not in result_dict:
        result_dict["item_names"] = []
    if "rewritten_query" not in result_dict:
        result_dict["rewritten_query"] = original_query
    return result_dict


@step_log("search_by_item_names")
def search_by_item_names(item_names: list[str]) -> dict[str, list[dict]]:
    """
       进行向量数据库搜索
    :param item_names:
    :return:
    """
    # 准备一个最终的字典
    final_result = {}
    # 1.循环llm查询到item_names的列表 -> item_name
    # item_names_vector = {dense:[[],[]],sparse:[{},{}]}
    # 先批量生成向量!
    item_names_vector = llm_provider.generate_embeddings(item_names)
    for index in range(0, len(item_names)):
        # 2.获取稠密和稀疏向量
        item_name = item_names[index]
        item_name_dense = item_names_vector['dense'][index]
        item_name_sparse = item_names_vector['sparse'][index]
        # 3.稀疏和稠密向量进行混合检索
        # 3.1 创建annSearchRequest -> 2 -> []
        reqs = milvus_gateway.create_requests(
            item_name_dense, item_name_sparse, limit=5*2)
        # 3.2 创建WeightReranker排序器
        # 3.3 进行混合检索
        #  稠密 满分 1
        #  稀疏 满分 0.6
        #  0.5 0.5  = 0.75 - 0.8      0.73 -> 0.7   0.78  0.75
        results = milvus_gateway.hybrid_search(
            collection_name=milvus_gateway.item_name_collection_name,
            reqs=reqs,  # [1,2]
            ranker_weights=(0.5, 0.5),
            norm_score=True,
            output_fields=['item_name']
        )
        # results = [[{pk:主键,distance:0.9,entity:{item_name:具体的name}},{pk:主键,distance:0.9,entity:{item_name:具体的name}},{pk:主键,distance:0.9,entity:{item_name:具体的name}}]]  保证对称性 单列检索和混合检索的返回结果一致
        # 4.处理混合检索的结果
        item_name_milvus_list = []
        if len(results[0]) > 0:
            for item in results[0]:
                # {pk:主键,distance:0.9,entity:{item_name:具体的name}}
                item_name_milvus_list.append({
                    "item_name": item.get('entity').get('item_name'), "score": item.get('distance')
                })
            # {item_name:分,item_name:分...5个}
        # 5.循环完以后得结果最终返回即可
        final_result[item_name] = item_name_milvus_list
    return final_result


@step_log("select_item_names")
def select_item_names(milvus_result: dict[str, list[dict]]) -> dict[str, list]:
    """
      根据分数,明确确定和可选的item_name列表
    :param milvus_result:
    :return:
    """
    confirmed_list = []
    option_list = []

    # 思路: item_name -> [{item_name:"向量数据库中的item_name",score:0.8},{item_name:"向量数据库中的item_name",score:0.8},{item_name:"向量数据库中的item_name",score:0.8}]
    # 循环处理
    for item_name, mivlus_result_list_dict in milvus_result.items():
        # mivlus_result_list_dict = [{item_name:"向量数据库中的item_name",score:0.9 }, 0.85 0.8 ..]
        # 苹果手机和华为手机哪个好用?
        # 苹果手机 : [{},{},{},{},{},{}]  确认 -> 条件筛选 -> 确认1个 -> 分最高的  可选 -> 可能是.. 0.8 - 0.6 都要 topk 2
        # 华为手机 : [{},{},{},{},{},{}]  确认 -> 条件筛选 -> 确认1个 -> 分最高的  可选 -> 可能是.. 0.8 - 0.6 都要 topk 2
        # [{item_name:"向量数据库中的item_name",score:0.8},..] 数据是已经排好顺序的! 分高 前面!
        # confirmed_list = [] -> 啥样的算确认  [ 稠密向量满分 1 * 0.5 + 稀疏向量满分 0.75 * 0.5 ] = 0.5 + 0.375 = 0.875 -> 0.8 + 确认
        # option_list = [] -> 算可选的 -> 0.6 - 0.8 -> 可选
        high_score_list = [
            item for item in mivlus_result_list_dict if item.get("score", 0) >= 0.70]
        midden_score_list = [
            item for item in mivlus_result_list_dict if 0.6 <= item.get("score", 0) < 0.70]

        if len(high_score_list) > 0:
            confirmed_list.append(high_score_list[0])
            logger.info(
                f"模型识别item_name:{item_name},有对应向量数据库中确认的item_name:{high_score_list[0].get('item_name')}")
            continue

        if len(midden_score_list) > 0:
            option_list.extend(midden_score_list[:2])
            logger.info(
                f"模型识别item_name:{item_name},没有对应向量数据库中确认的item_name,"
                f"但是有可选的:{','.join([item.get('item_name') for item in midden_score_list[:2]])}")
            continue

    return {
        "confirmed_list": confirmed_list,
        "option_list": option_list
    }


@step_log("apply_item_name_result")
def apply_item_name_result(state, list_dict: dict[str, list], rewritten_query: str):
    """
      本次就是为了修改state
         confirmed_list ->  有数据
           item_names = []
           rewritten_query = ""
           一定不能给 answer del ...
           return
         option_list ->confirmed_list没有,  有数据
           item_names 不赋值
           rewritten_query 也无需赋值
           answer = 本次问题没有识别到关联的主体,可能是: 1,2,3,4 请您确认和选择!
           return
         confirmed_list,option_list -> 都没有数据
           item_names 不赋值
           rewritten_query 也无需赋值
           answer = 本次问题没有关联到任何主体,有没有相似可选的主体! 请您明确主体再提问!
           return
    :param state:
    :param list_dict:
    :param rewritten_query:
    :return:
    """
    # [{item_name:xx,score:xxx},]
    confirmed_list = list_dict.get("confirmed_list", [])
    option_list = list_dict.get("option_list", [])

    if len(confirmed_list) > 0:
        state['item_names'] = [item.get('item_name')
                               for item in confirmed_list]
        state['rewritten_query'] = rewritten_query
        if "answer" in state:
            state["answer"] = None
        return

    if len(option_list) > 0:
        # 没有确认,但是有可选的
        # option_list = [[],[]]
        state["answer"] = f"本次提问没有确认主体,但是有相似可选的: {','.join([item.get('item_name') for item in option_list])},请您再次确认!"
        return

    state['answer'] = "本次问题没有关联到任何主体,有没有相似可选的主体! 请您明确主体再提问!"


@step_log("save_history_message")
def save_history_message(state: QueryGraphState):
    history_repository.save_message(
        session_id=state.get("session_id"),
        role="user",  # 用户提问
        text=state.get("original_query"),
        rewritten_query=state.get("rewritten_query", ""),
        item_names=state.get("item_names", []),
        image_urls=[]
    )


@step_log("confirm_item_name")
def confirm_item_name(state: QueryGraphState) -> QueryGraphState:
    """
    意图确认服务：
    1. 结合历史对话提取商品名
    2. 将模糊问题改写为完整独立的精准问题
    3. 在 Milvus 向量库中进行混合搜索
    4. 根据评分高低自动对齐标准型号，或生成反问让用户手动确认
    5. 同步历史记录到 MongoDB
    """
    # 1.获取并且校验参数(state) -> session_id / original_query
    session_id, original_query = get_data_and_validates(state)
    # 2.获取(有效的)历史聊天记录,并且拼接成上下文
    history_text = get_history_messages_and_context(session_id)
    # 3.调用模型识别item_names和rewritten_query -> json [item_names不一定准 大模型]
    result: dict = call_llm_item_name_and_rewritten(
        history_text, original_query)
    if len(result.get("item_names", [])) > 0:
        # 4. 进行向量数据库的搜索 llm - 分析 -> item_names -> milvus中进行查询 -> 打分
        # [1 -> 关联item_name,2 -> item_name,3 ...,4]
        milvus_result: dict[str, list[dict]] = search_by_item_names(
            result.get("item_names", []))
        # 5. 根据打分确定两个列表 确认列表 可选列表
        # 确认列表
        # 可选列表
        # dict{"confirmed_list":[],option_list:[]}
        #   "confirmed_list":confirmed_list,
        #   "option_list":option_list
        list_dict: dict[str, list] = select_item_names(milvus_result)
    # 6. 确定和可选列表修改state answer item_names rewritten_query
    # 修改 state answer item_names rewritten_query list_dict
    apply_item_name_result(state, list_dict, result.get("rewritten_query"))
    # 7. 记录提问的聊天记录
    save_history_message(state)
    return state
