"""
知识图谱构建业务逻辑模块

代码结构：
    1. 数据获取与校验 (get_data_and_validates)
    2. LLM 实体关系提取 (llm_extract_entities_relations)
    3. JSON 解析与清洗 (parse_and_clean_graph_data)
    4. Milvus 实体向量写入 (save_entities_to_milvus)
    5. Neo4j 图数据写入 (save_graph_to_neo4j)
    6. 主入口 (build_knowledge_graph)

整体流程：
    chunks → LLM 提取 → JSON 清洗 → Milvus 写入 → Neo4j 写入
"""

import json
import re
from typing import Any
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from pymilvus import DataType

from app.process.import_.agent.state import ImportGraphState
from app.shared.runtime.logger import logger, step_log
from app.shared.runtime.load_prompt import load_prompt
from app.infra.llm.providers import llm_provider
from app.infra.config.providers import infra_config
from app.infra.vector_store.milvus_gateway import milvus_gateway
from app.infra.neo4j_store.neo4j_gateway import neo4j_gateway
from app.rag.import_.config import ALLOWED_RELATION_TYPES, CYPHER_MERGE_CHUNK, CYPHER_MERGE_ENTITY, CYPHER_LINK_ENTITY_TO_CHUNK, CYPHER_MERGE_RELATION_TEMPLATE


#  1. 数据获取与校验
@step_log("get_chunks_for_kg")
def get_chunks_for_kg(state: ImportGraphState) -> tuple[list[dict[str, Any]], str]:
    """
    从 state 中获取切片数据和主体名称，并进行校验。
    如果 chunks 为空，尝试从 md_path 对应的 JSON 文件读取备份。

    :param state: LangGraph 流程状态字典
    :return: (chunks列表, item_name字符串)
    """
    # 1. 从 state 获取关键参数
    md_path = state.get("md_path")
    item_name = state.get("item_name")
    chunks = state.get("chunks")

    # 2. 校验 item_name：如果为空，从 md_path 提取文件名作为默认值
    if not item_name:
        if md_path and Path(md_path).exists():
            item_name = Path(md_path).stem
        else:
            item_name = "default_item_name"
        logger.warning(f"item_name 没有值，给予默认值: {item_name}")

    # 3. 校验 chunks：如果为空，尝试从本地 JSON 备份文件读取
    if not chunks:
        if md_path:
            chunks_json_obj: Path = Path(md_path).with_name(
                f"{Path(md_path).stem}.json")
            if chunks_json_obj.exists():
                chunks = json.loads(
                    chunks_json_obj.read_text(encoding="utf-8"))
        if not chunks:
            logger.error("chunks 为空，读取本地备份文件依然为空，知识图谱构建无法继续！")
            raise ValueError("chunks 为空，读取本地备份文件依然为空，知识图谱构建无法继续！")

    return chunks, item_name


#  2. LLM 实体关系提取
@step_log("llm_extract_entities_relations")
def llm_extract_entities_relations(content: str) -> str:
    """
    调用 LLM 从文本切片中提取实体和关系。

    :param content: 文本切片内容
    :return: LLM 返回的原始 JSON 字符串
    """
    try:
        # 加载提示词（从 knowledge_graph.prompt 文件读取）
        system_prompt_text = load_prompt("knowledge_graph")

        # 构建消息列表
        messages = [
            SystemMessage(content=system_prompt_text),
            HumanMessage(content=f"请处理以下文本切片：\n\n{content}"),
        ]

        # 调用 LLM
        chain = llm_provider.chat(json_mode=True) | StrOutputParser()
        response = chain.invoke(messages)

        return (response or "").strip()

    except Exception as e:
        logger.warning(f"LLM 提取实体关系失败: {e}")
        return ""


# 3. JSON 解析与清洗
@step_log("parse_and_clean_graph_data")
def parse_and_clean_graph_data(raw_text: str) -> dict[str, Any]:
    """
    解析 LLM 返回的 JSON 字符串，并对实体和关系进行清洗。

    清洗步骤：
        - 去除 Markdown 代码围栏
        - JSON 解析
        - 实体清洗：过滤无效项、截断过长名称、去重
        - 关系清洗：字段修正、白名单校验、过滤悬空引用

    :param raw_text: LLM 返回的原始文本
    :return: 清洗后的图数据 {"entities": [...], "relations": [...]}
    """
    if not raw_text:
        return {"entities": [], "relations": []}

    # 去除 Markdown 代码围栏（```json ... ```）
    cleaned_text = re.sub(r"^```(?:json)?\s*", "", raw_text.strip())
    cleaned_text = re.sub(r"\s*```$", "", cleaned_text)

    # JSON 解析
    try:
        data = json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON 解析失败: {e}, 原文前200字: {raw_text[:200]}")
        return {"entities": [], "relations": []}

    # 清洗实体
    cleaned_entities = _clean_entities(data.get("entities", []))
    # 清洗关系（需要有效实体名称集合，用于过滤悬空引用）
    valid_names = {e["name"] for e in cleaned_entities}
    cleaned_relations = _clean_relations(
        data.get("relations", []), valid_names)

    return {"entities": cleaned_entities, "relations": cleaned_relations}


def _clean_entities(entities: list[dict]) -> list[dict]:
    """
    清洗实体列表。

    清洗规则：
        - 过滤 name 或 label 为空的实体
        - 截断过长的 name（超过20字）
        - 按 (name, label) 去重

    :param entities: 原始实体列表
    :return: 清洗后的实体列表
    """
    seen: set[tuple] = set()
    cleaned: list[dict] = []

    for entity in entities:
        name = str(entity.get("name", "")).strip()
        label = str(entity.get("label", "")).strip()
        description = str(entity.get("description", "")).strip()

        # 跳过无效实体
        if not name or not label:
            continue

        # 去重
        dedup_key = (name, label)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        # 构建清洗后的实体
        result = {"name": name, "label": label}
        if description:
            result["description"] = description
        cleaned.append(result)

    return cleaned


def _clean_relations(relations: list[dict], valid_entity_names: set[str]) -> list[dict]:
    """
    清洗关系列表。

    清洗规则：
        - 过滤 head 或 tail 为空的关系
        - 关系类型白名单校验，不在白名单内的统一改为 RELATED_TO
        - 过滤悬空引用（head 或 tail 不在有效实体集合中）

    :param relations: 原始关系列表
    :param valid_entity_names: 有效的实体名称集合
    :return: 清洗后的关系列表
    """
    cleaned: list[dict] = []

    for rel in relations:
        head = str(rel.get("head", "")).strip()
        tail = str(rel.get("tail", "")).strip()

        # 跳过空值
        if not head or not tail:
            continue

        # 关系类型校验（兼容 type/label 两种字段名）
        rel_type = str(rel.get("type") or rel.get(
            "label") or "RELATED_TO").strip()
        if rel_type not in ALLOWED_RELATION_TYPES:
            rel_type = "RELATED_TO"

        # 过滤悬空引用
        if head not in valid_entity_names or tail not in valid_entity_names:
            logger.debug(f"悬空关系已跳过: {head} -[{rel_type}]-> {tail}")
            continue

        cleaned.append({"head": head, "tail": tail, "type": rel_type})

    return cleaned


#  4. Milvus 实体向量写入
@step_log("save_entities_to_milvus")
def save_entities_to_milvus(entities: list[dict], chunk_id: str, content: str, item_name: str) -> None:
    """
    将实体向量化并写入 Milvus（稠密 + 稀疏双向量）。

    流程：
        1. 实体按 name 去重
        2. 使用 BGE-M3 生成向量
        3. 确保 Milvus 集合存在
        4. 批量插入

    :param entities: 实体列表
    :param chunk_id: 所属切片 ID
    :param content: 原始文本内容
    :param item_name: 主体名称
    """
    collection_name = infra_config.milvus_config.entity_name_collection
    if not entities or not collection_name:
        return

    # 按 name 去重
    dedup_map = _dedup_entities_by_name(entities)
    if not dedup_map:
        return

    try:
        # 获取实体名称列表
        names = list(dedup_map.keys())

        # 生成向量（稠密 + 稀疏）
        vectors = llm_provider.generate_embeddings(names)

        # 获取 Milvus 客户端
        client = milvus_gateway.milvus_client
        if client is None:
            logger.error("Milvus 客户端连接失败，无法写入实体")
            return

        # 确保集合存在
        _ensure_entity_collection(client, collection_name)

        # 组装 Milvus 插入记录
        insert_data = _build_milvus_records(
            names, vectors, chunk_id, content, item_name)

        # 批量插入
        if insert_data:
            client.insert(collection_name=collection_name, data=insert_data)
            client.load_collection(collection_name=collection_name)
            logger.debug(
                f"写入 {len(insert_data)} 个实体到 Milvus 集合 [{collection_name}]")

    except Exception as e:
        logger.warning(f"Milvus 实体写入失败: {e}")


def _dedup_entities_by_name(entities: list[dict]) -> dict[str, dict]:
    """
    按 name 去重实体，合并同名不同类型的 label。

    :param entities: 实体列表
    :return: {name: {"labels": set, "description": str}}
    """
    dedup: dict[str, dict] = {}
    for entity in entities:
        name = str(entity.get("name", "")).strip()
        if not name:
            continue
        label = str(entity.get("label", "")).strip()
        description = str(entity.get("description", "")).strip()

        if name not in dedup:
            dedup[name] = {"labels": set(), "description": description}
        if label:
            dedup[name]["labels"].add(label)
    return dedup


def _ensure_entity_collection(client, collection_name: str) -> None:
    """
    确保 Milvus 实体集合存在，不存在则创建完整的 schema 和索引。

    Schema 字段：
        - pk: 主键，INT64，自增
        - entity_name: 实体名称，VARCHAR
        - dense_vector: 稠密向量，FLOAT_VECTOR (dim=1024)
        - sparse_vector: 稀疏向量，SPARSE_FLOAT_VECTOR
        - source_chunk_id: 来源切片 ID
        - context: 上下文内容
        - item_name: 主体名称

    :param client: Milvus 客户端实例
    :param collection_name: 集合名称
    """
    if client.has_collection(collection_name):
        return

    # 创建 schema
    schema = client.create_schema(enable_dynamic_field=True)
    schema.add_field(field_name="pk",              datatype=DataType.INT64,
                     is_primary=True, auto_id=True)
    schema.add_field(field_name="entity_name",     datatype=DataType.VARCHAR,
                     max_length=65535)
    schema.add_field(field_name="dense_vector",    datatype=DataType.FLOAT_VECTOR,
                     dim=1024)
    schema.add_field(field_name="sparse_vector",
                     datatype=DataType.SPARSE_FLOAT_VECTOR)
    schema.add_field(field_name="source_chunk_id", datatype=DataType.VARCHAR,
                     max_length=65535)
    schema.add_field(field_name="context",         datatype=DataType.VARCHAR,
                     max_length=65535)
    schema.add_field(field_name="item_name",       datatype=DataType.VARCHAR,
                     max_length=65535)

    # 创建索引
    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="dense_vector",
        index_name="dense_vector_index",
        index_type="IVF_FLAT",
        metric_type="COSINE",
        params={"nlist": 128},
    )
    index_params.add_index(
        field_name="sparse_vector",
        index_name="sparse_vector_index",
        index_type="SPARSE_INVERTED_INDEX",
        metric_type="IP",
    )

    # 创建集合
    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=index_params,
    )
    logger.info(f"Milvus 实体集合 [{collection_name}] 创建成功")


def _build_milvus_records(
    names: list[str],
    vectors: dict[str, list],
    chunk_id: str,
    content: str,
    item_name: str,
) -> list[dict]:
    """
    组装 Milvus 插入记录（稠密 + 稀疏双向量）。

    :param names: 实体名称列表
    :param vectors: 向量字典 {"dense": [...], "sparse": [...]}
    :param chunk_id: 来源切片 ID
    :param content: 原始文本内容
    :param item_name: 主体名称
    :return: Milvus 插入记录列表
    """
    dense_list = vectors.get("dense", [])
    sparse_list = vectors.get("sparse", [])

    records = []
    for idx, name in enumerate(names):
        if idx >= len(dense_list):
            break

        record = {
            "entity_name": name,
            "dense_vector": dense_list[idx],
            "source_chunk_id": chunk_id,
            "context": content[:200],  # 截断过长内容
            "item_name": item_name,
        }

        # 添加稀疏向量（如果存在）
        if idx < len(sparse_list):
            record["sparse_vector"] = sparse_list[idx]

        records.append(record)

    return records


# ====================================================================== #
#                    5. Neo4j 图数据写入                                   #
# ====================================================================== #

@step_log("save_graph_to_neo4j")
def save_graph_to_neo4j(
    graph_data: dict[str, Any],
    chunk_id: str,
    item_name: str,
) -> None:
    """
    将图数据（实体 + 关系）写入 Neo4j。

    流程：
        1. 获取 Neo4j 驱动
        2. 在单个事务内完成所有写入

    :param graph_data: 图数据 {"entities": [...], "relations": [...]}
    :param chunk_id: 所属切片 ID
    :param item_name: 主体名称
    """
    entities = graph_data.get("entities", [])
    relations = graph_data.get("relations", [])

    if not entities:
        return

    try:
        # 【修改】使用 neo4j_gateway 统一获取 session，database 从配置读取
        with neo4j_gateway.session() as session:
            session.execute_write(
                _write_graph_in_tx,
                entities, relations, chunk_id, item_name,
            )

        logger.debug(
            f"写入 {len(entities)} 个实体, {len(relations)} 条关系到 Neo4j"
        )

    except Exception as e:
        logger.warning(f"Neo4j 写入失败: {e}")


def _write_graph_in_tx(tx, entities: list[dict], relations: list[dict],
                       chunk_id: str, item_name: str) -> None:
    """
    在单个 Neo4j 事务内完成所有写入操作。

    写入顺序：
        1. 创建/合并 Chunk 节点
        2. 创建/合并 Entity 节点
        3. 建立 Entity → Chunk 关联
        4. 创建/合并 Entity 之间的关系

    :param tx: Neo4j 事务对象
    :param entities: 实体列表
    :param relations: 关系列表
    :param chunk_id: 切片 ID
    :param item_name: 主体名称
    """
    # 1. 创建/合并 Chunk 节点
    _tx_merge_chunk(tx, chunk_id, item_name)

    # 2. 处理每个实体
    for entity in entities:
        name = str(entity.get("name", "")).strip()
        if not name:
            continue
        label = str(entity.get("label", "")).strip()
        description = str(entity.get("description", "")).strip()

        # 创建/合并 Entity 节点
        _tx_merge_entity(tx, name, label, description, chunk_id, item_name)
        # 建立 Entity → Chunk 关联
        _tx_link_entity_to_chunk(tx, name, chunk_id, item_name)

    # 3. 处理每个关系
    for rel in relations:
        head = str(rel.get("head", "")).strip()
        tail = str(rel.get("tail", "")).strip()
        if not head or not tail:
            continue
        rel_type = str(rel.get("type", "RELATED_TO")).strip() or "RELATED_TO"
        _tx_merge_relation(tx, head, tail, rel_type, item_name)


def _tx_merge_chunk(tx, chunk_id: str, item_name: str) -> None:
    """执行 Cypher：创建/合并 Chunk 节点。"""
    tx.run(CYPHER_MERGE_CHUNK, chunk_id=chunk_id, item_name=item_name)


def _tx_merge_entity(tx, name: str, label: str, description: str,
                     chunk_id: str, item_name: str) -> None:
    """执行 Cypher：创建/合并 Entity 节点。"""
    tx.run(CYPHER_MERGE_ENTITY,
           name=name, label=label, description=description,
           chunk_id=chunk_id, item_name=item_name)


def _tx_link_entity_to_chunk(tx, name: str, chunk_id: str, item_name: str) -> None:
    """执行 Cypher：建立 Entity 到 Chunk 的 MENTIONED_IN 关联。"""
    tx.run(CYPHER_LINK_ENTITY_TO_CHUNK,
           name=name, chunk_id=chunk_id, item_name=item_name)


def _tx_merge_relation(tx, head: str, tail: str, rel_type: str, item_name: str) -> None:
    """执行 Cypher：创建/合并 Entity 之间的关系。"""
    # 白名单校验
    if rel_type not in ALLOWED_RELATION_TYPES:
        rel_type = "RELATED_TO"
    # 动态填充关系类型
    cypher = CYPHER_MERGE_RELATION_TEMPLATE.format(rel_type=rel_type)
    tx.run(cypher, head=head, tail=tail, item_name=item_name)


# ====================================================================== #
#                    6. 主入口                                             #
# ====================================================================== #

@step_log("process_single_chunk")
def process_single_chunk(content: str, chunk_id: str, item_name: str) -> None:
    """
    处理单个文本切片：LLM 提取 → 解析清洗 → Milvus 写入 → Neo4j 写入。

    :param content: 文本切片内容
    :param chunk_id: 切片 ID
    :param item_name: 主体名称
    """
    # 1. LLM 提取实体和关系
    raw_response = llm_extract_entities_relations(content)
    if not raw_response:
        return

    # 2. 解析并清洗 JSON
    graph_data = parse_and_clean_graph_data(raw_response)
    if not graph_data.get("entities"):
        return

    logger.info(
        f"切片 {chunk_id}: "
        f"提取到 {len(graph_data['entities'])} 个实体, "
        f"{len(graph_data['relations'])} 条关系"
    )

    # 3. 写入 Milvus（实体向量）
    save_entities_to_milvus(
        graph_data.get("entities", []),
        chunk_id, content, item_name,
    )

    # 4. 写入 Neo4j（图数据）
    save_graph_to_neo4j(graph_data, chunk_id, item_name)


@step_log("build_knowledge_graph")
def build_knowledge_graph(state: ImportGraphState) -> ImportGraphState:
    """
    知识图谱构建服务总入口。

    流程：
        1. 获取并校验 chunks 和 item_name
        2. 遍历每个切片，执行完整的提取 → 写入流程

    :param state: LangGraph 流程状态字典
    :return: 更新后的 state（不变，仅做副作用操作）
    """
    # 1. 获取并且校验 切片数据和主体名称
    chunks, item_name = get_chunks_for_kg(state)

    logger.info(f"开始知识图谱构建，共 {len(chunks)} 个切片，主体: {item_name}")

    # 2. 遍历每个切片进行处理
    for i, chunk in enumerate(chunks, start=1):
        # 跳过非字典类型的切片
        if not isinstance(chunk, dict):
            continue

        # 提取关键字段
        content = chunk.get("content", "")
        chunk_id = str(chunk.get("chunk_id", f"temp_{i}"))
        chunk_item_name = chunk.get("item_name") or item_name

        # 跳过空内容
        if not content or not chunk_item_name:
            continue

        logger.debug(f"处理切片 {i}/{len(chunks)}: {chunk_id}")

        # 处理单个切片
        process_single_chunk(content, chunk_id, chunk_item_name)

    logger.info("知识图谱构建完成")

    return state
