# KnowLoop 本地容器部署

以下是需要真实模型与服务的部署流程，不是免配置演示。先按 README 准备三个模型目录。命令从仓库根目录执行。

```powershell
Copy-Item .env.compose.example .env.compose
# 编辑 .env.compose：填入 DASHSCOPE_API_KEY 和 ADMIN_API_TOKEN。
# 确认 ACTIVE_SCENARIO_ID=logistics_after_sales，模型路径对应 /app/models 下的目录。
notepad .env.compose

docker compose --env-file .env.compose up -d mysql redis etcd minio milvus
docker build -f Dockerfile.base -t localhost/knowforge-rag-platform-base:py312 .
docker compose --env-file .env.compose build api

# 首次入库：新建版本，通过质量门禁后激活；不删除已有集合。
docker compose --env-file .env.compose run --rm api python scripts/rebuild_kb_version.py --scenario logistics_after_sales --new-version --force --quality-gate --activate --description "initialize synthetic logistics knowledge"
docker compose --env-file .env.compose up -d api
docker compose --env-file .env.compose ps
```

每条命令成功后再执行下一条；依赖启动后应等待健康检查通过。构建基础镜像会下载大型 Python/深度学习依赖，需要足够磁盘空间与网络访问。本次未执行容器部署，具体镜像可用性和依赖解析以本机实测为准。

已有 `.env.compose` 时不要覆盖，直接修改现有文件。MySQL 的 `MYSQL_PASSWORD` 必须与数据库实际密码一致。Compose 的默认开发密码只适用于隔离的本机环境；如修改密码，需同时修改数据库环境、API 配置与健康检查。若使用原有数据库，遵循原部署的账户与数据备份流程。

宿主机运行 API 时改用 `.env.local.example`，将 MySQL 端口等配置改成 Docker 对外发布端口。示例 Compose 的 MySQL 端口为 `13307`，本地示例文件默认 `3306`，需手动对齐。再安装依赖、执行同一入库命令并运行 `python app.py`。

`/api/docs` 是接口文档；`/docs/` 在没有可选 MkDocs 站点时跳转到接口文档。若要构建简要项目说明站点，可以运行 `mkdocs build`。课程维护脚本、通用发布验收及企业叠加数据脚本保留作源代码参考，依赖未随仓库分发的原平台资料，不属于上述物流启动流程。
