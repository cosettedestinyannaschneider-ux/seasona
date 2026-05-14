# 拾季 Seasona

拾季是一个面向农产品的垂直电商课程项目，后端使用 FastAPI，前端使用 Vue 3 + Vite。项目包含买家、卖家、管理员三类角色，并在普通商城能力之外提供“小拾”AI 辅助导购入口。

## 项目结构

- `app/`：FastAPI 应用，包含配置、路由、SQLAlchemy 模型、Pydantic Schema 和业务服务。
- `frontend/vite/`：Vue 3 + Vite 前端源码。
- `frontend/dist/`：前端生产构建产物，由 Nginx 容器读取。
- `deploy/nginx/`：Nginx 反向代理、静态页面和上传媒体访问配置。
- `media/`：本地上传文件目录，运行时挂载，不进入 Git。
- `docs/data-model.md`：数据模型与状态机说明。
- `docs/schema.sql`：当前模型对应的 PostgreSQL 建表参考脚本。
- `docs/http-tests.http`：接口调试示例。

## 核心能力

- 买家：注册登录、商品浏览、商城搜索、小拾 AI 导购、购物车、下单支付、订单查询、退款/争议、评价、钱包与流水、地址簿、资料维护。
- 卖家：注册登录、资质审核材料提交、店铺资料、商品/SPU/SKU 管理、库存维护、订单履约、退款处理、评价回复、收益与流水。
- 管理员：用户启用/禁用、商家资质审核、商品审核/下架、分类管理、争议处理、搜索索引重建。
- 搜索：Meilisearch 统一承担首页搜索和 AI 食材匹配。
- AI：LLM 负责多轮意图确认与食材提取，搜索结果由后端结构化为商品卡片返回。

## 环境准备

1. 复制 `.env.example` 为 `.env`。
2. 填写 PostgreSQL、Redis、Meilisearch、JWT、LLM、Embedding 等配置。
3. 根据 `docs/schema.sql` 在 PostgreSQL 中手动建表。
4. 手动准备至少一个管理员账号。管理员不开放公网注册。
5. 安装后端依赖：

```bash
python -m pip install -r requirements.txt
```

6. 安装前端依赖：

```bash
cd frontend/vite
npm install
```

## 本地开发启动

后端：

```bash
uvicorn main:app --reload
```

前端：

```bash
cd frontend/vite
npm run dev
```

Vite 开发环境会把后端 `/api` 和 `/media` 代理到 `http://127.0.0.1:8000`。可以通过`http://127.0.0.1:8000/docs` 访问Swagger查看接口，如果前端需要访问其他后端地址，可以在 `frontend/vite/.env` 中设置 `VITE_API_BASE_URL`。前端默认通过`http://localhost:5173` 访问

## Docker 部署

项目提供 `docker-compose.yml`，包含：

- `api`：FastAPI 服务。
- `postgres`：PostgreSQL。
- `redis`：Redis，已开启 AOF 持久化和密码。
- `meilisearch`：Meilisearch 搜索服务。
- `nginx`：生产入口，负责前端静态文件、接口反代和媒体文件访问。

启动前请确认 `.env` 中至少填写：

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `MEILI_MASTER_KEY`
- `SEASONA_DATABASE_URL`
- `SEASONA_REDIS_URL`
- `SEASONA_MEILISEARCH_URL`
- `SEASONA_MEILISEARCH_API_KEY`
- `SEASONA_JWT_SECRET_KEY`

生产构建前端：

```bash
cd frontend/vite
npm run build
```

然后启动：

```bash
docker compose up --build
```

Nginx 会从 `frontend/dist` 读取前端页面，从 `media/` 读取上传文件，并把 `/api/` 转发给 FastAPI。也就是说，本地使用 Vite 开发服务器时 Nginx 不参与；准备以 Docker 或服务器方式部署时，Nginx 才是浏览器访问的统一入口。

## 搜索与 AI

- Meilisearch 索引名默认是 `seasona_products`，可通过 `SEASONA_MEILISEARCH_INDEX` 修改。
- Docker 中如设置了 `MEILI_MASTER_KEY`，`SEASONA_MEILISEARCH_API_KEY` 应填写同一个值。
- 首页搜索和小拾食材匹配共用同一个商品索引。
- 商品审核通过、下架、商家禁用等业务操作会同步刷新搜索派生数据。
- 如需手动重建索引，管理员可调用：`POST /api/v1/admin/search/reindex`。
- FastAPI 不直接保存向量；Embedding 配置用于 Meilisearch REST embedder。

## 认证与权限

- 买家注册：`POST /api/v1/auth/buyer/register`
- 卖家注册：`POST /api/v1/auth/seller/register`
- 买家登录：`POST /api/v1/auth/buyer/login`
- 卖家登录：`POST /api/v1/auth/seller/login`
- 管理员登录：`POST /api/v1/auth/admin/login`
- 登出：`POST /api/v1/auth/logout`

买家、卖家登录支持用户名、手机号或邮箱。管理员只使用管理员用户名登录。密码使用 Argon2id 哈希，不保留旧哈希兼容路径。

## 订单与资金原则

- 待支付订单只对买家可见，卖家在付款前看不到订单。
- 创建订单会锁定库存；20 分钟未付款会在后续查询/操作中惰性过期并释放库存。
- 付款时扣减买家可用余额并转入冻结余额。
- 买家确认收货后，冻结资金结算给卖家。
- 未发货订单可直接取消；发货后进入退款流程。
- 退款由卖家先处理，三天未处理会惰性升级为争议，由管理员裁决。
- 钱包流水只展示实际落地的资金变化，不展示冻结和解冻的内部中间状态。

## 上传文件

- 头像、店铺 Logo、商家资质图、商品图都存入 `media/`。
- 数据库只保存文件 URL，不直存图片二进制。
- Docker 中 `api` 和 `nginx` 都挂载同一个 `./media`，因此上传后可由 Nginx 直接访问。

## 验证命令

后端：

```bash
python -m compileall app main.py
python -c "from main import app; print(len(app.openapi()['paths']))"
python -m pip check
```

前端：

```bash
cd frontend/vite
npm run build
```

## 注意事项

- `.env`、上传文件、依赖目录和构建产物不会进入 Git。
- `docs/schema.sql` 是当前代码模型的建表参考，不是迁移系统。
- 前端可以隐藏按钮，但权限边界以后端角色检查为准。
- 交易时不能信任搜索索引中的价格、库存或状态，最终仍回 PostgreSQL 校验。
