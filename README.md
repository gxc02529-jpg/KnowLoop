# KnowLoop

物流售后问答与知识治理项目。复用已有 KnowForge RAG 源码中的 FastAPI、LangChain、Milvus 混合检索、FAQ 直出、多租户范围与知识版本治理，新增 `logistics_after_sales` 场景包，把轨迹异常、破损理赔、退件改址组织成可检索的知识资料。

本仓库是公开开发版本。物流资料、FAQ 与评测问题均为自建合成样例，不代表真实承运商政策；没有接入真实运单、退款或赔付系统，也没有附带生产效果数据。

## 已有实现

- FAQ 高置信直出，文档 Dense + BM25 混合检索、重排与引用生成。
- 场景、租户、数据集、可见级别和角色过滤；知识版本 staged / active / archived 管理。
- 文档解析、切分、增量入库、质量门禁、离线检索评测和反馈收集。
- 会话历史、Redis 缓存及知识版本切换后的缓存失效。
- 物流场景：6 条 FAQ、3 篇合成政策文档、4 条离线评测问题。

多租户过滤属于代码能力，生产认证、租户身份绑定和外部业务系统集成仍需部署方完成。原有 8 个通用场景保留为复用参考，业务规则不能直接作为物流政策使用。

## 结构与复用

| 路径 | 职责 |
| --- | --- |
| `qa_core/retrieval/`、`pipeline/` | 检索、重排、回答和引用 |
| `qa_core/indexing/`、`governance/` | 入库、数据范围和版本治理 |
| `qa_core/api/`、`application/` | HTTP/WebSocket 接口和应用编排 |
| `scenarios/logistics_after_sales/` | 新增物流场景配置、FAQ 与合成文档 |
| `eval_sets/logistics_after_sales.json` | 物流回归输入与预期关键词，非已取得的评测结果 |
| `scripts/`、`tests/` | 入库、评测、训练脚本与测试 |

详细复用边界见 [REUSE_MAP.md](REUSE_MAP.md)。

## 部署前置条件

推荐 Python 3.12。应用启动会检查 MySQL、Milvus、模型文件、有效模型服务 Key、管理令牌以及已激活的知识版本，缺少这些条件不会启动。启用缓存时还必须配置 Redis。

需自行准备以下模型目录，仓库不分发权重：`models/bge-m3`、`models/bge-reranker-large`、`models/bert_intent_classifier_v1`。意图分类器必须包含训练权重、Tokenizer、配置和 `intent_labels.json`；只有原始 BERT 权重不够。可以使用自己已有的分类器，或准备 `models/bert-base-chinese` 后运行仓库训练脚本：

```powershell
python -m pip install -r requirements.txt
python scripts/intent/train_intent_bert.py --base-model models/bert-base-chinese --output models/bert_intent_classifier_v1 --train-data eval_sets/intent/train.jsonl --eval-data eval_sets/intent/eval.jsonl
```

训练数据是通用意图样例，物流效果需要另外验证。模型下载、训练、Docker 构建及完整 RAG 链路未在本次公开整理中重跑。

按 [INSTALL.md](INSTALL.md) 配置 `.env.compose`、启动依赖、构建并激活物流知识库，最后启动 API。示例数据库凭据只用于本机开发；不要直接用于公网部署。运行后访问首页 `http://localhost:8000/`、API 文档 `http://localhost:8000/api/docs`、健康检查 `http://localhost:8000/health`。

## 验证

不依赖模型与外部数据库的检查：

```powershell
python -m pytest -q tests/test_logistics_scenario.py tests/test_memory_history.py tests/test_answer_confidence.py tests/test_api_protection.py
```

配置模型、数据库及 active 版本后，再进行真实链路评测：

```powershell
python scripts/evaluate_core_chain.py --dataset eval_sets/logistics_after_sales.json --scenario logistics_after_sales --limit 4 --output reports/evaluation/logistics.json
python scripts/quality/check_evaluation_gate.py --report reports/evaluation/logistics.json
```

上述隔离单元测试与物流场景配置测试共 22 项通过。完整测试收集在当前机器缺少 `python-docx` 和 `pymilvus` 时失败；意图模型相关测试需要未随仓库分发的本地权重。全套测试、物流召回率和生产服务仍待完整环境验证。

`.env`、模型、数据库卷、日志和生成报告不提交。继承的课程工具及 `VERSIONING.md` / `V1_RELEASE_MANIFEST.json` 描述原通用平台的资料结构；相关课程文档、数据包与历史验收产物未包含，不能据此推断本仓库已经通过该平台的发布验收。
