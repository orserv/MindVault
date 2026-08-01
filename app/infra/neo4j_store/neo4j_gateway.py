"""
Neo4j 门面模块，统一封装图数据库客户端与读写操作。

参照 milvus_gateway.py 的设计模式：
    - 封装底层驱动（neo4j_utils）
    - 暴露配置属性（neo4j_config）
    - 提供高层业务方法（session / execute_read / execute_write）
"""
from contextlib import contextmanager
from typing import Any

from app.shared.config.neo4j_config import neo4j_config
from app.shared.clients.neo4j_utils import get_neo4j_driver


class Neo4jGateway:
    """
    Neo4j 统一网关。

    使用方式：
        from app.infra.neo4j_store.neo4j_gateway import neo4j_gateway

        # 获取 session（自动使用配置的 database）
        with neo4j_gateway.session() as session:
            session.run("MATCH (n) RETURN n LIMIT 1")

        # 快捷读操作
        records = neo4j_gateway.execute_read("MATCH (n:Entity) RETURN n")

        # 快捷写操作（事务）
        neo4j_gateway.execute_write(my_tx_func, arg1, arg2)
    """

    @property
    def database(self) -> str:
        """
        获取 Neo4j 数据库名称。
        从 neo4j_config.database 读取（环境变量 NEO4J_DATABASE，默认 "neo4j"）。
        """
        return neo4j_config.database

    @property
    def driver(self):
        """
        获取 Neo4j 驱动实例（单例）。
        底层调用 neo4j_utils.get_neo4j_driver()。
        """
        return get_neo4j_driver()

    @contextmanager
    def session(self, **kwargs):
        """
        获取 Neo4j session 上下文管理器。
        自动使用配置的 database，无需手动指定。

        用法：
            with neo4j_gateway.session() as session:
                session.run(cypher, **params)
        """
        driver = self.driver
        if driver is None:
            raise RuntimeError("Neo4j 驱动获取失败，请检查连接配置")

        kwargs.setdefault("database", self.database)
        session = driver.session(**kwargs)
        try:
            yield session
        finally:
            session.close()

    def execute_read(self, cypher: str, **params) -> list[dict[str, Any]]:
        """
        执行只读 Cypher 查询，返回记录列表。

        :param cypher: Cypher 查询语句
        :param params: 查询参数
        :return: 记录列表 [{"key": value}, ...]
        """
        with self.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    def execute_write(self, func, *args, **kwargs) -> Any:
        """
        在事务中执行写操作。

        :param func: 事务函数，签名为 func(tx, *args, **kwargs)
        :param args: 传递给 func 的位置参数
        :param kwargs: 传递给 func 的关键词参数
        :return: func 的返回值
        """
        with self.session() as session:
            return session.execute_write(func, *args, **kwargs)


# 全局单例，直接导入使用
neo4j_gateway = Neo4jGateway()
