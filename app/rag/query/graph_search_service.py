"""
Neo4j 图检索服务模块

核心功能：
    1. 从查询中提取关键实体
    2. 在 Neo4j 中模糊匹配实体
    3. 遍历 1-2 跳关系子图
    4. 格式化结果为统一检索格式

整体流程：
    rewritten_query → 实体提取 → Neo4j 匹配 → 子图遍历 → 格式化输出
"""
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser

from app.shared.runtime.logger import logger, step_log
from app.infra.neo4j_store.neo4j_gateway import neo4j_gateway
from app.infra.llm.providers import llm_provider
from app.process.query.agent.state import QueryGraphState
from app.shared.runtime.load_prompt import load_prompt

# ====================================================================== #
#                    1. 获取并校验参数                                     #
# ====================================================================== #


@step_log("get_graph_search_params")
def get_graph_search_params(state: QueryGraphState) -> tuple[list[str], str]:
    """
    从 state 中获取图检索所需参数。

    :param state: 查询流程状态
    :return: (item_names, rewritten_query)
    """
    item_names = state.get("item_names", [])
    rewritten_query = state.get("rewritten_query")

    if not item_names or not rewritten_query:
        logger.warning("item_names 或 rewritten_query 为空，图检索跳过")
        raise ValueError("图检索参数不足，跳过执行")

    return item_names, rewritten_query


# ====================================================================== #
#                    2. 从查询中提取关键词                                  #
# ====================================================================== #

@step_log("extract_query_keywords")
def extract_query_keywords(rewritten_query: str) -> list[str]:
    """
    使用 LLM 从查询中提取关键词。

    :param rewritten_query: 改写后的查询
    :return: 关键词列表
    """
    try:
        chain = llm_provider.chat() | StrOutputParser()
        messages = [
            SystemMessage(content=load_prompt("entity_extract")),
            HumanMessage(content=rewritten_query),
        ]
        response = chain.invoke(messages)

        # 解析 JSON 数组
        import json
        response = response.strip()
        # 去除可能的 markdown 代码块
        if response.startswith("```"):
            response = response.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        keywords = json.loads(response)
        if isinstance(keywords, list):
            logger.info(f"从查询中提取到关键词: {keywords}")
            return keywords[:5]  # 最多5个
        return []

    except Exception as e:
        logger.warning(f"关键词提取失败: {e}，使用原始查询作为关键词")
        # 降级：直接用查询中的名词（简单分词）
        return [rewritten_query[:10]]


# ====================================================================== #
#                    3. Neo4j 实体模糊匹配                                #
# ====================================================================== #

# Cypher: 模糊匹配实体（item_name 也做模糊匹配，容忍空格差异）
CYPHER_FUZZY_MATCH_ENTITY = """
    MATCH (n:Entity)
    WHERE ANY(iname IN $item_names
              WHERE n.item_name = iname
                 OR replace(n.item_name, ' ', '') = replace(iname, ' ', ''))
      AND (n.name CONTAINS $keyword OR $keyword CONTAINS n.name)
    RETURN DISTINCT n.name AS name,
                    n.description AS description,
                    n.types AS types
    LIMIT 5
"""


def _normalize_item_names(item_names: list[str]) -> list[str]:
    """
    对 item_names 做去空格归一化，用于兼容导入/查询两侧命名差异。

    例: "HAK 180 烫金机" → "HAK180烫金机"
    """
    normalized = []
    seen = set()
    for name in item_names:
        raw = name.strip()
        compact = raw.replace(" ", "")
        for candidate in (raw, compact):
            if candidate and candidate not in seen:
                seen.add(candidate)
                normalized.append(candidate)
    return normalized


@step_log("fuzzy_match_entities")
def fuzzy_match_entities(keywords: list[str], item_names: list[str]) -> list[dict]:
    """
    在 Neo4j 中根据关键词模糊匹配实体。

    :param keywords: 提取的关键词列表
    :param item_names: 限定的主体名称列表
    :return: 匹配到的实体列表 [{"name", "description", "types"}]
    """
    matched_entities = []
    seen_names = set()

    # 对 item_names 做归一化（原始 + 去空格版本），提高匹配率
    normalized_names = _normalize_item_names(item_names)
    logger.debug(f"item_names 归一化: {item_names} → {normalized_names}")

    try:
        with neo4j_gateway.session() as session:
            for keyword in keywords:
                if not keyword.strip():
                    continue

                result = session.run(
                    CYPHER_FUZZY_MATCH_ENTITY,
                    keyword=keyword.strip(),
                    item_names=normalized_names,
                )

                for record in result:
                    name = record["name"]
                    if name not in seen_names:
                        seen_names.add(name)
                        matched_entities.append({
                            "name": name,
                            "description": record["description"] or "",
                            "types": record["types"] or [],
                        })

                # 匹配够 3 个实体即可
                if len(matched_entities) >= 3:
                    break

        logger.info(
            f"模糊匹配到 {len(matched_entities)} 个实体: {[e['name'] for e in matched_entities]}")

    except Exception as e:
        logger.warning(f"Neo4j 实体匹配失败: {e}")

    return matched_entities


# ====================================================================== #
#                    4. 子图遍历                                          #
# ====================================================================== #

# Cypher: 从实体出发遍历 1-2 跳子图（item_name 模糊匹配）
CYPHER_TRAVERSE_SUBGRAPH = """
    MATCH (start:Entity)-[r*1..2]-(connected:Entity)
    WHERE start.name = $entity_name
      AND ANY(iname IN $item_names
              WHERE start.item_name = iname
                 OR replace(start.item_name, ' ', '') = replace(iname, ' ', ''))
      AND ANY(iname IN $item_names
              WHERE connected.item_name = iname
                 OR replace(connected.item_name, ' ', '') = replace(iname, ' ', ''))
    RETURN DISTINCT
        start.name AS start_name,
        start.description AS start_description,
        [rel IN r | type(rel)] AS rel_types,
        connected.name AS connected_name,
        connected.description AS connected_description,
        connected.types AS connected_types
    LIMIT 15
"""

# Cypher: 获取操作的完整步骤链（item_name 模糊匹配）
CYPHER_GET_OPERATION_STEPS = """
    MATCH (op:Entity {name: $operation_name})-[:HAS_STEP]->(step:Entity)
    WHERE ANY(iname IN $item_names
              WHERE op.item_name = iname
                 OR replace(op.item_name, ' ', '') = replace(iname, ' ', ''))
    OPTIONAL MATCH (step)-[:NEXT_STEP]->(next_step:Entity)
    OPTIONAL MATCH (step)-[:USES_TOOL]->(tool:Entity)
    OPTIONAL MATCH (step)-[:HAS_WARNING]->(warning:Entity)
    OPTIONAL MATCH (step)-[:AFFECTS]->(part:Entity)
    RETURN step.name AS step_name,
           step.description AS step_description,
           collect(DISTINCT next_step.name) AS next_steps,
           collect(DISTINCT tool.name) AS tools,
           collect(DISTINCT warning.name) AS warnings,
           collect(DISTINCT warning.description) AS warning_descs,
           collect(DISTINCT part.name) AS affected_parts
    ORDER BY step.name
"""


@step_log("traverse_subgraph")
def traverse_subgraph(entities: list[dict], item_names: list[str]) -> list[dict]:
    """
    从匹配到的实体出发，遍历 1-2 跳关系子图。

    :param entities: 匹配到的实体列表
    :param item_names: 限定的主体名称列表
    :return: 子图遍历结果列表
    """
    if not entities:
        return []

    subgraph_results = []

    try:
        with neo4j_gateway.session() as session:
            for entity in entities:
                entity_name = entity["name"]

                # 尝试获取操作步骤链（如果是 Operation 类型实体）
                if "Operation" in (entity.get("types") or []):
                    step_results = session.run(
                        CYPHER_GET_OPERATION_STEPS,
                        operation_name=entity_name,
                        item_names=item_names,
                    )
                    for record in step_results:
                        step_info = _format_step_record(entity_name, record)
                        if step_info:
                            subgraph_results.append(step_info)

                # 通用子图遍历
                graph_results = session.run(
                    CYPHER_TRAVERSE_SUBGRAPH,
                    entity_name=entity_name,
                    item_names=item_names,
                )
                for record in graph_results:
                    path_info = _format_path_record(record)
                    if path_info:
                        subgraph_results.append(path_info)

    except Exception as e:
        logger.warning(f"Neo4j 子图遍历失败: {e}")

    logger.info(f"子图遍历获取到 {len(subgraph_results)} 条关系信息")
    return subgraph_results


def _format_step_record(operation_name: str, record) -> dict | None:
    """格式化操作步骤记录为文本描述。"""
    step_name = record["step_name"] or ""
    step_desc = record["step_description"] or ""
    tools = [t for t in (record["tools"] or []) if t]
    warnings = [w for w in (record["warnings"] or []) if w]
    warning_descs = [d for d in (record["warning_descs"] or []) if d]
    parts = [p for p in (record["affected_parts"] or []) if p]

    if not step_name:
        return None

    # 组装结构化文本
    lines = [f"[步骤] {step_name}"]
    if step_desc:
        lines.append(f"  描述: {step_desc}")
    if tools:
        lines.append(f"  使用工具: {', '.join(tools)}")
    if parts:
        lines.append(f"  操作部件: {', '.join(parts)}")
    if warnings:
        for i, w in enumerate(warnings):
            desc = warning_descs[i] if i < len(warning_descs) else ""
            lines.append(f"  ⚠ 警告: {w}" + (f" - {desc}" if desc else ""))

    return {
        "type": "step",
        "operation": operation_name,
        "text": "\n".join(lines),
        "step_name": step_name,
    }


def _format_path_record(record) -> dict | None:
    """格式化子图路径记录为文本描述。"""
    start_name = record["start_name"] or ""
    start_desc = record["start_description"] or ""
    rel_types = record["rel_types"] or []
    connected_name = record["connected_name"] or ""
    connected_desc = record["connected_description"] or ""
    connected_types = record["connected_types"] or []

    if not start_name or not connected_name:
        return None

    # 组装关系链文本
    rel_chain = " → ".join(rel_types) if rel_types else "RELATED_TO"
    type_label = f"[{','.join(connected_types)}]" if connected_types else ""

    text = f"{start_name} -[{rel_chain}]-> {connected_name}{type_label}"
    if connected_desc and connected_desc != connected_name:
        text += f"\n  详情: {connected_desc}"

    return {
        "type": "relation",
        "start": start_name,
        "connected": connected_name,
        "rel_types": rel_types,
        "text": text,
    }


# ====================================================================== #
#                    5. 格式化输出                                        #
# ====================================================================== #

@step_log("format_graph_results")
def format_graph_results(
    entities: list[dict],
    subgraph: list[dict]
) -> list[dict]:
    """
    将图检索结果格式化为与其他检索结果统一的格式。

    :param entities: 匹配到的实体列表
    :param subgraph: 子图遍历结果
    :param rewritten_query: 改写后的查询
    :return: 统一格式的检索结果列表
    """
    if not entities and not subgraph:
        return []

    graph_chunks = []

    # 按操作分组组装结果
    operation_texts: dict[str, list[str]] = {}
    general_texts: list[str] = []

    for item in subgraph:
        if item["type"] == "step":
            op = item.get("operation", "未知操作")
            operation_texts.setdefault(op, []).append(item["text"])
        else:
            general_texts.append(item["text"])

    # 每个操作组装为一个检索结果
    for idx, (op_name, steps) in enumerate(operation_texts.items()):
        content = f"【{op_name}】操作步骤:\n" + "\n".join(steps)
        graph_chunks.append({
            "chunk_id": f"graph_op_{idx}",
            "score": 0.8,
            "title": f"图检索: {op_name}",
            "content": content,
            "source": "neo4j",
            "url": "",
        })

    # 通用关系组装为一个检索结果
    if general_texts:
        content = "【知识图谱关系】\n" + "\n".join(general_texts[:10])
        graph_chunks.append({
            "chunk_id": "graph_relations",
            "score": 0.7,
            "title": "图检索: 实体关系",
            "content": content,
            "source": "neo4j",
            "url": "",
        })

    # 如果只有实体没有子图，也把实体信息输出
    if not graph_chunks and entities:
        entity_texts = []
        for e in entities:
            text = f"[{','.join(e.get('types', []))}] {e['name']}"
            if e.get("description"):
                text += f": {e['description']}"
            entity_texts.append(text)

        graph_chunks.append({
            "chunk_id": "graph_entities",
            "score": 0.6,
            "title": "图检索: 相关实体",
            "content": "【相关实体】\n" + "\n".join(entity_texts),
            "source": "neo4j",
            "url": "",
        })

    logger.info(f"图检索格式化完成，共 {len(graph_chunks)} 条结果")
    # {增加}
    if graph_chunks:
        logger.info(f"【得分】graph 检索结果: "
                    f"共{len(graph_chunks)}条, "
                    f"分数: {[c['score'] for c in graph_chunks]}, "
                    f"类型: {[c['chunk_id'].split('_')[1] if '_' in c['chunk_id'] else c['chunk_id'] for c in graph_chunks]}")
    return graph_chunks


# ====================================================================== #
#                    6. 主入口                                            #
# ====================================================================== #

@step_log("search_by_graph")
def search_by_graph(state: QueryGraphState) -> list[dict]:
    """
    图检索服务总入口。

    流程：
        1. 获取并校验参数
        2. 从查询中提取关键词
        3. Neo4j 模糊匹配实体
        4. 遍历 1-2 跳子图
        5. 格式化结果

    :param state: 查询流程状态
    :return: 统一格式的图检索结果列表
    """
    try:
        # 1. 获取参数
        item_names, rewritten_query = get_graph_search_params(state)

        # 1.5 归一化 item_names（原始 + 去空格版本），容忍导入/查询两侧命名差异
        # item_names = _normalize_item_names(item_names)
        # logger.debug(f"归一化后 item_names: {item_names}")

        # 2. 提取关键词
        keywords = extract_query_keywords(rewritten_query)
        if not keywords:
            logger.info("未提取到关键词，图检索返回空结果")
            return []

        # 3. Neo4j 模糊匹配实体
        entities = fuzzy_match_entities(keywords, item_names)
        if not entities:
            logger.info("Neo4j 中未匹配到实体，图检索返回空结果")
            return []

        # 4. 子图遍历
        subgraph = traverse_subgraph(entities, item_names)

        # 5. 格式化结果
        graph_chunks = format_graph_results(entities, subgraph)

        return graph_chunks

    except Exception as e:
        logger.warning(f"图检索执行异常: {e}，返回空结果")
        return []
