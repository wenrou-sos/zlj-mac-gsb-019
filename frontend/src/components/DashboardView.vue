<script setup>
import { ref, onMounted } from 'vue'
import api from '../api.js'

defineEmits(['go'])

const stats = ref(null)
const logs = ref([])

async function load() {
  stats.value = await api.getDashboard()
  logs.value = await api.getLogs()
}

onMounted(load)
</script>

<template>
  <div v-if="stats">
    <div class="panel">
      <h2>坞期运行总览</h2>
      <div class="cards">
        <div class="card">
          <div class="num">{{ stats.project_count }}</div>
          <div class="label">维修项目</div>
        </div>
        <div class="card">
          <div class="num">{{ stats.task_count }}</div>
          <div class="label">维修任务总数</div>
        </div>
        <div class="card">
          <div class="num danger">{{ stats.blocked_task_count }}</div>
          <div class="label">受影响/受阻任务</div>
        </div>
        <div class="card">
          <div class="num warn">{{ stats.delayed_part_count }}</div>
          <div class="label">延期未到备件</div>
        </div>
        <div class="card">
          <div class="num">{{ stats.dock_count }}</div>
          <div class="label">坞位数量</div>
        </div>
        <div class="card">
          <div class="num">{{ stats.team_count }}</div>
          <div class="label">施工队数量</div>
        </div>
        <div class="card">
          <div class="num" :class="{ danger: stats.booking_conflict_count > 0 }">
            {{ stats.booking_conflict_count }}
          </div>
          <div class="label">坞位冲突</div>
        </div>
      </div>
    </div>

    <div class="panel">
      <h2>最近自动调整</h2>
      <div class="logs" v-if="logs.length">
        <div
          v-for="l in logs.slice(0, 12)"
          :key="l.id"
          class="log-line"
          :class="l.kind"
        >
          <span class="time">{{ l.created_at?.replace('T', ' ').slice(0, 16) }}</span>
          <span>{{ l.message }}</span>
        </div>
      </div>
      <div v-else class="empty">暂无调整记录</div>
    </div>
  </div>
  <div v-else class="panel empty">加载中…</div>
</template>
