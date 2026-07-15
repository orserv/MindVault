from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from app.process.import_.agent.state import ImportGraphState
from app.process.import_.agent.nodes.node_entry import node_entry
from app.process.import_.agent.nodes.node_pdf_to_md import node_pdf_to_md
from app.process.import_.agent.nodes.node_md_img import node_md_img
from app.process.import_.agent.nodes.node_document_split import node_document_split
from app.process.import_.agent.nodes.node_item_name_recognition import node_item_name_recognition
from app.process.import_.agent.nodes.node_bge_embedding import node_bge_embedding
from app.process.import_.agent.nodes.node_import_milvus import node_import_milvus


from app.shared.runtime.logger import logger

load_dotenv()

# 1. 创建图(工作流)的构建对象，并指定全局state
workflow = StateGraph(ImportGraphState)


# 2. 添加图节点
# workflow.add_node("node_entry", node_entry)
workflow.add_node(node_entry)
workflow.add_node(node_pdf_to_md)
workflow.add_node(node_md_img)
workflow.add_node(node_document_split)
workflow.add_node(node_item_name_recognition)
workflow.add_node(node_bge_embedding)
workflow.add_node(node_import_milvus)

# 3. 设置起始节点
# workflow.add_edge(STAR, "node_entry")
workflow.set_entry_point("node_entry")


# 4. 起始节点的条件边设置

def after_entry_node(state: ImportGraphState):
    """
    入口节点后的路由函数： 

        判断文件类型 is_md_read_enabled 是否为 True or is_pdf_read_enabled 是否为 True
        :params: state
        :return: 目标节点名称

    - Markdown 文件：直接进入图片处理节点
    - PDF 文件：先进入 PDF 转 Markdown 节点
    - 其他类型：直接结束
    """
    if state.get("is_md_read_enabled", False):
        # Markdown 文件
        # 日志：核心点，交代清楚，有理有据有目标
        logger.info(
            f"传入文件地址： {state.get('local_file_path')}，判断传入的文件是Markdown类型，所以跳转到node_md_img节点")
        return "node_md_img"
    elif state.get("is_pdf_read_enabled", False):
        # PDF 文件
        logger.info(
            f"传入文件地址： {state.get('local_file_path')}，判断传入的文件是Markdown类型，所以跳转到node_pdf_to_md节点")
        return "node_pdf_to_md"
    else:
        # 其他类型
        logger.warning(
            f"传入文件地址： {state.get('local_file_path')}，不支持该文档类型处理，只支持md/pdf格式，请检查文件类型!")
        return END


"""
添加条件边：
  参数1 ：起始节点str节点名
  参数2 ：路由函数state -> 业务逻辑 -> return "节点名称"，"节点名称"
  参数3 ：path_map 字典，显示的配置路由的关系，供静态打印使用    路径到节点名称的映射
"""
workflow.add_conditional_edges(
    "node_entry",
    after_entry_node,
    # 路径到节点名称的一一映射
    {
        "node_md_img": "node_md_img",
        "node_pdf_to_md": "node_pdf_to_md",
        END: END,
    }
)


# 5.设置静态边
workflow.add_edge("node_pdf_to_md", "node_md_img")
workflow.add_edge("node_md_img", "node_document_split")
workflow.add_edge("node_document_split", "node_item_name_recognition")
workflow.add_edge("node_item_name_recognition", "node_bge_embedding")
workflow.add_edge("node_bge_embedding", "node_import_milvus")
workflow.add_edge("node_import_milvus", END)


# 6.编译图/工作流对象
import_app = workflow.compile()
