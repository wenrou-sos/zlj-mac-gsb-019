<template>
  <div>
    <h2 class="page-title">施工队与排班</h2>
    <p class="page-sub">管理各专业施工队，查看其在所有项目上的档期</p>

    <div class="panel">
      <h3>新建施工队</h3>
      <div class="form-grid">
        <label class="field">编号<input v-model="form.code" placeholder="HULL2" /></label>
        <label class="field">名称<input v-model="form.name" /></label>
        <label class="field">专业
          <select v-model="form.specialty">
            <option>船体</option><option>轮机</option><option>电气</option>
            <option>涂装</option><option>管道</option>
          </select>
        </label>
        <label class="field">队长<input v-model="form.leader" /></label>
        <label class="field">电话<input v-model="form.phone" /></label>
        <label class="field">人数<input type="number" min="1" v-model.number="form.size" /></label>
      </div>
      <button class="btn" @click="create">创建</button>
    </div>

    <div class="panel">
      <h3>施工队列表</h3>
      <table>
        <thead><tr><th>编号</th><th>名称</th><th>专业</th><th>队长</th><th>电话</th><th>人数</th><th></th></tr></thead>
        <tbody>
          <tr v-for="t in teams" :key="t.id">
            <td>{{ t.code }}</td><td>{{ t.name }}</td><td>{{ t.specialty }}</td>
            <td>{{ t.leader || '—' }}</td><td>{{ t.phone || '—' }}</td><td>{{ t.size }}</td>
            <td class="right"><button class="btn sm ghost" @click="showSchedule(t)">查看排班</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="panel" v-if="schedule.length">
      <h3>{{ current?.name }} 的排班档期</h3>
      <table>
        <thead><tr><th>任务</th><th>所属项目</th><th>开始</th><th>结束</th><th>状态</th><th></th></tr></thead>
        <tbody>
          <tr v-for="a in schedule" :key="a.id">
            <td>{{ a.task_code }} {{ a.task_name }}</td>
            <td><router-link :to="`/projects/${a.project_id}`">项目 #{{ a.project_id }}</router-link></td>
            <td>{{ fmt(a.planned_start) }}</td><td>{{ fmt(a.planned_end) }}</td>
            <td><span class="badge" :class="a.status">{{ a.status }}</span></td>
            <td>
              <span v-if="hasOverlap(a)" class="badge shortage">档期重叠</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { inject, onMounted, reactive, ref } from 'vue'
import api from '../api'

const notify = inject('notify')
const teams = ref([])
const schedule = ref([])
const current = ref(null)
const form = reactive({ code: '', name: '', specialty: '船体', leader: '', phone: '', size: 5 })

const fmt = (d) => (d || '').slice(0, 10)

function hasOverlap(a) {
  return schedule.value.some(
    (b) => b.id !== a.id && b.planned_start <= a.planned_end && a.planned_start <= b.planned_end
  )
}

async function create() {
  if (!form.code || !form.name) return notify('请填写编号和名称', true)
  try {
    await api.createTeam({ ...form })
    notify('施工队已创建')
    teams.value = await api.teams()
  } catch (e) { notify(e.message, true) }
}

async function showSchedule(team) {
  current.value = team
  schedule.value = await api.teamSchedule(team.id)
}

onMounted(async () => { teams.value = await api.teams() })
</script>
