"""
工具模块，负责提供 Neo4j 相关的辅助能力。

【修改】改用 neo4j_config 读取配置，不再直接使用 os.getenv()
"""
import logging
from neo4j import GraphDatabase

from app.shared.config.neo4j_config import neo4j_config

logger = logging.getLogger(__name__)
_neo4j_driver = None


def get_neo4j_driver() -> GraphDatabase:
    """
    获取 Neo4j 驱动实例（单例模式）

    【修改】从 neo4j_config 读取 URI/username/password，
    不再直接使用 os.getenv()
    """
    global _neo4j_driver
    try:
        if _neo4j_driver is None:
            # 【修改】使用配置类读取环境变量
            uri = neo4j_config.uri
            username = neo4j_config.username
            password = neo4j_config.password

            logger.info(f"正在初始化 Neo4j 驱动，连接 URI: {uri}")

            _neo4j_driver = GraphDatabase.driver(
                uri=uri,
                auth=(username, password)
            )
            # Neo4j 驱动默认是懒加载，这行代码能确保如果账号密码错误或网络不通，当场就会抛出异常，而不是等到插入数据时才报错。
            _neo4j_driver.verify_connectivity()

            logger.info("Neo4j 驱动初始化成功并已验证连接！")

        return _neo4j_driver

    except Exception as e:
        # exc_info=True 会在日志中打印出完整的 Error Traceback 堆栈，方便排查到底是密码错还是网络不通
        logger.error(f"初始化 Neo4j 驱动失败: {e}", exc_info=True)
        return None


def get_neo4j_session():
    """
    获取 Neo4j session（便捷方法）。
    自动使用 neo4j_config.database 配置的数据库名。

    【新增】便捷方法，避免业务代码中重复写 driver.session(database=xxx)

    用法：
        with get_neo4j_session() as session:
            session.run("MATCH (n) RETURN n")
    """
    driver = get_neo4j_driver()
    if driver is None:
        raise RuntimeError("Neo4j 驱动获取失败，请检查连接配置")
    return driver.session(database=neo4j_config.database)
