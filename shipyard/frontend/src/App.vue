<template>
  <div class="layout">
    <aside class="sidebar">
      <h1>
        船舶维修坞期管理
        <small>SHIPYARD DOCK CONTROL</small>
      </h1>
      <nav>
        <router-link to="/">📊 总览仪表盘</router-link>
        <router-link to="/projects">🚢 维修项目</router-link>
        <router-link to="/teams">👷 施工队排班</router-link>
        <router-link to="/docks">⚓ 坞位管理</router-link>
      </nav>
    </aside>
    <main class="content">
      <router-view />
    </main>
    <div v-if="toast" class="toast" :class="{ error: toastError }">{{ toast }}</div>
  </div>
</template>

<script setup>
import { ref, provide } from 'vue'

const toast = ref('')
const toastError = ref(false)
let timer = null

function notify(msg, isError = false) {
  toast.value = msg
  toastError.value = isError
  clearTimeout(timer)
  timer = setTimeout(() => (toast.value = ''), 3500)
}

provide('notify', notify)
</script>
