# 企业化 RAG 智能体项目
 
一个面向知识库问答场景的 RAG 智能体项目，当前已经完成兼容式企业化重构，具备以下能力：
 
- 文档导入：支持 `PDF -> Markdown -> 图片增强 -> 主体识别 -> 切块 -> 向量化 -> Milvus 入库`
- 智能查询：支持 `问题改写 -> 商品确认 -> Embedding 召回 -> HyDE 召回 -> WebSearch -> RRF -> Rerank -> 答案生成`
- 流式问答：支持 SSE 流式输出
 
## 项目特点
 
- 保留原有导入流程与查询流程的可运行能力，并统一收口到 `app/process`
- 当前采用 `api / infra / shared / rag / process` 分层
- 查询链核心能力已按节点职责下沉到 `app/rag/query`
- 导入链核心能力已下沉到 `app/rag/import_`
- 保持导入服务与查询服务双入口、双端口运行
 
## 目录结构
 
```
app/
├─ api/                           # 接口层
│  ├─ http/                       # 导入/查询两个可运行 server 入口
│  └─ schemas/                    # 请求与响应数据结构
├─ infra/                         # 基础设施正式出口
│  ├─ config/                     # 应用运行配置与端口设置
│  ├─ document_parse/             # PDF 解析服务门面（MinerU）
│  ├─ llm/                        # LLM / Embedding / Reranker 提供者出口
│  ├─ object_storage/             # 对象存储门面（MinIO）
│  ├─ persistence/                # 持久化门面（聊天历史等）
│  └─ vectorstore/                # 向量库门面（Milvus）
├─ process/                       # 流程编排层
│  ├─ import_/                    # 导入图、导入状态与导入页面
│  │  ├─ agent/                   # LangGraph 导入图与各节点
│  │  └─ page/                    # 导入演示页面
│  └─ query/                      # 查询图、查询状态与查询页面
│     ├─ agent/                   # LangGraph 查询图与各节点
│     └─ page/                    # 查询演示页面
├─ rag/                           # RAG 核心能力层
│  ├─ import_/                    # 导入域能力：入口识别、解析、图片增强、切块、主体识别、向量化、入库
│  └─ query/                      # 查询域能力：主体确认、检索、HyDE、WebSearch、RRF、Rerank、答案生成
├─ resources/                     # 应用资源目录
│  └─ prompts/                    # 提示词模板
├─ shared/                        # 公共底座
│  ├─ clients/                    # 底层客户端工具（Milvus / Mongo / MinIO）
│  ├─ config/                     # 原子配置读取与各组件配置对象
│  ├─ model/                      # 模型工具封装
│  ├─ runtime/                    # 运行时能力（日志、Prompt 加载）
│  ├─ tool/                       # 模型下载等辅助脚本
│  └─ utils/                      # 通用工具（SSE、任务状态、限流、路径等）
└─ __init__.py
 
docs/
└─ architecture.md                # 当前项目架构说明

```
 
## 运行环境
 
- Python `3.11+`
- 推荐使用 `uv`
- 推荐使用项目本地虚拟环境 `.venv`
- 需要准备外部依赖：
  - Milvus
  - MongoDB
  - MinIO
  - 大模型与视觉模型服务
  - MinerU PDF 解析服务
  - DashScope WebSearch MCP
 
## 安装依赖
 
### 方式一：使用 uv
 
```bash
uv venv
uv sync
```
 
### 方式二：使用 pip
 
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```
 
## 环境变量
 
1. 复制示例文件：
 
```bash
copy .env.example .env
```
 
2. 按实际环境填写：
 
- 应用基础配置
- LLM / VL 模型配置
- Embedding / Reranker 模型配置
- Milvus / Mongo / MinIO 配置
- MinerU 配置
- DashScope MCP 配置
 
详细变量说明见 `.env.example`
 
## 启动方式
 
### 启动导入服务
 
```bash
uv run uvicorn app.api.http.import_server:app --host 0.0.0.0 --port 8000 --reload
```
 
### 启动查询服务
 
```bash
uv run uvicorn app.api.http.query_server:app --host 0.0.0.0 --port 8001 --reload
```
 
如果不使用 `uv`：
 
```bash
.venv\Scripts\python -m uvicorn app.api.http.import_server:app --host 0.0.0.0 --port 8000 --reload
.venv\Scripts\python -m uvicorn app.api.http.query_server:app --host 0.0.0.0 --port 8001 --reload
```
 
### 健康检查
 
- 导入服务：`GET http://127.0.0.1:8000/health`
- 查询服务：`GET http://127.0.0.1:8001/health`
 
### 文档入口
 
- 导入 Swagger: `http://127.0.0.1:8000/docs`
- 查询 Swagger: `http://127.0.0.1:8001/docs`
 
## 主要入口
 
### 导入相关
 
- 页面：`GET /html`
- 上传：`POST /upload`
- 状态：`GET /status/{task_id}`
- 默认端口：`8000`
 
### 查询相关
 
- 页面：`GET /html`
- 查询：`POST /query`
- SSE：`GET /stream/{session_id}`
- 历史：`GET /history/{session_id}`
- 清空历史：`DELETE /history/{session_id}`
- 默认端口：`8001`
 
## 推荐演示流程
 
### 1. 先演示导入
 
- 打开 `http://127.0.0.1:8000/html`
- 上传一份 PDF 或 Markdown 文档
- 观察状态接口中的 `done_list / running_list`
 
### 2. 再演示普通问答
 
- 打开 `http://127.0.0.1:8001/html`
- 提问一个与文档内容强相关的问题
- 观察回答与 SSE 输出
 
## 当前重构状态
 
- 已完成双服务双端口入口恢复
- 已完成接口入口统一收敛到 `app/api`
- 已完成查询链能力层下沉
- 已完成导入链能力层下沉
 
## 当前已知注意事项
 
- 运行前必须准备完整 `.env`
- 本项目较重，首次加载本地模型耗时较长
- WebSearch 依赖 DashScope MCP 配置
- 如果系统 Python 环境缺少 `fastapi` 等依赖，请务必使用 `.venv` 或 `uv run`
 
## 参考文档
 
- 架构说明：`docs/architecture.md`


保留现有导入流程与查询流程的可运行能力，并统一收口到 `app/process`
- 保留导入服务与查询服务独立运行、独立端口的原始语义
- 将接口入口统一收敛到 `app/api`，但仍保持两个独立服务
- 使用 `api / infra / shared / rag / process` 做收敛，而不过度增加中间层
 
## 当前分层
 
### 服务入口
 
- `app/api/http/import_server.py`
  - 导入服务独立入口
  - 默认端口 `8000`
 
- `app/api/http/query_server.py`
  - 查询服务独立入口
  - 默认端口 `8001`
 
### API 层
 
- `app/api/http/import_server.py`
  - 使用 `@app.get / @app.post` 直接定义导入接口
  - 在同文件内直接处理上传、后台任务与状态查询
 
- `app/api/http/query_server.py`
  - 使用 `@app.get / @app.post` 直接定义查询接口与 SSE
  - 在同文件内直接处理会话、查询执行与历史记录
 
- `app/api/schemas`
  - API 输入输出模型
  - 仅保留请求与响应数据结构
 
### Infra 层
 
- `app/infra/config/settings.py`
  - 读取导入服务和查询服务的端口、名称、环境等配置
 
- `app/infra/config`
  - 作为配置统一出口，对外优先通过包级导出访问 `settings`、`infra_config` 及各类配置别名
 
- `app/infra/llm/providers.py`
  - 聚合 ChatModel、Embedding、Reranker 的获取方式
 
- `app/infra/vectorstore/milvus_gateway.py`
  - 聚合 Milvus 客户端、混合检索请求、按 chunk_id 回查
 
- `app/infra/persistence/history_repository.py`
  - 聚合历史对话查询、写入、清空等能力
 
- `app/infra/object_storage/minio_gateway.py`
  - 聚合 MinIO 客户端与桶配置
 
- `app/infra/document_parse/mineru_gateway.py`
  - 聚合 MinerU 文档解析服务配置出口
 
- `app/infra/websearch/dashscope_gateway.py`
  - 聚合 DashScope WebSearch MCP 的连接与调用参数
 
- 该层职责是对外部系统做正式门面封装
  - 不是简单把旧代码再包一层
  - 上层 `api / process / rag` 只依赖这里暴露的稳定出口
 
### Resources 层
 
- `app/resources/prompts`
  - 存放查询改写、答案生成、图片总结等提示词模板
  - 属于应用运行资源，不放入 `shared` 或根目录
 
### Shared 层
 
- `app/shared/config`
  - 原始配置对象与环境变量读取
 
- `app/shared/runtime`
  - 日志、提示词加载等运行时公共能力
 
- `app/shared/model`
  - Embedding、LLM、Reranker 等模型基础工具
 
- `app/shared/clients`
  - Milvus、Mongo、MinIO 等底层客户端工具
 
- `app/shared/utils`
  - SSE、任务状态、路径处理等通用工具
 
- `app/shared/tool`
  - 下载脚本等辅助工具
 
### 流程编排层
 
- `app/process/import_/*`
  - 保留原导入图与节点
 
- `app/process/query/*`
  - 保留原查询图与节点
 
### RAG 能力层
 
- `app/rag/import_`
  - 对应导入域能力
  - 文件按导入步骤组织，例如 `entry_service.py`、`pdf_parse_service.py`、`split_service.py`
 
- `app/rag/query`
  - 对应查询域能力
  - 文件按查询节点职责组织，例如 `item_name_confirm_service.py`、`search_embedding_service.py`、`rrf_service.py`、`answer_output_service.py`
 
## 调用关系图
 
### 导入链
 
```text
HTTP Request
  -> app/api/http/import_server.py
  -> process/import_/agent/main_graph.py
  -> process/import_/agent/nodes/node_entry.py
  -> rag/import_/entry_service.py
  -> process/import_/agent/nodes/node_pdf_to_md.py
  -> rag/import_/pdf_parse_service.py
  -> process/import_/agent/nodes/node_md_img.py
  -> rag/import_/markdown_image_service.py
  -> process/import_/agent/nodes/node_document_split.py
  -> rag/import_/split_service.py
  -> process/import_/agent/nodes/node_item_name_recognition.py
  -> rag/import_/item_name_service.py
  -> process/import_/agent/nodes/node_bge_embedding.py
  -> rag/import_/embedding_service.py
  -> process/import_/agent/nodes/node_import_milvus.py
  -> rag/import_/index_service.py
  -> infra/vectorstore/milvus_gateway.py
```
 
- `import_server.py` 负责接收上传请求、保存文件、生成 `task_id`、启动后台任务与状态查询
- `process/import_` 负责导入流程编排与节点顺序控制
- `rag/import_` 负责每个导入步骤的具体实现
- `infra/*` 负责调用 Milvus、模型服务、对象存储等底层依赖
 
### 查询链
 
```text
HTTP Request
  -> app/api/http/query_server.py
  -> process/query/agent/main_graph.py
  -> process/query/agent/nodes/node_item_name_confirm.py
  -> rag/query/item_name_confirm_service.py
  -> process/query/agent/nodes/node_search_embedding.py
  -> rag/query/search_embedding_service.py
  -> process/query/agent/nodes/node_search_embedding_hyde.py
  -> rag/query/search_embedding_hyde_service.py
  -> process/query/agent/nodes/node_web_search_mcp.py
  -> rag/query/web_search_service.py
  -> process/query/agent/nodes/node_rrf.py
  -> rag/query/rrf_service.py
  -> process/query/agent/nodes/node_rerank.py
  -> rag/query/rerank_service.py
  -> process/query/agent/nodes/node_answer_output.py
  -> rag/query/answer_output_service.py
  -> infra/llm/providers.py
  -> infra/vectorstore/milvus_gateway.py
  -> infra/persistence/history_repository.py
```
 
- `query_server.py` 负责普通问答、流式问答、历史记录、会话管理、图调用与 SSE 收尾
- `process/query` 负责查询图编排与节点流转
- `rag/query` 负责按节点职责实现商品确认、检索、HyDE、联网检索、RRF、重排和答案生成
- `infra/*` 负责调用 LLM、Milvus、Mongo 等底层能力
 
## 当前结构说明
 
- `api`
  - 只负责接口定义、请求参数与响应返回
  - 不再额外包 `application` 转发层
 
- `process/import_ / process/query`
  - 负责流程编排
  - 保留原来 LangGraph 主链
 
- `rag/import_ / rag/query`
  - 负责节点背后的具体能力实现
  - 将复杂逻辑从节点中继续下沉
 
## 能力下沉情况
 
### 查询链
 
- 已下沉到 `app/rag/query` 的能力包括：
  - `item_name_confirm_service.py`
  - `search_embedding_service.py`
  - `search_embedding_hyde_service.py`
  - `web_search_service.py`
  - `rrf_service.py`
  - `rerank_service.py`
  - `answer_output_service.py`
 
- 已瘦身的查询节点包括：
  - `node_item_name_confirm`
  - `node_search_embedding`
  - `node_search_embedding_hyde`
  - `node_web_search_mcp`
  - `node_rrf`
  - `node_rerank`
  - `node_answer_output`
 
### 导入链
 
- 已下沉到 `app/rag/import_` 的能力包括：
  - `entry_service.py`
  - `split_service.py`
  - `embedding_service.py`
  - `index_service.py`
  - `item_name_service.py`
  - `pdf_parse_service.py`
  - `markdown_image_service.py`
 
- 已瘦身的导入节点包括：
  - `node_entry`
  - `node_document_split`
  - `node_bge_embedding`
  - `node_import_milvus`
  - `node_item_name_recognition`
  - `node_pdf_to_md`
  - `node_md_img`
 
## 启动建议
 
```bash
python -m app.api.http.import_server
python -m app.api.http.query_server
```
 
或
 
```bash
uvicorn app.api.http.import_server:app --host 0.0.0.0 --port 8000
uvicorn app.api.http.query_server:app --host 0.0.0.0 --port 8001
```