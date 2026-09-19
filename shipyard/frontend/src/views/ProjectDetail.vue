<template>
  <div v-if="project">
    <h2 class="page-title">
      {{ project.name }}
      <span class="badge" :class="project.status" style="margin-left:10px">{{ projectStatus(project.status) }}</span>
    </h2>
    <p class="page-sub">
      {{ project.code }} · {{ project.ship_name }}（{{ project.imo || '无 IMO' }}）
      ｜ 进坞 {{ fmt(project.planned_start) }} ｜ 计划完工 {{ fmt(project.planned_end) }}
      ｜ 基线完工 {{ fmt(project.baseline_end) }}
      <strong :class="{ reason: project.delay_days > 0 }">
        {{ project.delay_days ? `｜整体延期 ${project.delay_days} 天` : '｜计划正常' }}
      </strong>
    </p>

    <div class="toolbar">
      <button class="btn" @click="recalc">🔄 重新编排计划</button>
      <button v-if="project.status !== 'completed'" class="btn ghost" @click="complete">标记项目完工</button>
      <router-link to="/projects" class="btn ghost">← 返回列表</router-link>
      <span v-if="lastResult" class="muted">
        重排完成：受阻 {{ lastResult.blocked_tasks.length }} 项，顺移 {{ lastResult.shifted_tasks.length }} 项
      </span>
    </div>

    <div class="panel" v-if="conflictReport.length">
      <h3 class="reason">坞位档期冲突</h3>
      <ul>
        <li v-for="c in conflictReport" :key="c.occupancy_id" class="reason">
          坞位 {{ c.dock_id }} 与项目 {{ c.other_project_id }} 占用期重叠（{{ fmt(c.start_date) }} ~ {{ fmt(c.end_date) }}）
        </li>
      </ul>
    </div>

    <!-- 甘特图 -->
    <div class="panel">
      <h3>任务排程甘特图（红框 = 延期，红条 = 受阻）</h3>
      <GanttChart :items="ganttItems" />
    </div>

    <div class="panel">
      <h3>WBS 维修任务拆分</h3>
      <div class="form-grid">
        <label class="field">任务编号<input v-model="taskForm.code" placeholder="T8" /></label>
        <label class="field">任务名称<input v-model="taskForm.name" placeholder="舵系检修" /></label>
        <label class="field">阶段<input v-model="taskForm.phase" placeholder="轮机/船体/涂装" /></label>
        <label class="field">计划开工<input type="date" v-model="taskForm.planned_start" /></label>
        <label class="field">工期(天)<input type="number" min="1" v-model.number="taskForm.duration_days" /></label>
        <label class="field">前置任务
          <select v-model="taskForm.depends_on" multiple size="1" style="height:34px">
            <option v-for="t in project.tasks" :key="t.id" :value="t.id">{{ t.code }}</option>
          </select>
        </label>
        <label class="field">施工队
          <select v-model="taskForm.team_ids" multiple size="1" style="height:34px">
            <option v-for="t in teams" :key="t.id" :value="t.id">{{ t.code }} {{ t.name }}</option>
          </select>
        </label>
      </div>
      <button class="btn" @click="addTask">添加任务并重排</button>

      <table style="margin-top:14px">
        <thead>
          <tr>
            <th>编号</th><th>名称/阶段</th><th>状态</th><th>进度</th>
            <th>计划周期</th><th>延期</th><th>前置</th><th>施工队</th><th>受影响原因</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in project.tasks" :key="t.id">
            <td class="nowrap">{{ t.code }}</td>
            <td>{{ t.name }}<div class="muted">{{ t.phase }}</div></td>
            <td><span class="badge" :class="t.status">{{ taskStatus(t.status) }}</span></td>
            <td>
              <select :value="t.status" class="sm" @change="setStatus(t, $event.target.value)" style="padding:2px 4px">
                <option value="pending">未开始</option>
                <option value="in_progress">进行中</option>
                <option value="done">完工</option>
              </select>
              <div class="muted">{{ t.progress }}%</div>
            </td>
            <td class="nowrap">{{ fmt(t.planned_start) }}<br />~ {{ fmt(t.planned_end) }}</td>
            <td :class="{ reason: t.delay_days > 0 }">{{ t.delay_days ? `${t.delay_days}天` : '—' }}</td>
            <td>{{ (t.depends_on || []).map((d) => d.code).join(', ') || '—' }}</td>
            <td>
              <span v-for="a in t.assignments" :key="a.id" style="margin-right:6px; white-space:nowrap">
                {{ a.team?.code }}
                <a href="#" @click.prevent="unassign(t, a)" title="移除排班">✕</a>
              </span>
              <select @change="assign(t, $event.target.value); $event.target.value=''" style="padding:2px 4px">
                <option value="">+ 派队</option>
                <option v-for="tm in availableTeams(t)" :key="tm.id" :value="tm.id">{{ tm.code }}</option>
              </select>
            </td>
            <td class="reason" style="max-width:240px">{{ t.affected_reason || '—' }}</td>
            <td class="nowrap">
              <button class="btn sm danger" @click="removeTask(t)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 备件到货跟踪 -->
    <div class="panel">
      <h3>备件到货跟踪</h3>
      <div class="form-grid">
        <label class="field">备件编号<input v-model="partForm.code" /></label>
        <label class="field">名称<input v-model="partForm.name" /></label>
        <label class="field">供应商<input v-model="partForm.supplier" /></label>
        <label class="field">数量<input type="number" min="1" v-model.number="partForm.quantity" /></label>
        <label class="field">需求到货日<input type="date" v-model="partForm.required_date" /></label>
        <label class="field">预计到货 ETA<input type="date" v-model="partForm.eta" /></label>
        <label class="field">状态
          <select v-model="partForm.status">
            <option value="pending">待采购</option>
            <option value="in_transit">运输中</option>
            <option value="delayed">延期</option>
            <option value="shortage">缺件</option>
            <option value="arrived">已到货</option>
          </select>
        </label>
        <label class="field">需求任务
          <select v-model="partForm.task_id">
            <option :value="null">不关联</option>
            <option v-for="t in project.tasks" :key="t.id" :value="t.id">{{ t.code }} {{ t.name }}</option>
          </select>
        </label>
      </div>
      <button class="btn" @click="addPart">登记备件</button>

      <table style="margin-top:14px">
        <thead>
          <tr>
            <th>编号</th><th>名称</th><th>供应商</th><th>数量</th><th>需求任务</th>
            <th>需求到货</th><th>ETA</th><th>实际到货</th><th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in project.parts" :key="p.id">
            <td>{{ p.code }}</td><td>{{ p.name }}</td><td>{{ p.supplier || '—' }}</td><td>{{ p.quantity }}</td>
            <td>{{ taskCode(p.task_id) }}</td>
            <td>{{ fmt(p.required_date) }}</td>
            <td :class="{ reason: isLate(p) }">{{ fmt(p.eta) }}</td>
            <td>{{ fmt(p.arrived_date) }}</td>
            <td>
              <select :value="p.status" @change="updatePart(p, { status: $event.target.value })" style="padding:2px 4px">
                <option value="pending">待采购</option>
                <option value="in_transit">运输中</option>
                <option value="delayed">延期</option>
                <option value="shortage">缺件</option>
                <option value="arrived">已到货</option>
              </select>
              <input
                type="date" class="sm" :value="p.eta || ''" style="margin-top:4px"
                @change="updatePart(p, { eta: $event.target.value })"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 坞位占用 -->
    <div class="panel">
      <h3>坞位占用安排</h3>
      <table style="margin-bottom:12px">
        <thead><tr><th>坞位</th><th>开始</th><th>结束</th><th>状态</th></tr></thead>
        <tbody>
          <tr v-for="o in project.occupancies" :key="o.id">
            <td>{{ o.dock?.code }} {{ o.dock?.name }}</td>
            <td>{{ fmt(o.start_date) }}</td><td>{{ fmt(o.end_date) }}</td>
            <td><span class="badge" :class="o.status">{{ occStatus(o.status) }}</span></td>
          </tr>
          <tr v-if="!project.occupancies.length"><td colspan="4" class="muted">尚未安排坞位</td></tr>
        </tbody>
      </table>
      <div class="toolbar">
        <select v-model="occForm.dock_id">
          <option :value="null">选择坞位</option>
          <option v-for="d in docks" :key="d.id" :value="d.id">{{ d.code }} {{ d.name }}</option>
        </select>
        <label class="field">开始<input type="date" v-model="occForm.start_date" /></label>
        <label class="field">结束<input type="date" v-model="occForm.end_date" /></label>
        <button class="btn" @click="addOccupancy">安排坞位（重叠将拒绝）</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref } from 'vue'
import api from '../api'
import GanttChart from '../components/GanttChart.vue'

const props = defineProps({ id: [String, Number] })
const notify = inject('notify')

const project = ref(null)
const teams = ref([])
const docks = ref([])
const lastResult = ref(null)
const conflictReport = ref([])

const today = () => new Date().toISOString().slice(0, 10)
const taskForm = reactive({
  code: '', name: '', phase: '', planned_start: today(), duration_days: 3,
  depends_on: [], team_ids: []
})
const partForm = reactive({
  code: '', name: '', supplier: '', quantity: 1,
  required_date: today(), eta: null, status: 'pending', task_id: null
})
const occForm = reactive({ dock_id: null, start_date: today(), end_date: today() })

const projectStatus = (s) => ({ planned: '计划中', in_progress: '进行中', completed: '已完工' })[s] || s
const taskStatus = (s) => ({ pending: '未开始', in_progress: '进行中', blocked: '受阻', done: '完工' })[s] || s
const occStatus = (s) => ({ reserved: '已预约', occupied: '占用中', released: '已释放' })[s] || s
const fmt = (d) => (d || '—').toString().slice(0, 10)

const ganttItems = computed(() =>
  (project.value?.tasks || []).map((t) => ({
    id: t.id, code: t.code, name: t.name,
    start: t.planned_start, end: t.planned_end,
    status: t.status, delay_days: t.delay_days
  }))
)

function taskCode(taskId) {
  return project.value.tasks.find((t) => t.id === taskId)?.code || '—'
}
function availableTeams(task) {
  return teams.value.filter((tm) => !task.assignments.some((a) => a.team_id === tm.id))
}
function isLate(p) {
  return p.eta && p.required_date && p.eta > p.required_date
}

async function refresh() {
  project.value = await api.project(props.id)
  conflictReport.value = await api.conflicts(props.id)
}

async function addTask() {
  if (!taskForm.code || !taskForm.name) return notify('请填写任务编号和名称', true)
  try {
    await api.createTask(props.id, { ...taskForm })
    notify(`任务 ${taskForm.code} 已加入，计划已自动重排`)
    Object.assign(taskForm, { code: '', name: '', phase: '', depends_on: [], team_ids: [] })
    await refresh()
  } catch (e) { notify(e.message, true) }
}

async function removeTask(t) {
  if (!confirm(`确定删除任务 ${t.code}？`)) return
  await api.deleteTask(props.id, t.id)
  notify('任务已删除并重排')
  await refresh()
}

async function setStatus(t, status) {
  try {
    await api.updateTask(props.id, t.id, { status })
    await refresh()
  } catch (e) { notify(e.message, true) }
}

async function assign(t, teamId) {
  if (!teamId) return
  try {
    await api.assignTeam(props.id, t.id, Number(teamId))
    notify(`已派 ${teams.value.find((x) => x.id === Number(teamId))?.code} 施工队，排班随计划联动`)
    await refresh()
  } catch (e) { notify(e.message, true) }
}

async function unassign(t, a) {
  await api.unassignTeam(props.id, t.id, a.id)
  await refresh()
}

async function addPart() {
  if (!partForm.code || !partForm.name) return notify('请填写备件编号和名称', true)
  try {
    await api.createPart(props.id, { ...partForm, eta: partForm.eta || null, supplier: partForm.supplier || null })
    notify('备件已登记，计划已按到货情况重算')
    Object.assign(partForm, { code: '', name: '', supplier: '', quantity: 1 })
    await refresh()
  } catch (e) { notify(e.message, true) }
}

async function updatePart(p, patch) {
  try {
    await api.updatePart(p.id, patch)
    notify('备件信息已更新，受影响任务已重新标记/顺排')
    await refresh()
  } catch (e) { notify(e.message, true) }
}

async function addOccupancy() {
  if (!occForm.dock_id) return notify('请选择坞位', true)
  try {
    await api.createOccupancy(props.id, { ...occForm })
    notify('坞位档期已锁定')
    await refresh()
  } catch (e) { notify(e.message, true) }
}

async function recalc() {
  lastResult.value = await api.recalc(props.id)
  notify('计划重排完成')
  await refresh()
}

async function complete() {
  await api.updateProject(props.id, { status: 'completed' })
  await refresh()
}

onMounted(async () => {
  [teams.value, docks.value] = await Promise.all([api.teams(), api.docks()])
  await refresh()
})
</script>
