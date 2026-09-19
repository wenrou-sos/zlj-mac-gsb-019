# 船舶维修坞期管理平台 (Shipyard Dock Management)

面向修船厂的坞期管控系统：维修项目 WBS 拆分、施工队排班、备件到货跟踪、坞位占用安排；
**当备件延期或缺件、前置任务受阻时，系统会自动标记受影响任务并沿依赖链顺排计划**，
同时联动项目完工日、坞位档期与施工队排班。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Vite + Vue Router + Axios（Nginx 托管） |
| 后端 | FastAPI + SQLAlchemy 2 + Pydantic v2 |
| 数据库 | PostgreSQL 16（测试/本地无 PG 时自动回退 SQLite） |

## 一键启动

```bash
chmod +x start.sh stop.sh
./start.sh            # Docker Compose: PostgreSQL + FastAPI + Vue
# 前端 http://localhost:8080   后端文档 http://localhost:8000/docs

./start.sh --local    # 无 Docker 时本机直跑（SQLite + Vite）
./start.sh --test     # 只跑后端测试
./stop.sh             # 停止容器
```

首次启动会自动建表并生成演示项目 **P-2026-009 远洋之星轮坞修**：
其中“尾轴密封组件”缺件、“中间轴承”延期到货，可直接看到 T4→T5→T7 任务链被自动标红/顺排。
在页面上把缺件改为“已到货”，即可看到受阻任务自动恢复、计划重排。

## 核心业务规则

排程引擎见 `backend/app/services/scheduling.py`：

1. **拓扑排序**：按任务“完成-开始”依赖关系前向排程；
2. 每个任务最早开工日 = `max(期望开工日, 前置完工日, 备件最晚到货日)`；
3. **缺件**（`shortage` 或无 ETA）→ 任务标记 `blocked`；其所有下游任务级联 `blocked`，
   原因写入 `affected_reason`（如“前置任务 T4 受阻”“备件延期到货（预计 …）”）；
4. **延期到货**（ETA 晚于需求日）→ 任务顺移到 ETA 开工，`delay_days` 沿依赖链向下游传导；
5. 重算后联动更新：**项目计划完工日/整体延期天数、坞位占用结束日、施工队排班起止日**；
6. **坞位冲突**：同坞档期重叠时安排坞位返回 409，并提供冲突查询接口。

## 主要 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/dashboard` | 仪表盘统计 + 受阻任务 + 坞位档期 |
| CRUD | `/api/docks` `/api/teams` | 坞位、施工队 |
| CRUD | `/api/projects` | 维修项目 |
| POST | `/api/projects/{id}/tasks` | WBS 拆分（支持 `depends_on`、`team_ids`，自动重排） |
| PUT | `/api/projects/{id}/tasks/{tid}` | 更新任务（状态/工期/开工日，触发重排） |
| POST | `.../tasks/{tid}/dependencies` `/assignments` | 依赖与排班 |
| CRUD | `/api/projects/{id}/parts`、`PUT /api/parts/{id}` | 备件到货跟踪（**更新即触发传播重算**） |
| POST | `/api/projects/{id}/occupancies` | 坞位占用（重叠拒绝） |
| POST | `/api/projects/{id}/recalc` | 手动重排 |
| GET | `/api/projects/{id}/conflicts` | 坞位冲突报告 |

交互式文档：启动后访问 `http://localhost:8000/docs`。

## 测试

```bash
cd backend
python3 -m pip install -r requirements.txt
SHIPYARD_SEED_DEMO=0 python3 -m pytest tests/ -v
```

`tests/test_workflow.py` 为端到端业务测试：建坞位/施工队/项目 → 拆任务链 →
制造缺件断言阻断与级联 → 备件到货断言恢复 → 延期到货断言顺排天数 → 坞位冲突 409。
测试使用 SQLite 临时库（开启外键约束），无需 PostgreSQL。

## 目录结构

```
shipyard/
├── docker-compose.yml         # db + backend + frontend 一键编排
├── start.sh / stop.sh
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py            # FastAPI 入口 + 演示数据
│   │   ├── core/              # 配置 / 数据库
│   │   ├── models/            # SQLAlchemy 模型
│   │   ├── schemas/           # Pydantic 模型
│   │   ├── services/
│   │   │   └── scheduling.py  # 拓扑排程 + 缺件/延期传播引擎
│   │   └── api/routers.py     # 全部 REST 接口
│   └── tests/                 # pytest 端到端测试
└── frontend/
    ├── Dockerfile + nginx.conf
    └── src/
        ├── views/             # 仪表盘 / 项目 / 项目详情 / 施工队 / 坞位
        ├── components/GanttChart.vue
        └── api/               # axios 接口封装
```

> 生产环境建议把建表替换为 Alembic 迁移，并把数据库口令改为环境变量/密钥管理。
