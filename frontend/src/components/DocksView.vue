<script setup>
import { ref, onMounted } from 'vue'
import api from '../api.js'

const docks = ref([])
const bookings = ref([])
const tasks = ref([])
const dockForm = ref({ name: '', capacity: '' })
const bookingForm = ref({ dock_id: null, task_id: null, start_date: '', end_date: '' })

async function load() {
  docks.value = await api.listDocks()
  bookings.value = await api.listBookings()
  tasks.value = await api.listTasks()
}

async function createDock() {
  if (!dockForm.value.name) return
  await api.createDock(dockForm.value)
  dockForm.value = { name: '', capacity: '' }
  await load()
}

async function createBooking() {
  const f = bookingForm.value
  if (!f.dock_id || !f.task_id || !f.start_date || !f.end_date) {
    return alert('请完整填写坞位、任务与占用日期')
  }
  const result = await api.createBooking({
    dock_id: Number(f.dock_id),
    task_id: Number(f.task_id),
    start_date: f.start_date,
    end_date: f.end_date,
  })
  if (result.moved) {
    alert(
      `所选时段坞位已被占用，已自动改约至 ${result.booking.start_date} ~ ${result.booking.end_date}，` +
      `并调整 ${result.affected_tasks.length} 个关联任务`,
    )
  }
  bookingForm.value = { dock_id: null, task_id: null, start_date: '', end_date: '' }
  await load()
}

async function removeBooking(id) {
  if (!confirm('删除该坞位占用记录?')) return
  await api.deleteBooking(id)
  await load()
}

async function removeDock(id) {
  if (!confirm('删除该坞位?')) return
  await api.deleteDock(id)
  await load()
}

function dockName(id) {
  return docks.value.find((d) => d.id === id)?.name || `#${id}`
}
function taskName(id) {
  return tasks.value.find((t) => t.id === id)?.name || `#${id}`
}

function conflictsFor(dockId) {
  const list = bookings.value.filter((b) => b.dock_id === dockId)
  const found = []
  for (let i = 0; i < list.length; i++) {
    for (let j = i + 1; j < list.length; j++) {
      const a = list[i]
      const b = list[j]
      if (a.start_date <= b.end_date && b.start_date <= a.end_date) {
        found.push([a, b])
      }
    }
  }
  return found
}

onMounted(load)
</script>

<template>
  <div class="panel">
    <h2>坞位与占用安排</h2>
    <div class="form-row">
      <label>新建坞位</label>
      <input v-model="dockForm.name" placeholder="如：1号干船坞" />
      <input v-model="dockForm.capacity" placeholder="能力等级，如 10万吨级" />
      <button class="btn" @click="createDock">添加坞位</button>
    </div>

    <h3>安排坞位占用（冲突时自动顺延）</h3>
    <div class="form-row">
      <label>坞位</label>
      <select v-model="bookingForm.dock_id">
        <option :value="null">选择坞位</option>
        <option v-for="d in docks" :key="d.id" :value="d.id">{{ d.name }}（{{ d.capacity }}）</option>
      </select>
      <label>任务</label>
      <select v-model="bookingForm.task_id">
        <option :value="null">选择任务</option>
        <option v-for="t in tasks" :key="t.id" :value="t.id">#{{ t.id }} {{ t.name }}</option>
      </select>
      <label>开始</label>
      <input v-model="bookingForm.start_date" type="date" />
      <label>结束</label>
      <input v-model="bookingForm.end_date" type="date" />
      <button class="btn" @click="createBooking">安排占用</button>
    </div>
  </div>

  <div class="panel" v-for="d in docks" :key="d.id">
    <div class="flex-between">
      <h2 style="margin: 0">{{ d.name }} <span class="muted" style="font-size: 13px">{{ d.capacity }}</span></h2>
      <button class="btn danger small" @click="removeDock(d.id)">删除坞位</button>
    </div>
    <table>
      <thead>
        <tr><th>任务</th><th>占用开始</th><th>占用结束</th><th>冲突</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="b in bookings.filter((x) => x.dock_id === d.id)" :key="b.id">
          <td>{{ taskName(b.task_id) }}</td>
          <td>{{ b.start_date }}</td>
          <td>{{ b.end_date }}</td>
          <td>
            <span v-if="conflictsFor(d.id).some(([a, c]) => a.id === b.id || c.id === b.id)"
              class="badge blocked">重叠</span>
            <span v-else class="badge done">正常</span>
          </td>
          <td><button class="btn danger small" @click="removeBooking(b.id)">删除</button></td>
        </tr>
      </tbody>
    </table>
    <div v-if="!bookings.some((x) => x.dock_id === d.id)" class="empty">该坞位暂无占用计划</div>
  </div>
  <div v-if="!docks.length" class="panel empty">暂无坞位，请先创建</div>
</template>
