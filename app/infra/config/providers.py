from app.shared.config.embedding_config import embedding_config, EmbeddingConfig
from app.shared.config.lm_config import lm_config, LLMConfig
from app.shared.config.bailian_mcp_config import mcp_config, McpConfig
from app.shared.config.milvus_config import milvus_config, MilvusConfig
from app.shared.config.mineru_config import mineru_config, MinerUConfig
from app.shared.config.minio_config import minio_config, MinIOConfig
from app.shared.config.reranker_config import reranker_config, RerankerConfig
from app.shared.config.settings_config import settings, AppSettings
# 【新增】Neo4j 配置
from app.shared.config.neo4j_config import neo4j_config, Neo4jConfig

from dataclasses import dataclass, field

# 创建一个类 赋值对应的config 对象, 导入当前一个类即可获取所有的config对象
# 装饰器的目的是


@dataclass
class InfraConfig:
    """
    提供者配置。
    """
    # 属性名：类型 object = 默认值
    embedding_config: EmbeddingConfig = field(
        default_factory=lambda: embedding_config)  # 复制一个对象
    # lm_config: LLMConfig = field(default=lm_config) 等同于 lm_config: LLMConfig = lm_config 一般字符串这类才用default,但是实际上可以直接给字符串赋值。如：sss_config: str = "sss"
    lm_config: LLMConfig = field(default_factory=lambda: lm_config)
    mcp_config: McpConfig = field(default_factory=lambda: mcp_config)
    milvus_config: MilvusConfig = field(default_factory=lambda: milvus_config)
    mineru_config: MinerUConfig = field(default_factory=lambda: mineru_config)
    minio_config: MinIOConfig = field(default_factory=lambda: minio_config)
    reranker_config: RerankerConfig = field(
        default_factory=lambda: reranker_config)
    settings_config: AppSettings = field(default_factory=lambda: settings)
    # 【新增】Neo4j 配置
    neo4j_config: Neo4jConfig = field(default_factory=lambda: neo4j_config)


"""
InfraConfig -> 属性 = 默认值 -> 另外的一个模块中的对象 embedding_config
InfraConfig -> embedding_config -> 对象
                                        每个模块不同的类型指向同一个对象 地址引用
embedding_config -> embedding_config -> 对象

修改：
embedding_config -> 对象| {} [] （因为它们也是指向一个地址） ->  field(default_factory=lambda: embedding_config)   # 复制一个对象
                  -> str bool 数字 () -> 可以直接赋值
"""

infra_config = InfraConfig()

if __name__ == "__main__":
    print(infra_config.lm_config.api_key)
    print(infra_config.settings_config.import_app_name)
    print(infra_config.mineru_config.base_url)
    print(infra_config.mineru_config.api_key)
    # 【新增】测试 Neo4j 配置
    print(infra_config.neo4j_config.uri)
    print(infra_config.neo4j_config.database)


#  python -m app.infra.config.providers
