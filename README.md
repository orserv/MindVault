# RAG 智库项目（MindVault）

## 1 项目介绍
MindVault 是面向企业级知识库问答的 **检索增强生成（RAG）** 系统。它通过 **FastAPI + LangGraph** 框架，将文档导入、向量化、知识图谱构建以及多路检索与答案生成统一管理，实现了高可扩展、可配置的企业级智能问答能力。

主要功能包括：
- **文档导入**：PDF → Markdown → 图片增强 → 主体识别 → 切块 → 向量化 → Milvus 入库，同时同步到 Neo4j 知识图谱。
- **智能查询**：问题改写 → 商品确认 → 多路检索（Embedding、HyDE、WebSearch、Neo4j 图谱） → RRF 融合 → Rerank → LLM 生成答案，支持 **SSE 流式** 输出。

## 2 目录结构
```
shopkeeper_brain/
├─ app/
│   ├─ api/
│   │   └─ http/
│   │       ├─ import_server.py   # 导入服务入口
│   │       └─ query_server.py    # 查询服务入口
│   ├─ infra/
│   │   └─ neo4j_store/
│   │       └─ neo4j_gateway.py  # Neo4j 交互层
│   ├─ process/
│   │   ├─ import_/               # 文档导入流程
│   │   │   └─ agent/
│   │   │       ├─ main_graph.py   # LangGraph 编排
│   │   │       └─ nodes/          # 各节点实现
│   │   └─ query/
│   │       └─ agent/
│   │           ├─ main_graph.py   # 查询流程编排
│   │           └─ nodes/          # 各检索/融合节点
│   ├─ rag_eval/                    # 评估脚本/工具
│   ├─ resources/
│   │   └─ prompts/                # LLM Prompt 模板
│   └─ shared/
│       ├─ config/                 # 配置对象（Neo4j、Milvus、LLM 等）
│       ├─ clients/                # Neo4j、MinIO 等客户端
│       └─ utils/                  # 通用工具、日志、任务管理等
├─ requirements.txt                # 依赖列表
├─ .env.example                    # 环境变量示例
└─ README.md                      # 本文档（中文详细说明）
```
> 各目录职责说明：
> - `app/api/http`：FastAPI 接口，实现导入和查询两大服务。
> - `app/process/*/agent`：基于 LangGraph 的状态机，每个节点负责单一业务步骤，易于插拔。
> - `app/shared/config`：使用 `dataclass` 将所有配置统一管理，从 `.env` 注入。

## 3 项目特点
- **全链路可配置**：通过 `.env` 管理 LLM、Embedding、Reranker、Milvus、Neo4j 等外部服务。
- **多路检索**：向量检索、HyDE 生成检索、DashScope WebSearch、Neo4j 图谱检索四路并行。
- **RRF 融合 + Rerank**：使用 Reciprocal Rank Fusion 合并结果，再用 BGE‑Reranker 二次排序，提升答案质量。
- **流式输出**：基于 SSE（Server‑Sent Events）实现增量答案返回，适配前端即时交互。
- **模块化设计**：每个业务步骤都是独立节点，便于二次开发或替换模型。
- **企业级部署**：兼容 Milvus、Neo4j、MongoDB、MinIO，支持 Docker‑Compose 快速启动。

## 4 运行环境
| 组件 | 推荐版本 | 备注 |
|------|----------|------|
| Python | >= 3.10 | 官方 CPython |
| Neo4j | 5.x (Bolt 7687) | 关系型知识图谱存储 |
| Milvus | 2.x (gRPC 19530) | 向量库 |
| MongoDB | 5.x | 文档元数据持久化 |
| MinIO | 2023.x | 对象存储（原始文件、图片） |
| Docker / Docker‑Compose | 最新 | 可选，用于快速启动依赖服务 |
| DashScope MCP (可选) | - | WebSearch 节点使用的外部搜索服务 |

> 若本地未安装上述服务，可使用项目根目录的 `docker-compose.yml`（若提供）一键启动。

## 5 安装依赖
```bash
# 1. 克隆仓库
git clone https://github.com/orserv/MindVault.git
cd MindVault

# 2. 创建虚拟环境（推荐）
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. 安装 Python 依赖
pip install -r requirements.txt

```
> `requirements.txt` 已列出 `fastapi`, `uvicorn`, `langgraph`, `neo4j`, `pymilvus`, `pymongo`, `minio`, `dashscope` 等关键库。

## 6 环境配置
复制 `.env.example` 为 `.env`，并根据实际部署填写关键变量。

```ini
# =========================
# 应用基础配置
# =========================
IMPORT_APP_NAME=Enterprise RAG Import Service
QUERY_APP_NAME=Enterprise RAG Query Service
APP_ENV=dev
APP_HOST=0.0.0.0
IMPORT_APP_PORT=8000
QUERY_APP_PORT=8001
CORS_ORIGINS=*

# =========================
# LLM / VL 模型配置
# =========================
OPENAI_BASE_URL=https://your-llm-endpoint/v1
OPENAI_API_KEY=sk-your-key
LLM_DEFAULT_MODEL=qwen-plus
LLM_DEFAULT_TEMPERATURE=0.1
VL_MODEL=qwen-vl-max

# =========================
# Embedding 配置
# =========================
BGE_M3_PATH=./models/bge-m3
BGE_M3=BAAI/bge-m3
BGE_DEVICE=cpu
BGE_FP16=False

# =========================
# Reranker 配置
# =========================
BGE_RERANKER_LARGE=./models/bge-reranker-v2-m3
BGE_RERANKER_DEVICE=cpu
BGE_RERANKER_FP16=False

# =========================
# Milvus 配置
# =========================
MILVUS_URL=http://127.0.0.1:19530
CHUNKS_COLLECTION=kb_chunks
ENTITY_NAME_COLLECTION=kb_entities
ITEM_NAME_COLLECTION=kb_item_names
ENTITY_NAME_COLLECTION=kb_graph_entity_names

# =========================
# Neo4j 配置
# =========================
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j

# =========================
# Mongo 配置
# =========================
MONGO_URL=mongodb://127.0.0.1:27017
MONGO_DB_NAME=enterprise_rag

# =========================
# MinIO 配置
# =========================
MINIO_ENDPOINT=127.0.0.1:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=enterprise-rag
MINIO_IMG_DIR=/kb-images
MINIO_SECURE=False

# =========================
# MinerU 配置（可选）
# =========================
MINERU_BASE_URL=https://your-mineru-endpoint
MINERU_API_TOKEN=your-mineru-token

# =========================
# DashScope MCP / WebSearch 配置（可选）
# =========================
MCP_DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/mcp

# =========================
# 项目根目录可选配置
# =========================
PROJECT_ROOT=
```
> **关键说明**：
> - `IMPORT_APP_NAME` / `QUERY_APP_NAME` 用于 FastAPI 文档标题。 
> - `LLM_DEFAULT_MODEL`、`VL_MODEL` 决定使用的语言模型与视觉模型。 
> - `BGE_M3` 与 `BGE_RERANKER_LARGE` 可以是本地路径或 HuggingFace 标识符。 
> - `MINIO_IMG_DIR` 必须以 `/` 开头，表示对象存储中图片的根目录。

## 7 接口说明
### 7.1 Import Service (`app/api/http/import_server.py`)
| 方法 | 路径 | 描述 | 返回 |
|------|------|------|------|
| **POST** | `/upload` | 上传一个或多个文件，系统为每个文件生成唯一 `task_id` 并异步执行导入链。 | `task_id` 列表、成功信息 |
| **GET** | `/status/{task_id}` | 查询对应 `task_id` 的导入任务状态、已完成节点、当前进行中的节点。 | `task_id`, `status`, `done_list`, `running_list` |
| **GET** | `/index` | 返回演示页面 `import.html`（用于快速测试 UI）。 | HTML 文件 |

**示例**（使用 `curl`）：
```bash
# 上传文件
curl -X POST "http://127.0.0.1:8000/upload" \
    -F "files=@/path/to/document.pdf" \
    -H "Content-Type: multipart/form-data"

# 查询任务状态
curl http://127.0.0.1:8000/status/<task_id>
```

### 7.2 Query Service (`app/api/http/query_server.py`)
| 方法 | 路径 | 描述 | 返回 |
|------|------|------|------|
| **POST** | `/query` | 接收用户自然语言查询，返回答案或 SSE 流式答案（取决于 `is_stream` 参数）。 | `answer`（JSON）或 `text/event-stream` |
| **GET** | `/health` | 健康检查，返回 `200 OK`。 | `{ "status": "ok" }` |

**示例**（同步返回）：
```bash
curl -X POST "http://127.0.0.1:8001/query" \
    -H "Content-Type: application/json" \
    -d '{"session_id":"sess-001","query":"烫金机的手柄怎么拆卸？","is_stream":false}'
```

**示例**（SSE 流式）：
```bash
curl -N "http://127.0.0.1:8001/query?session_id=sess-001&query=烫金机的手柄怎么拆卸？&is_stream=true"
```

## 8 导入链（Import Chain）过程
1. **文件上传** → `import_server.upload` 将上传的文件保存至 `output/<date>/<task_id>/`。
2. **创建 ImportGraphState** → `create_default_state(task_id, local_file_path, local_file_dir)`，封装路径、任务 ID、运行时状态等信息。
3. **LangGraph 编排** (`app/process/import_/agent/main_graph.py`)：
   - `node_entry`：校验文件合法性。
   - `node_pdf_to_md`：PDF 转 Markdown，保留图片、标题结构。
   - `node_split_chunks`：根据字数或段落切块，生成 `Chunk` 列表。
   - `node_embedding`：调用 BGE‑M3 将每块向量化并写入 Milvus 指定集合。
   - `node_knowledge_graph`：利用 `entity_extract.prompt` 抽取实体关系，调用 `neo4j_gateway` 将实体/关系写入 Neo4j。
4. **任务状态更新**：通过 `task_utils.update_task_status` 在每一步更新状态，最终标记为 `completed` 或 `failed`。

> 所有节点均通过 `app.shared.runtime.logger` 记录 INFO/ERROR，便于排查。

## 9 查询链（Query Chain）过程
1. **接收查询** → `query_server` 将请求包装为 `QueryGraphState`（包括 `original_query`、`session_id` 等）。
2. **商品确认** (`node_item_name_confirm`)：使用 `item_name_recognition.prompt` 判断查询中是否包含明确的商品名称。
   - **有商品名** → 进入多路检索。
   - **无商品名** → 直接跳到 `node_answer_output`（基于原始查询生成答案）。
3. **并行检索**（四路）：
   - `node_search_embedding`：Milvus 向量相似搜索。
   - `node_search_embedding_hyde`：先用 HyDE 生成潜在检索查询，再在 Milvus 检索。
   - `node_web_search_mcp`：调用 DashScope MCP 进行网络搜索。
   - `node_search_graph`：Neo4j 图谱检索，基于实体/关系路径返回文档。
4. **RRF 融合** (`node_rrf`)：对四路返回的文档列表进行 Reciprocal Rank Fusion，得到统一排序列表。
5. **Rerank** (`node_rerank`)：使用 BGE‑Reranker 对融合后的结果进行二次排序，提升相关性。
6. **答案生成** (`node_answer_output`)：将最终检索结果拼装进 Prompt，调用 LLM（如 Qwen‑Plus）生成自然语言答案；若 `is_stream=True`，通过 SSE 按块返回。

**关键状态流(简化示意)**：
```
QueryGraphState -> node_item_name_confirm
    ├─(有商品名)─► 并行 {Embedding, HyDE, WebSearch, Graph}
    │        └─► node_rrf
    │                └─► node_rerank
    │                    └─► node_answer_output -> END
    └─(无商品名)─► node_answer_output -> END
```

---

## 10 验证与提交
- **Git 检查**：`git status` 确认 `README.md` 已被添加。
- **启动服务**：分别启动导入服务（`uvicorn app.api.http.import_server:app --host $APP_HOST --port $IMPORT_APP_PORT`）和查询服务（`uvicorn app.api.http.query_server:app --host $APP_HOST --port $QUERY_APP_PORT`），使用上述 `curl` 示例验证接口返回是否符合文档描述。
- **单元测试**：运行 `pytest`（项目自带测试），确保文档添加未导致代码异常。

---

## 11 贡献指南
1. Fork 本仓库并创建新分支（如 `feat/README`）。
2. 按项目根目录的 **PEP‑8** 与 **type‑hint** 规范编写代码。
3. 新增或修改功能后，请确保 `pytest` 全部通过。
4. 提交 PR，标题请简要说明变更，正文列出变更点与可能的影响。

---

## 12 许可证
本项目采用 **MIT License**，详见根目录 `LICENSE` 文件。

---

