from app.process.import_.agent.state import ImportGraphState
from app.shared.runtime.logger import logger, step_log
from pathlib import Path


@step_log("入口识别:resolve_input_file")
def resolve_input_file(state: ImportGraphState) -> ImportGraphState:
    """
    # 入口识别服务：
    # 1. 校验 local_file_path
    # 2. 识别文件类型（PDF / Markdown）
    # 3. 回写 is_pdf_read_enabled / is_md_read_enabled
    # 4. 回写 pdf_path / md_path / file_title
    进行文件校验分发的任务
    :param state:
    :return:
    """
    # 1. 先获取 local_file_path参数 state
    local_file_path = state.get("local_file_path")
    # 2. local_file_path进行非空校验 -> 空 -> 直接抛出异常 FileNotFound....
    if not local_file_path:  # 获取文件路径
        logger.error("local_file_path参数为空,无法继续业务，提前终止")
        raise FileNotFoundError("local_file_path参数为空,无法继续业务，提前终止")
    # 3. 判断是不是md -> md_path is_md_read_enabled is_pdf_read_enabled = False
    if local_file_path.endswith(".md"):  # 判断是不是md
        state["is_md_read_enabled"] = True
        state["is_pdf_read_enabled"] = False
        state["pdf_path"] = local_file_path
    # 4. 判断是不是pdf -> is_md_read_enabled = False pdf_path  is_pdf_read_enabled
    elif local_file_path.endswith(".pdf"):  # 判断是不是pdf
        state["is_pdf_read_enabled"] = True
        state["pdf_path"] = local_file_path
        state["is_md_read_enabled"] = False
    # 后续扩展文件名类型支持，在这里添加elif判断继续写即可。
    # elif local_file_path.endswith(".txt"):
    # 5. 都不是做好警告提示 is_md_read_enabled  pdf_path  is_pdf_read_enabled = False 提前结束
    else:
        logger.warning(
            f"{local_file_path}不支持的文件类型,仅支持md/pdf格式的文件,提前终止，跳转到END节点")
        state["is_md_read_enabled"] = False
        state["is_pdf_read_enabled"] = False
        return state
    # 6. 获取file_title参数 同步更新state
    # d:/xxx/xxx.md  xxx.pdf
    # 获取文件名 xxx.md xxx.pdf
    # local_file_path.split("/")[-1]
    # Path   获取当前路径地址   属性：.name ：文件名（带后缀）  .stem：文件名（无后缀）  .suffix ：后缀 .parent ：上一层文件夹 .parents 父文件夹列表
    #                          函数： read_text() 读取文件内容   read_bytes() 读取文件字节   write_text() 写入文件内容
    state["file_title"] = Path(local_file_path).stem
    # 7. 返回处理后的state
    return state
