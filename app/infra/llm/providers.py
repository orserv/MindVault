from langchain_openai import ChatOpenAI

from app.infra.config.providers import infra_config
from app.shared.model.lm_utils import get_llm_client
from app.shared.model.embedding_utils import get_bge_m3_ef, generate_embeddings
from app.shared.model.reranker_utils import get_reranker_model


class LLMProvider:
    """
    LLM 模型统一网关（提供器）
    作用：封装所有大模型调用入口，统一管理普通对话、视觉模型、向量模型等
    外部业务只需要调用 llm_provider 就能获取各种模型，不用关心底层配置
    """

    # 获取普通大语言模型
    # def chat(self,json_mode:bool):
    #     """
    #       我们创建固定的语言模型 -> .env中决定! 全局只有一种类型!
    #       我们可以在创建的时候传入json模式参数!!
    #     :param json_mode:
    #     :return:
    #     """

   # 获取普通大语言模型
    def chat(self, model: str | None = None, json_mode: bool = False) -> ChatOpenAI:
        """
        获取【普通文本对话】LLM 客户端
        :param model: 可选，指定模型名称，不填则使用默认配置
        :param json_mode: 是否开启 JSON 格式输出模式
        :return: 可直接调用的 LangChain LLM 客户端

        允许传递模型的名称,不传入使用默认 .env > 默认参数
        可以在创建的时候传入json模式参数!!
        可以在一个项目使用不同的大语言模型
        """
        return get_llm_client(model=model, json_mode=json_mode)

    def vision_chat(self, vision_mode_name: str = None) -> ChatOpenAI:
        """
        获取【视觉对话】LLM 客户端（用于图片理解、图片摘要、多模态理解）
        默认使用配置中的 lv_model（视觉大模型）
        :return: 视觉模型客户端
        """
        return get_llm_client(vision_mode_name or infra_config.lm_config.lv_model)

    # 获取嵌入模型
    def bge_m3_embedding(self):
        return get_bge_m3_ef()

    # 生成向量
    def generate_embeddings(self, texts: list[str]) -> dict[str, list]:
        return generate_embeddings(texts)

    # 重排序模型
    def reranker_model(self):
        return get_reranker_model()


# 创建全局唯一的 LLM 提供器实例，全项目通用，避免重复创建
llm_provider = LLMProvider()
