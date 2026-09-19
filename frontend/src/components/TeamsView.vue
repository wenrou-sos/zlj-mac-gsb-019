<script setup>
import { ref, onMounted } from 'vue'
import api from '../api.js'

const teams = ref([])
const tasks = ref([])
const form = ref({ name: '', specialty: '', size: 1 })

async function load() {
  teams.value = await api.listTeams()
  tasks.value = await api.listTasks()
}

async function submit() {
  if (!form.value.name) return alert('请填写施工队名称')
  await api.createTeam({
    name: form.value.name,
    specialty: form.value.specialty,
    size: Number(form.value.size) || 1,
  })
  form.value = { name: '', specialty: '', size: 1 }
  await load()
}

async function remove(id) {
  if (!confirm('删除该施工队?')) return
  await api.deleteTeam(id)
  await load()
}

function taskNames(ids) {
  return ids.map((id) => tasks.value.find((t) => t.id === id)?.name || `#${id}`)
}

onMounted(load)
</script>

<template>
  <div class="panel">
    <h2>施工队花名册</h2>
    <div class="form-row">
      <label>队名</label>
      <input v-model="form.name" placeholder="如：船体一班" />
      <label>专业</label>
      <input v-model="form.specialty" placeholder="如：船体 / 机电 / 涂装" />
      <label>人数</label>
      <input v-model="form.size" type="number" min="1" style="width: 80px" />
      <button class="btn" @click="submit">建队</button>
    </div>
    <p class="muted">
      同一施工队在重叠日期被排到两个任务时，系统会自动在两边标记「施工队冲突」。
      排班可在「任务拆分与排班」页为任务勾选施工队。
    </p>
  </div>

  <div class="panel">
    <h2>施工队（{{ teams.length }}）</h2>
    <table v-if="teams.length">
      <thead>
        <tr><th>队名</th><th>专业</th><th>人数</th><th>当前承担任务</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="team in teams" :key="team.id">
          <td><strong>{{ team.name }}</strong></td>
          <td>{{ team.specialty }}</td>
          <td>{{ team.size }}</td>
          <td>
            <span v-if="team.task_ids?.length">
              <span v-for="n in taskNames(team.task_ids)" :key="n" class="tag">{{ n }}</span>
            </span>
            <span v-else class="muted">未排班</span>
          </td>
          <td><button class="btn danger small" @click="remove(team.id)">删除</button></td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">暂无施工队</div>
  </div>
</template>
