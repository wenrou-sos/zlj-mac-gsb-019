<script setup>
import { ref, onMounted } from 'vue'
import DashboardView from './components/DashboardView.vue'
import ProjectsView from './components/ProjectsView.vue'
import TasksView from './components/TasksView.vue'
import TeamsView from './components/TeamsView.vue'
import PartsView from './components/PartsView.vue'
import DocksView from './components/DocksView.vue'
import LogsView from './components/LogsView.vue'

const tabs = [
  { key: 'dashboard', label: '总览' },
  { key: 'projects', label: '维修项目' },
  { key: 'tasks', label: '任务拆分与排班' },
  { key: 'parts', label: '备件到货' },
  { key: 'docks', label: '坞位占用' },
  { key: 'teams', label: '施工队' },
  { key: 'logs', label: '调整日志' },
]

const active = ref('dashboard')

function switchTab(key) {
  active.value = key
}

// Simple cross-component refresh: selecting a project in one view focuses it
// in the tasks view.
onMounted(() => {
  window.addEventListener('navigate', (e) => {
    active.value = e.detail.tab
  })
})
</script>

<template>
  <header class="topbar">
    <h1>⚓ 船舶维修坞期管理平台</h1>
    <span class="anchor">维修项目拆分 · 施工队排班 · 备件跟踪 · 坞位调度</span>
    <nav class="tabs">
      <button
        v-for="t in tabs"
        :key="t.key"
        :class="{ active: active === t.key }"
        @click="switchTab(t.key)"
      >
        {{ t.label }}
      </button>
    </nav>
  </header>

  <main>
    <DashboardView v-if="active === 'dashboard'" @go="switchTab" />
    <ProjectsView v-else-if="active === 'projects'" />
    <TasksView v-else-if="active === 'tasks'" />
    <PartsView v-else-if="active === 'parts'" />
    <DocksView v-else-if="active === 'docks'" />
    <TeamsView v-else-if="active === 'teams'" />
    <LogsView v-else-if="active === 'logs'" />
  </main>
</template>
