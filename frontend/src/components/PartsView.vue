<script setup>
import { ref, onMounted } from 'vue'
import api from '../api.js'

const parts = ref([])
const tasks = ref([])
const form = ref({ task_id: null, name: '', quantity: 1, eta: '' })

async function load() {
  parts.value = await api.listParts()
  tasks.value = await api.listTasks()
}

async function submit() {
  if (!form.value.task_id || !form.value.name) return alert('请选择任务并填写备件名称')
  await api.createPart({
    task_id: Number(form.value.task_id),
    name: form.value.name,
    quantity: Number(form.value.quantity) || 1,
    eta: form.value.eta || null,
  })
  form.value = { task_id: null, name: '', quantity: 1, eta: '' }
  await load()
}

async function setEta(part, eta) {
  const result = await api.updatePart(part.id, { eta })
  if (result.count) {
    alert(`备件延期，已自动调整 ${result.count} 个受影响任务`)
  }
  await load()
}

async function markArrived(part) {
  await api.updatePart(part.id, { arrived: true, eta: new Date().toISOString().slice(0, 10) })
  await load()
}

async function remove(part) {
  if (!confirm('删除该备件?')) return
  await api.deletePart(part.id)
  await load()
}

function taskLabel(id) {
  const t = tasks.value.find((x) => x.id === id)
  return t ? `#${t.id} ${t.name}` : `#${id}`
}

function delayed(part) {
  const task = tasks.value.find((x) => x.id === part.task_id)
  return !part.arrived && part.eta && task && part.eta >= task.start_date
}

onMounted(load)
</script>

<template>
  <div class="panel">
    <h2>登记备件需求</h2>
    <div class="form-row">
      <label>所属任务</label>
      <select v-model="form.task_id">
        <option :value="null">请选择任务</option>
        <option v-for="t in tasks" :key="t.id" :value="t.id">{{ taskLabel(t.id) }}</option>
      </select>
      <label>备件名称</label>
      <input v-model="form.name" placeholder="如：新螺旋桨" />
      <label>数量</label>
      <input v-model="form.quantity" type="number" min="1" style="width: 80px" />
      <label>预计到货 ETA</label>
      <input v-model="form.eta" type="date" />
      <button class="btn" @click="submit">登记</button>
    </div>
    <p class="muted">
      当预计到货日期晚于任务开始日，系统自动将任务顺延至到货日并标记「缺件」，
      同时顺延其下游任务；登记到货后自动解除阻塞。
    </p>
  </div>

  <div class="panel">
    <h2>备件到货跟踪（{{ parts.length }}）</h2>
    <table v-if="parts.length">
      <thead>
        <tr>
          <th>备件</th>
          <th>数量</th>
          <th>所属任务</th>
          <th>预计到货</th>
          <th>实际到货</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in parts" :key="p.id"
          :class="{ 'blocked-row': !p.arrived && (!p.eta || delayed(p)) }">
          <td><strong>{{ p.name }}</strong></td>
          <td>{{ p.quantity }}</td>
          <td>{{ taskLabel(p.task_id) }}</td>
          <td>
            <input type="date" :value="p.eta || ''"
              @change="(e) => setEta(p, e.target.value || null)" />
            <span v-if="delayed(p)" class="badge blocked">延期风险</span>
          </td>
          <td>{{ p.arrived_at || '—' }}</td>
          <td>
            <span class="badge" :class="p.arrived ? 'done' : 'blocked'">
              {{ p.arrived ? '已到货' : p.eta ? '待到货' : 'ETA未定' }}
            </span>
          </td>
          <td style="white-space: nowrap">
            <button v-if="!p.arrived" class="btn small" @click="markArrived(p)">登记到货</button>
            <button class="btn danger small" @click="remove(p)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">暂无备件记录</div>
  </div>
</template>
