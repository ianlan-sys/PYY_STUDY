# Wixi App LLM — 后端（微信云托管 / FastAPI）

Python 学习小程序的后端服务，FastAPI + SQLite + DeepSeek。通过微信云托管以 Docker 方式部署。

> 注意：本仓库虽由「Flask 模板」创建，但实际运行的是 **FastAPI**。云托管按 Dockerfile 构建，不依赖框架类型。

## 结构

```
main.py                 FastAPI 入口（app）
database.py             SQLite 初始化与连接（init_db 自动建表）
models.py               数据模型
routers/                ai / assessment / users / progress / sessions / admin / lessons 路由
services/               deepseek（AI 调用）、prompts
admin/static/           后台管理静态页（挂载在 /admin-ui）
Dockerfile              云托管构建文件，监听端口 80
container.config.json   模板初始部署的服务设置（端口 80）
```

## 部署到微信云托管

1. 代码推送到本仓库（已与云托管关联）后，云托管自动触发构建与发布。
2. 在云托管「服务设置」中确认 **监听端口 = 80**（与 Dockerfile 的 `EXPOSE 80` 一致）。
3. 配置以下**环境变量**（不要写进代码/仓库）：

   | 变量 | 说明 |
   |---|---|
   | `DEEPSEEK_API_KEY` | DeepSeek 真实密钥（**必填**） |
   | `DEEPSEEK_BASE_URL` | 默认 `https://api.deepseek.com` |
   | `ALLOWED_ORIGINS` | CORS 允许来源，默认 `*` |
   | `JWT_SECRET` | 后台登录 JWT 签名密钥（**改成随机串**） |
   | `ADMIN_USERNAME` | 后台用户名，默认 `admin` |
   | `ADMIN_PASSWORD_HASH` | 后台密码 bcrypt 哈希 |

4. **数据持久化（重要）**：应用用 SQLite，库文件在 `/data/app.db`。容器磁盘是临时的，重启/缩容到 0 会丢数据。如需持久化，在云托管挂载「文件存储(NFS)」到 `/data`；或改用云数据库 MySQL。

## 健康检查

`GET /health` → `{"status": "ok"}`

## 本地开发

```bash
pip install -r requirements.txt
cp .env.example .env   # 填入真实密钥
uvicorn main:app --reload --port 8000
```

小程序前端 `miniapp/utils/api.js` 的 `BASE_URL` 需改为云托管分配的服务域名。
