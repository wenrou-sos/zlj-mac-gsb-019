<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api.js'

const projects = ref([])
const tasks = ref([])
const teams = ref([])
const selectedProject = ref(null)

const form = ref({
  name: '',
  start_date: '',
  end_date: '',
  depends_on: [],
  team_ids: [],
})
const delayDays = ref(2)

async function load() {
  projects.value = await api.listProjects()
  teams.value = await api.listTeams()
  if (!selectedProject.value && projects.value.length) {
    selectedProject.value = projects.value[0].id
  }
  if (selectedProject.value) {
    tasks.value = await api.listTasks(selectedProject.value)
  } else {
    tasks.value = []
  }
}

async function onProjectChange() {
  tasks.value = selectedProject.value
    ? await api.listTasks(selectedProject.value)
    : []
}

async function submit() {
  if (!selectedProject.value) return alert('请先创建并选择一个项目')
  if (!form.value.name || !form.value.start_date || !form.value.end_date) {
    return alert('请填写任务名称与起止日期')
  }
  await api.createTask({
    project_id: selectedProject.value,
    ...form.value,
  })
  form.value = { name: '', start_date: '', end_date: '', depends_on: [], team_ids: [] }
  await load()
}

async function reportDelay(task) {
  const days = Number(delayDays.value)
  if (!days || days <= 0) return alert('延期天数需大于 0')
  const result = await api.reportDelay(task.id, days)
  const names = result.affected_tasks.map((t) => `「${t.name}」`).join('、')
  alert(`已自动调整 ${result.count} 个任务：${names}`)
  await load()
}

async function setProgress(task, progress) {
  const status = progress >= 100 ? 'done' : progress > 0 ? 'in_progress' : 'pending'
  await api.updateTask(task.id, { progress: Number(progress), status })
  await load()
}

async function toggleDep(id, event) {
  const set = new Set(form.value.depends_on)
  event.target.checked ? set.add(id) : set.delete(id)
  form.value.depends_on = [...set]
}

async function toggleTeam(id, event) {
  const set = new Set(form.value.team_ids)
  event.target.checked ? set.add(id) : set.delete(id)
  form.value.team_ids = [...set]
}

async function assignExisting(task, teamId) {
  if (!teamId) return
  await api.assignTeam(task.id, Number(teamId))
  await load()
}

async function removeTask(id) {
  if (!confirm('删除该任务?')) return
  await api.deleteTask(id)
  await load()
}

function blockersJson(task) {
  try {
    return JSON.parse(task.blockers || '{}')
  } catch {
    return {}
  }
}

// ---- gantt projection ---------------------------------------------------
const ganttRange = computed(() => {
  if (!tasks.value.length) return null
  const starts = tasks.value.map((t) => t.start_date)
  const ends = tasks.value.map((t) => t.end_date)
  const min = starts.sort()[0]
  const max = ends.sort().reverse()[0]
  const d0 = new Date(min)
  const d1 = new Date(max)
  return { min, totalDays: Math.round((d1 - d0) / 86400000) + 1 }
})

function barStyle(task) {
  if (!ganttRange.value) return {}
  const d0 = new Date(ganttRange.value.min)
  const start = new Date(task.start_date)
  const end = new Date(task.end_date)
  const offset = Math.max(0, Math.round((start - d0) / 86400000))
  const width = Math.max(1, Math.round((end - start) / 86400000) + 1)
  return {
    marginLeft: `calc(${(offset / ganttRange.value.totalDays) * 100}% + 130px)`,
    width: `calc(${(width / ganttRange.value.totalDays) * 100}% - 130px)`,
  }
}

const statusLabel = {
  pending: '待开始',
  in_progress: '施工中',
  blocked: '受阻',
  done: '已完成',
}

function teamName(id) {
  return teams.value.find((t) => t.id === id)?.name || `#${id}`
}
function taskName(id) {
  return tasks.value.find((t) => t.id === id)?.name || `#${id}`
}

onMounted(load)
</script>

<template>
  <div class="panel">
    <div class="flex-between">
      <h2 style="margin: 0">维修项目拆分（WBS）与施工排班</h2>
      <div class="form-row" style="margin: 0">
        <label>选择项目</label>
        <select v-model="selectedProject" @change="onProjectChange">
          <option v-for="p in projects" :key="p.id" :value="p.id">
            {{ p.name }}（{{ p.start_date }} ~ {{ p.end_date }}）
          </option>
        </select>
      </div>
    </div>
  </div>

  <div class="panel">
    <h2>新增维修子项</h2>
    <div class="form-row">
      <label>任务名称</label>
      <input v-model="form.name" placeholder="如：螺旋桨拆装更换" />
      <label>开始</label>
      <input v-model="form.start_date" type="date" />
      <label>结束</label>
      <input v-model="form.end_date" type="date" />
    </div>
    <div class="form-row">
      <label>前置任务（完成后才能开始）：</label>
      <label v-for="t in tasks" :key="'dep' + t.id" style="font-weight: normal">
        <input type="checkbox" :checked="form.depends_on.includes(t.id)"
          @change="(e) => toggleDep(t.id, e)" /> {{ t.name }}
      </label>
    </div>
    <div class="form-row">
      <label>分配施工队：</label>
      <label v-for="team in teams" :key="'tm' + team.id" style="font-weight: normal">
        <input type="checkbox" :checked="form.team_ids.includes(team.id)"
          @change="(e) => toggleTeam(team.id, e)" />
        {{ team.name }}（{{ team.specialty }}）
      </label>
      <span v-if="!teams.length" class="muted">请先到「施工队」页创建</span>
    </div>
    <button class="btn" @click="submit">添加任务</button>
  </div>

  <div class="panel">
    <h2>任务计划（{{ tasks.length }}） — 延期上报自动级联调整</h2>
    <div class="form-row">
      <label>延期天数</label>
      <input v-model="delayDays" type="number" min="1" style="width: 80px" />
      <span class="muted">在每行点击「上报延期」，系统自动顺延该任务、下游任务及坞位预约</span>
    </div>
    <table v-if="tasks.length">
      <thead>
        <tr>
          <th>任务</th>
          <th>计划日期</th>
          <th>进度</th>
          <th>状态</th>
          <th>前置 / 施工队</th>
          <th>受阻原因（自动标记）</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in tasks" :key="t.id"
          :class="{ 'blocked-row': t.status === 'blocked', 'done-row': t.status === 'done' }">
          <td><strong>#{{ t.id }} {{ t.name }}</strong></td>
          <td>{{ t.start_date }} ~ {{ t.end_date }}</td>
          <td>
            <div class="progress"><span :style="{ width: t.progress + '%' }"></span></div>
            <select :value="t.progress" @change="(e) => setProgress(t, e.target.value)" style="width: 70px">
              <option v-for="v in [0, 25, 50, 75, 100]" :key="v" :value="v">{{ v }}%</option>
            </select>
          </td>
          <td><span class="badge" :class="t.status">{{ statusLabel[t.status] }}</span></td>
          <td>
            <div v-if="t.depends_on?.length">
              <span class="muted">前置：</span>
              <span v-for="d in t.depends_on" :key="d" class="tag">{{ taskName(d) }}</span>
            </div>
            <div>
              <span class="muted">施工队：</span>
              <span v-for="tid in t.team_ids" :key="tid" class="tag">{{ teamName(tid) }}</span>
            </div>
            <select @change="(e) => { assignExisting(t, e.target.value); e.target.value = '' }">
              <option value="">+ 加派施工队</option>
              <option v-for="team in teams.filter((x) => !t.team_ids.includes(x.id))"
                :key="team.id" :value="team.id">{{ team.name }}</option>
            </select>
          </td>
          <td>
            <div v-for="(reason, key) in blockersJson(t)" :key="key" class="blocker-text">
              ⚠ {{ reason }}
            </div>
          </td>
          <td style="white-space: nowrap">
            <button class="btn small" @click="reportDelay(t)">上报延期</button>
            <button class="btn danger small" @click="removeTask(t.id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">该项目暂无任务</div>

    <h3>计划甘特图</h3>
    <div class="gantt" v-if="tasks.length && ganttRange">
      <div v-for="t in tasks" :key="'g' + t.id" class="gantt-track"
        :style="{ gridTemplateColumns: '130px 1fr' }">
        <div class="gantt-label">{{ t.name }}</div>
        <div class="gantt-bar" :class="t.status" :style="barStyle(t)">
          <span class="dates">{{ t.start_date.slice(5) }} → {{ t.end_date.slice(5) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
