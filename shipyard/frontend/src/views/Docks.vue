<template>
  <div>
    <h2 class="page-title">坞位管理</h2>
    <p class="page-sub">干船坞 / 浮船坞 资源台账</p>

    <div class="panel">
      <h3>新增坞位</h3>
      <div class="form-grid">
        <label class="field">坞位编号<input v-model="form.code" placeholder="D3" /></label>
        <label class="field">名称<input v-model="form.name" /></label>
        <label class="field">长度(米)<input type="number" min="0" v-model.number="form.length_m" /></label>
        <label class="field">宽度(米)<input type="number" min="0" v-model.number="form.width_m" /></label>
        <label class="field">状态
          <select v-model="form.status">
            <option value="available">可用</option>
            <option value="maintenance">坞修中</option>
          </select>
        </label>
      </div>
      <button class="btn" @click="create">新增</button>
    </div>

    <div class="panel">
      <h3>坞位台账</h3>
      <table>
        <thead>
          <tr><th>编号</th><th>名称</th><th>长(m)</th><th>宽(m)</th><th>状态</th></tr>
        </thead>
        <tbody>
          <tr v-for="d in docks" :key="d.id">
            <td>{{ d.code }}</td><td>{{ d.name }}</td><td>{{ d.length_m }}</td><td>{{ d.width_m }}</td>
            <td><span class="badge" :class="d.status === 'available' ? 'done' : 'shortage'">
              {{ d.status === 'available' ? '可用' : '坞修中' }}
            </span></td>
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
const docks = ref([])
const form = reactive({ code: '', name: '', length_m: 200, width_m: 35, status: 'available' })

async function create() {
  if (!form.code || !form.name) return notify('请填写编号和名称', true)
  try {
    await api.createDock({ ...form })
    notify('坞位已新增')
    docks.value = await api.docks()
  } catch (e) { notify(e.message, true) }
}

onMounted(async () => { docks.value = await api.docks() })
</script>
