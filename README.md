# 船舶维修坞期管理平台

面向船厂坞修场景的计划管理系统，支持**维修项目拆分（WBS）**、**施工队排班**、
**备件到货跟踪**与**坞位占用安排**。当发生**延期**或**缺件**时，系统自动标记
受影响任务并沿依赖链顺延计划，同时自动延伸项目坞期。

技术栈：**Vue 3 + Vite** ｜ **FastAPI + SQLAlchemy** ｜ **PostgreSQL**

---

## 功能一览

| 模块 | 能力 |
| --- | --- |
| 维修项目 | 创建坞修项目（船名、坞期起止、备注），项目状态自动流转（计划中/进行中/延期/已完成） |
| 任务拆分 | 项目拆分为多个维修子项，子项之间可建立“完成-开始”依赖关系；甘特图展示 |
| 施工队排班 | 维护施工队花名册（专业、人数），为任务排班；同一施工队日期重叠自动标记冲突 |
| 备件跟踪 | 登记任务所需备件、数量、ETA；ETA 晚于开工日自动阻塞任务并顺延至到货日，到货后自动解除 |
| 坞位占用 | 维护坞位并安排占用区间；冲突时自动改约到最近空闲窗口（也可选择直接报 409） |
| 自动调整 | 延期/缺件/坞位冲突 → 受影响任务自动标红、下游任务级联顺延、坞期自动延长，全程写审计日志 |

### 自动调整规则

1. **任务延期上报**：任务整体后移 N 天，其坞位占用同步平移；所有下游任务按
   “完成-开始”关系递归顺延（已完成任务不动）。
2. **备件延期/缺件**：ETA ≥ 任务开始日即标记 `缺件` 阻塞，任务顺延至到货日；
   依赖链上的任务标记 `等待上游`；备件登记到货后阻塞自动解除。
3. **施工队冲突**：同一施工队在两个日期重叠的任务上时，双方标记 `施工队冲突`。
4. **坞位冲突**：同一坞位占用区间重叠时默认自动改约到最近空闲窗口，并相应平移任务。
5. **坞期联动**：任何任务结束日超过项目结束日时，项目坞期自动顺延。

---

## 快速开始

### 方式一：Docker 一键启动（推荐）

```bash
./start.sh
```

启动后：

- 前端页面：<http://localhost:8000/>
- API 文档（Swagger）：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/health>

首次启动会自动建表并写入一份演示数据（远洋号坞修工程，含缺件阻塞场景）。
端口与账号可在 `.env` 中修改（首次运行自动从 `.env.example` 生成）。

其他命令：

```bash
./start.sh dev     # 本地开发模式（Vite 热更新 + SQLite，无需 Docker）
./start.sh test    # 运行后端测试
./start.sh logs    # 查看容器日志
./start.sh down    # 停止容器（保留数据）
./start.sh clean   # 停止并删除数据卷（清空数据）
```

### 方式二：分别手动启动

```bash
# 后端
cd backend
python -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements.txt
DATABASE_URL="postgresql+psycopg2://shipyard:shipyard@localhost:5432/shipyard" \
  SEED_ON_STARTUP=1 uvicorn app.main:app --reload

# 前端（另开终端）
cd frontend
npm install
npm run dev        # http://localhost:5173 ， /api 自动代理到 8000
```

---

## 测试

```bash
./start.sh test
# 或
cd backend
DATABASE_URL="sqlite:///:memory:" python -m pytest
```

测试覆盖：应用启动/健康检查、项目与任务 CRUD、依赖链校验、**延期级联顺延**、
**缺件阻塞与到货解除**、**施工队冲突**、**坞位冲突与自动改约**、坞期自动延长、
统计面板与调整日志（共 21 个用例，使用内存 SQLite，无需 PostgreSQL）。

---

## 主要 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/dashboard` | 总览统计（受阻任务数、延期备件数、坞位冲突数） |
| GET/POST | `/api/projects` | 项目列表/创建 |
| PATCH/DELETE | `/api/projects/{id}` | 更新/删除 |
| GET/POST | `/api/tasks` | 任务（可按 `project_id` 过滤） |
| PATCH | `/api/tasks/{id}` | 更新任务（进度、依赖、施工队） |
| POST | `/api/tasks/{id}/delay` | **上报延期，触发自动级联调整** |
| GET/POST | `/api/teams` | 施工队 |
| POST | `/api/teams/assign` | 为任务排班 |
| GET/POST | `/api/parts` | 备件 |
| PATCH | `/api/parts/{id}` | **更新 ETA / 登记到货，触发重排** |
| GET/POST | `/api/docks` | 坞位 |
| POST | `/api/docks/bookings` | **安排坞位占用，冲突自动改约** |
| GET | `/api/logs` | 自动调整审计日志 |

完整接口见 Swagger 文档 `/docs`。

---

## 目录结构

```
.
├── Dockerfile               # 多阶段构建：Node 构建前端 -> Python 单镜像
├── docker-compose.yml       # PostgreSQL + API（内置前端）
├── start.sh                 # 一键启动 / 开发 / 测试脚本
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 入口（建表、CORS、SPA 托管）
│   │   ├── models.py        # SQLAlchemy 模型
│   │   ├── schemas.py       # Pydantic 模型
│   │   ├── planner.py       # 自动重排引擎（阻塞标记/级联顺延/坞位冲突）
│   │   ├── serializers.py
│   │   ├── routers/         # projects / tasks / teams / parts / docks / dashboard
│   │   └── scripts/seed.py  # 演示数据
│   └── tests/               # pytest（21 个用例）
└── frontend/
    └── src/
        ├── App.vue
        ├── api.js
        └── components/      # 总览/项目/任务/备件/坞位/施工队/日志 七个视图
```

## 设计说明

- 任务阻塞原因以 JSON 存储在 `tasks.blockers`（键：`parts`/`team`/`dock`/`upstream`），
  前端逐条展示；重算逻辑集中在 `app/planner.py:recompute()`，任何写操作后统一刷新。
- 顺延只向未来移动计划，绝不提前；已完成任务不受任何自动调整影响。
- 生产数据库为 PostgreSQL；测试与本地开发可用 SQLite，ORM 层无 PG 专有语法。
