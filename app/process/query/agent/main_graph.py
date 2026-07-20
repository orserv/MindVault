from langgraph.graph import StateGraph, END

from app.process.query.agent.nodes.node_item_name_confirm import node_item_name_confirm
from app.process.query.agent.nodes.node_search_embedding import node_search_embedding
from app.process.query.agent.nodes.node_search_embedding_hyde import node_search_embedding_hyde
from app.process.query.agent.nodes.node_web_search_mcp import node_web_search_mcp
from app.process.query.agent.nodes.node_rrf import node_rrf
from app.process.query.agent.nodes.node_rerank import node_rerank
from app.process.query.agent.nodes.node_answer_output import node_answer_output
from app.process.query.agent.state import QueryGraphState
from app.shared.runtime.logger import logger

# 1. 定义状态图对象，并且指定全局的 state
query_graph = StateGraph(QueryGraphState)

# 2. 添加节点信息
query_graph.add_node("node_item_name_confirm", node_item_name_confirm)
query_graph.add_node("node_search_embedding", node_search_embedding)
query_graph.add_node("node_search_embedding_hyde", node_search_embedding_hyde)
query_graph.add_node("node_web_search_mcp", node_web_search_mcp)
query_graph.add_node("node_rrf", node_rrf)
query_graph.add_node("node_rerank", node_rerank)
query_graph.add_node("node_answer_output", node_answer_output)

# 3. 指定入口节点（有条件边）
query_graph.set_entry_point("node_item_name_confirm")

# 4. 指定条件边，动态边
# 路由函数


def node_item_name_confirm_after_router(state: QueryGraphState):
    """
       方法一:判断item_names有 [明确]或者 没有 [可选 | 不确定]
       方法二：判断answer 没有 [明确] 或者 有 [可选 | 不确定]
    :param state:
    :return:
    """
    if not state.get("answer"):
        # 有item_names => 确定item_names 可以继续多路召回
        logger.info(f"本次问题有确定的item_names:{state.get('item_names')},正常进入多路召回~")
        return "node_search_embedding", "node_search_embedding_hyde", "node_web_search_mcp"
    else:
        logger.info(
            f"本次问题没有确定的item_names:{state.get('item_names')},跳到回答node_answer_output节点~")
        return "node_answer_output"


query_graph.add_conditional_edges("node_item_name_confirm", node_item_name_confirm_after_router, {
    "node_search_embedding": "node_search_embedding",
    "node_search_embedding_hyde": "node_search_embedding_hyde",
    "node_web_search_mcp": "node_web_search_mcp",
    "node_answer_output": "node_answer_output"
})

# 5. 指定静态边
query_graph.add_edge("node_search_embedding", "node_rrf")
query_graph.add_edge("node_search_embedding_hyde", "node_rrf")
query_graph.add_edge("node_web_search_mcp", "node_rrf")
query_graph.add_edge("node_rrf", "node_rerank")
query_graph.add_edge("node_rerank", "node_answer_output")
query_graph.add_edge("node_answer_output", END)

# 6. 编译对象即可
query_app = query_graph.compile()
