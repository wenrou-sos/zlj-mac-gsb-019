<template>
  <div>
    <h2 class="page-title">总览仪表盘</h2>
    <p class="page-sub">实时反映坞修进度、缺件/延期告警与坞位占用情况</p>

    <div class="cards">
      <div class="stat"><div class="num">{{ data.project_active }}</div><div class="label">进行中项目 / 共 {{ data.project_total }}</div></div>
      <div class="stat warn"><div class="num">{{ data.part_delayed }}</div><div class="label">延期到货备件</div></div>
      <div class="stat alert"><div class="num">{{ data.part_shortage }}</div><div class="label">缺件告警</div></div>
      <div class="stat alert"><div class="num">{{ data.task_blocked }}</div><div class="label">受阻任务</div></div>
      <div class="stat"><div class="num">{{ data.dock_total }}</div><div class="label">坞位总数</div></div>
    </div>

    <div class="panel">
      <h3>⚠️ 受阻任务（系统自动标记）</h3>
      <table v-if="data.blocked_tasks?.length">
        <thead><tr><th>任务编号</th><th>任务名称</th><th>受阻原因</th></tr></thead>
        <tbody>
          <tr v-for="t in data.blocked_tasks" :key="t.id">
            <td>{{ t.code }}</td>
            <td>{{ t.name }}</td>
            <td class="reason">{{ t.reason }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">暂无受阻任务，计划正常推进。</p>
    </div>

    <div class="panel">
      <h3>⚓ 坞位占用档期</h3>
      <table>
        <thead>
          <tr><th>坞位</th><th>项目</th><th>船舶</th><th>进坞</th><th>预计出坞</th><th>状态</th></tr>
        </thead>
        <tbody>
          <tr v-for="o in data.occupancies" :key="o.id">
            <td>{{ o.dock_code }}</td>
            <td><router-link :to="`/projects/${o.project_id}`">{{ o.project_code }}</router-link></td>
            <td>{{ o.ship_name }}</td>
            <td class="nowrap">{{ fmt(o.start_date) }}</td>
            <td class="nowrap">{{ fmt(o.end_date) }}</td>
            <td><span class="badge" :class="o.status">{{ statusText(o.status) }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive } from 'vue'
import api from '../api'

const data = reactive({
  project_total: 0, project_active: 0, task_total: 0, task_blocked: 0,
  part_delayed: 0, part_shortage: 0, dock_total: 0,
  blocked_tasks: [], occupancies: []
})
const statusMap = {
  reserved: '已预约', occupied: '占用中', released: '已释放'
}
const statusText = (s) => statusMap[s] || s
const fmt = (d) => (d || '').slice(0, 10)

onMounted(async () => {
  Object.assign(data, await api.dashboard())
})
</script>
