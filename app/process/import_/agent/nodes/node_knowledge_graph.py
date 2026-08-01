from app.shared.runtime.logger import node_log
from app.shared.utils.task_utils import add_done_task, add_running_task
from app.process.import_.agent.state import ImportGraphState
from app.rag.import_.knowledge_graph import build_knowledge_graph


@node_log("node_knowledge_graph")
def node_knowledge_graph(state: ImportGraphState) -> ImportGraphState:
    """
    节点: 知识图谱构建 (node_knowledge_graph)

    功能：
        1. 遍历每个文本切片
        2. 调用 LLM 提取实体和关系
        3. 解析清洗 JSON 数据
        4. 写入 Neo4j 图数据库

    调用链：node → build_knowledge_graph(state) → 完整 KG 构建流程
    """
    add_running_task(state["task_id"], "node_knowledge_graph")
    state = build_knowledge_graph(state)
    add_done_task(state["task_id"], "node_knowledge_graph")
    return state


if __name__ == '__main__':
    # --- 单元测试 ---
    import os
    from dotenv import load_dotenv

    # 加载环境变量
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(current_dir))))
    load_dotenv(os.path.join(project_root, ".env"))

    # 构造测试数据（HAK180 烫金机）
    test_state = {
        "task_id": "test_kg_hak180_001",
        "item_name": "HAK180烫金机",
        "chunks": [
            {
                "content": """# HAK180 烫金机手柄拆卸

警告: 拆卸手柄前请务必断开电源，防止触电或设备意外启动。

1. 关闭设备电源开关，并拔下电源插头。
2. 使用十字螺丝刀拧下手柄固定螺丝（共2颗，位于手柄两侧）。
3. 轻轻向上提起手柄，注意不要拉扯内部连接线。
4. 断开手柄与主板之间的排线连接器（按压卡扣后拔出）。
5. 取下手柄，放置在防静电垫上。

注意: 手柄内部含有温控传感器，拆卸时避免碰撞或弯折传感器引脚。""",
                "chunk_id": "chunk_hak180_001",
                "item_name": "HAK180烫金机",
            },
            {
                "content": """# HAK180 烫金机温度调节

操作前请确保设备已预热至少3分钟。

1. 按下控制面板上的"SET"键进入温度设置模式。
2. 使用上下箭头键调整目标温度（范围：100°C - 300°C）。
3. 再次按下"SET"键确认设置，设备将自动加热至目标温度。
4. 当显示屏温度稳定在目标值±5°C时，即可开始烫金操作。

警告: 温度超过250°C时，请务必佩戴隔热手套操作。
工具: 控制面板、隔热手套""",
                "chunk_id": "chunk_hak180_002",
                "item_name": "HAK180烫金机",
            },
        ]
    }

    print("=" * 60)
    print("开始测试: 知识图谱构建节点 (HAK180烫金机)")
    print("=" * 60)
    print(f"【输入】: {test_state['item_name']}")
    print(f"【切片数】: {len(test_state['chunks'])}")
    print("-" * 60)

    try:
        result_state = node_knowledge_graph(test_state)
        print("\n✅ 知识图谱构建节点执行完成!")
        print("-" * 60)

        # 验证 Neo4j 写入结果
        print("\n正在验证 Neo4j 数据...")
        from app.infra.neo4j_store.neo4j_gateway import neo4j_gateway

        with neo4j_gateway.session() as session:
            # 查询该主体的 Entity 节点数量
            result = session.run(
                "MATCH (n:Entity {item_name: $item_name}) RETURN count(n) AS cnt",
                item_name="HAK180烫金机"
            )
            entity_count = result.single()["cnt"]

            # 查询该主体的关系数量
            result = session.run(
                """MATCH (a:Entity {item_name: $item_name})-[r]->(b:Entity)
                   RETURN count(r) AS cnt""",
                item_name="HAK180烫金机"
            )
            relation_count = result.single()["cnt"]

            # 查询实体类型分布
            result = session.run(
                """MATCH (n:Entity {item_name: $item_name})
                   UNWIND n.types AS type
                   RETURN type, count(*) AS count
                   ORDER BY count DESC""",
                item_name="HAK180烫金机"
            )
            type_dist = {record["type"]: record["count"] for record in result}

        print(f"  Entity 节点数: {entity_count}")
        print(f"  关系数量: {relation_count}")
        print(f"  类型分布: {type_dist}")

        if entity_count > 0:
            print("\n✅ Neo4j 数据验证通过！")
        else:
            print("\n⚠️ Neo4j 中未找到数据，请检查 LLM 提取和 Neo4j 写入日志")

    except Exception as e:
        import traceback
        print(f"\n❌ 测试失败: {e}")
        traceback.print_exc()
