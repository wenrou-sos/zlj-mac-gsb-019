"""计划编排引擎。

规则（完成-开始依赖 + 前向排程）：

1. 按任务依赖做拓扑排序；
2. 每个任务的最早开始日 = max(期望开始日, 各前置任务完成日, 备件到货日)；
3. 缺件（shortage）或备件没有任何到货时间 → 任务标记 blocked；
   前置任务 blocked 且本任务依赖它 → 本任务也 blocked，延期沿依赖链向下传播；
4. 延期到货（eta 晚于要求到货日）→ 顺排任务开始日并记录延期天数；
5. 项目结束日 / 坞位占用结束日 / 施工队排班日期随排程结果联动更新。
"""

from collections import defaultdict, deque
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import models as m


def _topological_order(tasks: list[m.Task]) -> list[m.Task]:
    by_id = {t.id: t for t in tasks}
    indegree: dict[int, int] = defaultdict(int)
    graph: dict[int, list[int]] = defaultdict(list)

    for t in tasks:
        for dep in t.depends_on:
            if dep.id in by_id:  # 只排本项目内的依赖
                graph[dep.id].append(t.id)
                indegree[t.id] += 1

    ready = deque(
        sorted(
            (t for t in tasks if indegree[t.id] == 0),
            key=lambda t: (t.sort_order, t.baseline_start, t.id),
        )
    )
    ordered: list[m.Task] = []
    while ready:
        t = ready.popleft()
        ordered.append(t)
        for nxt in sorted(graph[t.id], key=lambda i: (by_id[i].sort_order, i)):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(by_id[nxt])

    # 理论上不会有环（创建时不做环校验时的兜底）
    if len(ordered) != len(tasks):
        ordered.extend(t for t in tasks if t not in ordered)
    return ordered


def _part_readiness(task: m.Task) -> tuple[bool, bool, object]:
    """返回 (缺件/到货时间不明, 到货延期, 可开工所需的最晚备件到货日)。"""
    shortage = False
    late = False
    ready_date = None
    for part in task.parts:
        if part.status == m.PART_ARRIVED:
            ready = part.arrived_date
        elif part.status == m.PART_SHORTAGE:
            shortage = True
            continue
        else:
            # pending / in_transit / delayed：没有 eta 等同于无法承诺 → 缺件
            if part.eta is None:
                shortage = True
                continue
            ready = part.eta
            if part.status == m.PART_DELAYED or part.eta > part.required_date:
                late = True
        if ready is not None:
            ready_date = ready if ready_date is None else max(ready_date, ready)
    return shortage, late, ready_date


def recalculate_project(db: Session, project: m.Project) -> dict:
    """对单个项目做完整重排，返回受影响任务统计。"""
    tasks = list(project.tasks)
    if not tasks:
        project.planned_end = project.baseline_end
        project.delay_days = 0
        return {"blocked": [], "shifted": [], "planned_end": project.baseline_end}

    blocked_ids: list[int] = []
    shifted_ids: list[int] = []
    project_end = project.baseline_end

    for t in _topological_order(tasks):
        if t.status == m.TASK_DONE:
            finish = t.actual_end or t.planned_end
            project_end = finish if project_end is None else max(project_end, finish)
            continue

        reasons: list[str] = []

        # ---- 前置任务约束 ----
        start = t.baseline_start
        predecessor_blocked = False
        for dep in t.depends_on:
            pred_finish = dep.actual_end if dep.status == m.TASK_DONE else dep.planned_end
            if pred_finish is not None and pred_finish > start:
                start = pred_finish
            if dep.status == m.TASK_BLOCKED:
                predecessor_blocked = True
                reasons.append(f"前置任务 {dep.code}（{dep.name}）受阻")
            elif dep.delay_days > 0:
                reasons.append(f"前置任务 {dep.code} 延期 {dep.delay_days} 天")

        # ---- 备件约束 ----
        shortage, late, part_ready = _part_readiness(t)
        if shortage:
            reasons.append("所需备件缺件或到货时间不明")
        if part_ready is not None and part_ready > start:
            if late:
                reasons.append(
                    f"备件延期到货（预计 {part_ready.isoformat()}）"
                )
            start = part_ready

        end = start + timedelta(days=t.duration_days - 1)

        # ---- 落库排程结果 ----
        t.planned_start = start
        t.planned_end = end
        t.delay_days = max(0, (end - t.baseline_end).days)

        is_blocked = shortage or predecessor_blocked
        if is_blocked:
            t.status = m.TASK_BLOCKED
            blocked_ids.append(t.id)
        else:
            # 完工之外的任务，排程恢复正常即可回到 pending（进行中的保留）
            if t.status == m.TASK_BLOCKED:
                t.status = m.TASK_PENDING
            if t.delay_days > 0:
                shifted_ids.append(t.id)

        t.affected_reason = "；".join(reasons) if reasons else None

        for a in t.assignments:
            a.planned_start = t.planned_start
            a.planned_end = t.planned_end

        project_end = end if project_end is None else max(project_end, end)

    # ---- 项目级汇总（基线结束日取首次整体排程结果，之后保持稳定） ----
    project.planned_end = project_end
    if project.baseline_end is None:
        project.baseline_end = project_end
    project.delay_days = max(0, (project_end - project.baseline_end).days)

    # ---- 坞位占用档期联动 ----
    occupancy = db.scalar(
        select(m.DockOccupancy).where(
            m.DockOccupancy.project_id == project.id,
            m.DockOccupancy.status != m.OCCUPANCY_RELEASED,
        )
    )
    if occupancy is not None:
        baseline_start = project.planned_start
        if baseline_start and occupancy.end_date < project_end:
            occupancy.end_date = project_end

    db.flush()
    return {
        "blocked": blocked_ids,
        "shifted": shifted_ids,
        "planned_end": project_end,
        "delay_days": project.delay_days,
    }


def find_dock_conflicts(db: Session, project_id: int) -> list[dict]:
    """检查项目当前占用档期与同坞其他项目是否时间重叠。"""
    occupancy = db.scalar(
        select(m.DockOccupancy).where(m.DockOccupancy.project_id == project_id)
    )
    if occupancy is None:
        return []

    others = db.scalars(
        select(m.DockOccupancy).where(
            m.DockOccupancy.dock_id == occupancy.dock_id,
            m.DockOccupancy.project_id != project_id,
            m.DockOccupancy.status != m.OCCUPANCY_RELEASED,
        )
    ).all()

    conflicts = []
    for o in others:
        if o.start_date <= occupancy.end_date and occupancy.start_date <= o.end_date:
            conflicts.append(
                {
                    "occupancy_id": o.id,
                    "dock_id": o.dock_id,
                    "other_project_id": o.project_id,
                    "start_date": o.start_date,
                    "end_date": o.end_date,
                }
            )
    return conflicts
