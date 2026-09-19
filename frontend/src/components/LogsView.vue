<script setup>
import { ref, onMounted } from 'vue'
import api from '../api.js'

const logs = ref([])

onMounted(async () => {
  logs.value = await api.getLogs(500)
})

const kindLabel = { info: '通知', warning: '预警', adjustment: '自动调整' }
</script>

<template>
  <div class="panel">
    <h2>计划自动调整审计日志</h2>
    <div class="logs" style="max-height: 600px" v-if="logs.length">
      <div v-for="l in logs" :key="l.id" class="log-line" :class="l.kind">
        <span class="time">{{ l.created_at?.replace('T', ' ').slice(0, 16) }}</span>
        <span class="badge" :class="l.kind === 'info' ? 'planned' : l.kind">{{ kindLabel[l.kind] }}</span>
        <span>{{ l.message }}</span>
      </div>
    </div>
    <div v-else class="empty">暂无日志</div>
  </div>
</template>
