# 测试指南

本项目使用分层架构的后端测试套件。运行时依赖存放在 `requirements.txt` 中；本地测试和代码覆盖率工具存放在 `requirements-dev.txt` 中，该文件包含了 `requirements.txt` 并添加了 `pytest`、`pytest-cov`、`polyfactory` 以及 `freezegun`。

## 应提交至 Git 的内容

提交测试框架和源文件：

* `pytest.ini`
* `requirements-dev.txt`
* `test/conftest.py`
* `test/factories.py`
* `test/unit/`
* `test/integration/`
* `test/final_acceptance_test.py`

不要提交本地输出或运行时数据：

* `.env`, `.coverage`, `.coverage.*`, `htmlcov/`
* `__pycache__/`, `.pytest_cache/`, `pytest-cache-files-*/`
* `test/media/`, `media/`, 日志, IDE 配置文件, 虚拟环境
* `AGENTS.md`，这是本地贡献者/AI代理的指南

## 安装依赖

如果仅运行该应用程序，请使用生产环境依赖：

```bash
python -m pip install -r requirements.txt

```

如果在运行测试，请使用开发环境依赖：

```bash
python -m pip install -r requirements-dev.txt

```

## 测试命令

运行默认测试套件：

```bash
python -m pytest

```

这会运行单元测试以及任何可用的轻量级集成测试。如果没有配置 `SEASONA_TEST_DATABASE_URL`，将会跳过 PostgreSQL 集成测试。

仅运行单元测试：

```bash
python -m pytest -m unit

```

运行 PostgreSQL 集成测试：

```powershell
$env:SEASONA_TEST_DATABASE_URL="postgresql+psycopg://user:password@127.0.0.1:5432/seasona_test"
python -m pytest -m integration

```

只能使用专用的、一次性的测试数据库。集成测试夹具（fixture）会重新创建 `public` 模式（schema），因此绝对不要将 `SEASONA_TEST_DATABASE_URL` 指向开发环境或生产环境的数据。

生成测试覆盖率报告：

```bash
python -m pytest --cov=app --cov-report=term-missing --cov-report=html

```

HTML 格式的报告将写入 `htmlcov/` 目录，并且会被 Git 忽略。

## 测试分层

`test/unit/` 包含不访问数据库或网络的快速测试。这些测试涵盖了模式验证（schema validation）、令牌/密码行为、搜索和 AI 解析辅助函数，以及确定性的服务辅助函数。

`test/integration/` 包含由 PostgreSQL 支持的集成测试，涉及身份验证、目录状态变更、钱包记账、订单状态转换、退款、争议和评论。外部的 Redis、Meilisearch 以及 LLM 调用均会被替换为内存存储或基于猴子补丁（monkeypatch）的伪造实现（fakes）。

`test/final_acceptance_test.py` 保留为全环境验收脚本。在配置好 PostgreSQL、Redis、Meilisearch、文件上传以及可选的 AI 依赖之后，并在进行类似发布前的演示之前，请手动运行该脚本。