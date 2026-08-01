import sys

from app.shared.runtime.logger import node_log
# 引入知识图谱检索服务
from app.rag.query.graph_search_service import search_by_graph
from app.shared.utils.task_utils import add_done_task, add_running_task


@node_log("node_search_graph")
def node_search_graph(state):
    """
    节点功能：进行 Neo4j 知识图谱检索

    通过图遍历获取跨切片的结构化关系信息，
    如操作步骤链、工具关联、警告提示等。
    """
    add_running_task(state["session_id"], sys._getframe(
    ).f_code.co_name, state.get("is_stream"))
    graph_chunks = search_by_graph(state)
    add_done_task(state["session_id"], sys._getframe(
    ).f_code.co_name, state.get("is_stream"))
    return {
        "graph_chunks": graph_chunks
    }


if __name__ == "__main__":
    test_state = {
        "session_id": "test_search_graph_001",
        "rewritten_query": "HAK180 烫金机的使用步骤是什么？需要什么工具？",
        "item_names": ["HAK180 烫金机"],
        "is_stream": False,
    }
    result = node_search_graph(test_state)
    print(result)
