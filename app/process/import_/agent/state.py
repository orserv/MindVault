
from typing import TypedDict
import copy
from app.shared.runtime.logger import logger


class ImportGraphState(TypedDict):
    """
    图的状态定义，包含所有节点产生和消费的数据字段。
    TypedDict 让我们在代码中能有自动补全和类型检查。
    使用字典式访问（如 state["task_id"]、state.get("chunks")）。
    """

    # ==================== 任务标识 ====================
    task_id: str  # 任务 ID，用于任务追踪(web交互的时候用到，实时看到节点的处理日志)
    # ==================== 流程控制标志 ====================
    is_md_read_enabled: bool  # 是否启用 MD 读取
    is_pdf_read_enabled: bool  # 是否启用 PDF 读取
    # ==================== 路径信息 ====================
    local_file_dir: str  # 导入(出)文件目录  文件夹地址  (pdf -> md  -> 输出的文件夹地址)
    local_file_path: str  # 导入的文件路径 传入文件地址 不确定md pdf
    pdf_path: str  # PDF 文件路径  pdf地址 文件 <- local_file_path
    md_path: str  # 转换后Markdown 文件路径 md地址 文件 <- local_file_path
    # ==================== 文件信息 ====================
    file_title: str  # 文件标题（不含扩展名）
    item_name: str  # 识别出的主体/产品名称(方便程序员用)
    # ==================== 处理中间数据 ====================
    md_content: str  # Markdown 文档内容
    chunks: list  # 文档切片列表
    # ==================== 数据库相关 ====================
    embeddings_content: list  # 带有向量的切块


# 准备一个state对象
graph_default_state: ImportGraphState = {
    "task_id": "",
    "is_pdf_read_enabled": False,
    "is_md_read_enabled": False,
    "local_file_dir": "",
    "import_file_path": "",
    "pdf_path": "",
    "md_path": "",
    "file_title": "",
    "md_content": "",
    "chunks": [],
    "item_name": "",
    "embedding_content": [],
}

# 定义一个可以更新对象属性的函数，并返回更新后的状态对象


def create_default_state(**kwargs) -> ImportGraphState:
    """
    创建一个对象，更新指定属性 形参列表中指定要更新的属性
    :param kwargs: 形参列表中指定要更新的属性
    :return: 更新后的状态对象

    **kwargs = local_file_path = value -> dict {local_file_path: key}
     赋值对象内容 进行复制（copy）内容更新
     深拷贝：不仅拷贝第一层属性，也会拷贝嵌套属性  新的 = copy.deepcopy(old对象)
     浅拷贝：只拷贝第一层属性，嵌套属性依然共享  新的 = copy.copy(old对象)  | dict.copy()
    """
    new_copy = copy.deepcopy(graph_default_state)
    # default_state 全局唯一的对象，多次更新，值进行共享
    new_copy.update(kwargs)
    return new_copy


def get_default_state() -> ImportGraphState:
    """
    返回一个新的状态实例，避免全局变量污染。
    """
    return copy.deepcopy(graph_default_state)


if __name__ == '__main__':
    # 测试：传入参数渲染占位符（和业务代码中实际使用方式一致）
    # root_folder = "hl3070使用说明书"  # 要替换的文件名称
    # image_content = ("这是图片的上文内容", "这是图片的下文内容")  # 要替换的上下文
    # # 调用时传入所有需要渲染的变量（键名必须和.prompt中的占位符完全一致）
    state = create_default_state(
        task_id="123舟", local_file_path="xx/xx/123.txt")
    # json数据转换和备份
    # json.dump  dumps   ：dict -> json    dump是写到外部的.json格式的文件，dumps是把dict转成json字符串
    # 不带s的都是文件
    # json.load  loads   ：json -> dict    load是加载外部的json文件然后转为dict，loads是json字符串转为dict
    import json
    print(state)
    print(type(state))
    logger.info("✅ 本次生成的state：\n{}", json.dumps(
        state, indent=4, ensure_ascii=False))
    # {'task_id': '123舟', 'local_file_path': 'xx/xx/123.txt'}转换为{"task_id": "123", "local_file_path": "xx/xx/123.txt"}


# python -m app.process.import_.agent.state
