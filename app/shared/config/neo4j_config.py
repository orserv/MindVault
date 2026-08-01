"""
Neo4j 配置模块，负责读取图数据库相关环境变量。
"""
from dataclasses import dataclass

from app.shared.config.common import env_str


@dataclass
class Neo4jConfig:
    uri: str
    username: str
    password: str
    database: str


neo4j_config = Neo4jConfig(
    uri=env_str("NEO4J_URI"),
    username=env_str("NEO4J_USERNAME"),
    password=env_str("NEO4J_PASSWORD"),
    database=env_str("NEO4J_DATABASE", "neo4j"),
)
