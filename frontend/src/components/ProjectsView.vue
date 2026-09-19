<script setup>
import { ref, onMounted } from 'vue'
import api from '../api.js'

const projects = ref([])
const form = ref({
  name: '',
  ship_name: '',
  start_date: '',
  end_date: '',
  notes: '',
})

async function load() {
  projects.value = await api.listProjects()
}

async function submit() {
  if (!form.value.name || !form.value.ship_name || !form.value.start_date || !form.value.end_date) {
    alert('请填写项目名称、船名与坞期起止日期')
    return
  }
  await api.createProject({ ...form.value, status: 'planned' })
  form.value = { name: '', ship_name: '', start_date: '', end_date: '', notes: '' }
  await load()
}

async function remove(id) {
  if (!confirm('删除该项目及其全部任务?')) return
  await api.deleteProject(id)
  await load()
}

const statusLabel = {
  planned: '计划中',
  in_progress: '进行中',
  delayed: '延期',
  completed: '已完成',
}

onMounted(load)
</script>

<template>
  <div class="panel">
    <h2>新建维修项目（坞期）</h2>
    <div class="form-row">
      <label>项目名称</label>
      <input v-model="form.name" placeholder="如：远洋号坞修工程" />
      <label>船舶名称</label>
      <input v-model="form.ship_name" placeholder="船名" />
      <label>坞期开始</label>
      <input v-model="form.start_date" type="date" />
      <label>坞期结束</label>
      <input v-model="form.end_date" type="date" />
      <label>备注</label>
      <input v-model="form.notes" placeholder="工程范围说明" style="min-width: 200px" />
      <button class="btn" @click="submit">创建项目</button>
    </div>
  </div>

  <div class="panel">
    <h2>维修项目列表（{{ projects.length }}）</h2>
    <table v-if="projects.length">
      <thead>
        <tr>
          <th>ID</th>
          <th>项目</th>
          <th>船舶</th>
          <th>坞期</th>
          <th>状态</th>
          <th>任务数</th>
          <th>备注</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in projects" :key="p.id">
          <td>{{ p.id }}</td>
          <td><strong>{{ p.name }}</strong></td>
          <td>{{ p.ship_name }}</td>
          <td>{{ p.start_date }} ~ {{ p.end_date }}</td>
          <td><span class="badge" :class="p.status">{{ statusLabel[p.status] || p.status }}</span></td>
          <td>{{ p.tasks?.length || 0 }}</td>
          <td class="muted">{{ p.notes }}</td>
          <td>
            <button class="btn danger small" @click="remove(p.id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">还没有项目，请先创建</div>
  </div>
</template>
