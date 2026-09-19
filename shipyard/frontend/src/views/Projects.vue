<template>
  <div>
    <h2 class="page-title">维修项目</h2>
    <p class="page-sub">一艘船一次进坞对应一个维修项目，点击项目可拆分 WBS 任务、跟踪备件与安排坞位</p>

    <div class="panel">
      <h3>新建维修项目</h3>
      <div class="form-grid">
        <label class="field">项目编号
          <input v-model="form.code" placeholder="P-2026-010" />
        </label>
        <label class="field">项目名称
          <input v-model="form.name" placeholder="XX轮坞修" />
        </label>
        <label class="field">船名
          <input v-model="form.ship_name" />
        </label>
        <label class="field">IMO 号
          <input v-model="form.imo" />
        </label>
        <label class="field">计划进坞日
          <input type="date" v-model="form.planned_start" />
        </label>
        <label class="field">安排坞位
          <select v-model="form.dock_id">
            <option :value="null">暂不安排</option>
            <option v-for="d in docks" :key="d.id" :value="d.id">{{ d.code }} {{ d.name }}</option>
          </select>
        </label>
      </div>
      <button class="btn" @click="create">创建项目</button>
    </div>

    <div class="panel">
      <h3>项目清单</h3>
      <table>
        <thead>
          <tr>
            <th>项目编号</th><th>船名</th><th>状态</th><th>坞位</th>
            <th>计划进坞</th><th>计划完工</th><th>延期</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in projects" :key="p.id">
            <td>{{ p.code }}</td>
            <td>{{ p.ship_name }}</td>
            <td><span class="badge" :class="p.status">{{ projectStatus(p.status) }}</span></td>
            <td>{{ p.dock?.code || '—' }}</td>
            <td class="nowrap">{{ fmt(p.planned_start) }}</td>
            <td class="nowrap">{{ fmt(p.planned_end) }}</td>
            <td :class="{ reason: p.delay_days > 0 }">{{ p.delay_days ? `${p.delay_days} 天` : '正常' }}</td>
            <td class="right nowrap">
              <router-link class="btn sm ghost" :to="`/projects/${p.id}`">打开</router-link>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { inject, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const notify = inject('notify')
const router = useRouter()
const projects = ref([])
const docks = ref([])
const form = reactive({ code: '', name: '', ship_name: '', imo: '', planned_start: '', dock_id: null })

const projectStatus = (s) => ({ planned: '计划中', in_progress: '进行中', completed: '已完工' })[s] || s
const fmt = (d) => (d || '').slice(0, 10)

async function load() {
  projects.value = await api.projects()
}

async function create() {
  if (!form.code || !form.name || !form.ship_name || !form.planned_start) {
    notify('请填写项目编号、名称、船名和进坞日期', true)
    return
  }
  try {
    const p = await api.createProject({ ...form, imo: form.imo || null })
    notify(`项目 ${p.code} 创建成功`)
    router.push(`/projects/${p.id}`)
  } catch (e) {
    notify(e.message, true)
  }
}

onMounted(async () => {
  docks.value = await api.docks()
  await load()
})
</script>
