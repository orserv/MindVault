# MinerU 模型版本配置（vlm = 视觉语言模型，适合PDF/图片高精度解析）
MINERU_MODEL_VERSION = "vlm"

# MinerU 任务轮询最大超时时间（单位：秒），超过则判定任务失败
# 600 -> 一个pdf 约等于 1秒
MINERU_POLL_TIMEOUT_SECONDS = 600

# MinerU 任务轮询间隔时间（单位：秒），每隔多久查询一次任务状态
MINERU_POLL_INTERVAL_SECONDS = 3

# MinerU 文件下载超时时间（单位：秒），下载文件超过此时长则中断
MINERU_DOWNLOAD_TIMEOUT_SECONDS = 30

# 定义local_file_dir对应输出的常量
PDF_PARSE_SERVICE_LOCAL_DIR = "output"

# 允许的图片文件扩展名
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

# 文本切块最大长度：单个文本块最多包含 1000 字符（防止过长导致向量失真）
CHUNK_MAX_SIZE = 1000
# 文本切块基准长度：单个文本块理想大小为 600 字符（兼顾语义完整性 + 检索精度）
CHUNK_SIZE = 600
# 文本块重叠长度：相邻块之间重叠 20 字符，保证语义不被切断、上下文连贯
CHUNK_OVERLAP = 50
# 最小碎片阈值：低于这个长度判定为短碎片，需要尝试合并
CHUNK_MIN_SIZE = 400


# 声明切块的截取数量，默认为10
CHUNKS_SPLIT_TOP_NUMBER = 10


# 向量化批次大小：每批处理 6 条切片，避免显存溢出
EMBEDDING_BATCH_SIZE = 6


# neo4j 配置
# 关系类型白名单：只允许这些关系类型写入 Neo4j
ALLOWED_RELATION_TYPES = {
    "HAS_OPERATION", "HAS_PART", "HAS_STEP", "USES_TOOL",
    "HAS_WARNING", "NEXT_STEP", "AFFECTS", "REQUIRES",
    "MENTIONED_IN", "RELATED_TO",
}

# Neo4j Cypher 语句 —— 创建/合并 Chunk 节点
CYPHER_MERGE_CHUNK = """
    MERGE (c:Chunk {id: $chunk_id, item_name: $item_name})
"""

# Neo4j Cypher 语句 —— 创建/合并 Entity 节点
CYPHER_MERGE_ENTITY = """
    MERGE (n:Entity {name: $name, item_name: $item_name})
    ON CREATE SET
        n.source_chunk_id = $chunk_id,
        n.description     = $description,
        n.types           = CASE
                                WHEN $label = "" THEN []
                                ELSE [$label]
                            END
    ON MATCH SET
        n.description = CASE
                            WHEN $description <> "" THEN $description
                            ELSE coalesce(n.description, "")
                        END,
        n.types       = CASE
                            WHEN $label = ""                       THEN coalesce(n.types, [])
                            WHEN $label IN coalesce(n.types, [])   THEN n.types
                            ELSE coalesce(n.types, []) + $label
                        END
"""

# Neo4j Cypher 语句 —— 建立 Entity 到 Chunk 的关联
CYPHER_LINK_ENTITY_TO_CHUNK = """
    MATCH (n:Entity {name: $name, item_name: $item_name})
    MATCH (c:Chunk  {id: $chunk_id, item_name: $item_name})
    MERGE (n)-[:MENTIONED_IN]->(c)
"""

# Neo4j Cypher 语句 —— 创建/合并关系（模板，动态填充 rel_type）
CYPHER_MERGE_RELATION_TEMPLATE = """
    MATCH (h:Entity {{name: $head, item_name: $item_name}})
    MATCH (t:Entity {{name: $tail, item_name: $item_name}})
    MERGE (h)-[:{rel_type}]->(t)
"""
