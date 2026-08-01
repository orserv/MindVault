from langgraph.graph import StateGraph, END

from app.process.query.agent.nodes.node_item_name_confirm import node_item_name_confirm
from app.process.query.agent.nodes.node_search_embedding import node_search_embedding
from app.process.query.agent.nodes.node_search_embedding_hyde import node_search_embedding_hyde
from app.process.query.agent.nodes.node_web_search_mcp import node_web_search_mcp
from app.process.query.agent.nodes.node_search_graph import node_search_graph  # 【新增】图检索节点
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
query_graph.add_node("node_search_graph", node_search_graph)  # 【新增】图检索节点
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
        logger.info(
            f"本次问题有确定的item_names:{state.get('item_names')},正常进入多路召回(含图检索)~")
        # 【修改】新增 node_search_graph 作为第4路并行检索
        return "node_search_embedding", "node_search_embedding_hyde", "node_web_search_mcp", "node_search_graph"
    else:
        logger.info(
            f"本次问题没有确定的item_names:{state.get('item_names')},跳到回答node_answer_output节点~")
        return "node_answer_output"


query_graph.add_conditional_edges("node_item_name_confirm", node_item_name_confirm_after_router, {
    "node_search_embedding": "node_search_embedding",
    "node_search_embedding_hyde": "node_search_embedding_hyde",
    "node_web_search_mcp": "node_web_search_mcp",
    "node_search_graph": "node_search_graph",  # 【新增】图检索路由
    "node_answer_output": "node_answer_output"
})

# 5. 指定静态边
query_graph.add_edge("node_search_embedding", "node_rrf")
query_graph.add_edge("node_search_embedding_hyde", "node_rrf")
query_graph.add_edge("node_web_search_mcp", "node_rrf")
query_graph.add_edge("node_search_graph", "node_rrf")  # 【新增】图检索汇入 RRF
query_graph.add_edge("node_rrf", "node_rerank")
query_graph.add_edge("node_rerank", "node_answer_output")
query_graph.add_edge("node_answer_output", END)

# 6. 编译对象即可
query_app = query_graph.compile()

if __name__ == "__main__":
    from dotenv import load_dotenv
    from app.process.query.agent.state import create_query_default_state

    load_dotenv()

    print("=" * 60)
    print("开始测试: 完整 Query 图 (含图检索)")
    print("=" * 60)

    # 构造初始状态，只需提供最小必要字段
    # 其余字段由 create_query_default_state 自动填充默认值
    mock_state = create_query_default_state(
        session_id="test_session_001",
        # original_query="HAK 180烫金机的手柄怎么拆卸？",
        original_query="Multi-Head Attention在Transformer中，其作用是什么？",
        is_stream=False,
    )

    print(f"【输入】: {mock_state['original_query']}")
    print("-" * 60)

    # stream 返回生成器，每个 yield 是一个节点的输出
    final_state = {}
    for event in query_app.stream(mock_state):
        # event 格式: {"node_name": {partial_state_update}}
        for node_name, node_output in event.items():
            print(f"\n✓ 节点 [{node_name}] 执行完成")
            # 打印关键输出摘要
            if "item_names" in node_output:
                print(f"  item_names: {node_output['item_names']}")
            if "rewritten_query" in node_output:
                print(f"  rewritten_query: {node_output['rewritten_query']}")
            if "embedding_chunks" in node_output:
                print(
                    f"  embedding_chunks: {len(node_output['embedding_chunks'])} 条")
            if "hyde_embedding_chunks" in node_output:
                print(
                    f"  hyde_chunks: {len(node_output['hyde_embedding_chunks'])} 条")
            if "web_search_docs" in node_output:
                print(
                    f"  web_search_docs: {len(node_output['web_search_docs'])} 条")
            if "graph_chunks" in node_output:
                print(f"  graph_chunks: {len(node_output['graph_chunks'])} 条")
            if "rrf_chunks" in node_output:
                print(f"  rrf_chunks: {len(node_output['rrf_chunks'])} 条")
            if "reranked_docs" in node_output:
                print(
                    f"  reranked_docs: {len(node_output['reranked_docs'])} 条")
            if "answer" in node_output:
                ans = node_output["answer"] or ""
                print(f"  answer: {ans[:200]}..." if len(
                    ans) > 200 else f"  answer: {ans or '（无答案）'}")
            # 累积到 final_state
            final_state.update(node_output)

    print("\n" + "=" * 60)
    print("【最终答案】:")
    print("-" * 60)
    final_answer = final_state.get("answer") or "（无答案）"
    print(final_answer)
    print("-" * 60)
    print("\n测试完成")
