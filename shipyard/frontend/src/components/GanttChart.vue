<template>
  <div class="gantt">
    <div v-for="item in items" :key="item.id" class="gantt-row">
      <div class="gantt-label" :title="item.name">
        {{ item.code }} · {{ item.name }}
      </div>
      <div class="gantt-track">
        <div
          class="gantt-bar"
          :class="[item.status, { delay: item.delay_days > 0 }]"
          :style="barStyle(item)"
          :title="`${item.start} ~ ${item.end}` + (item.delay_days ? `（延期 ${item.delay_days} 天）` : '')"
        >
          {{ item.start }} → {{ item.end }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  items: { type: Array, required: true } // {id,code,name,start,end,status,delay_days}
})

const DAYS_MS = 86400000

const range = computed(() => {
  if (!props.items.length) return { min: 0, span: 1 }
  const starts = props.items.map((i) => new Date(i.start).getTime())
  const ends = props.items.map((i) => new Date(i.end).getTime())
  const min = Math.min(...starts)
  const max = Math.max(...ends)
  return { min, span: Math.max(1, (max - min) / DAYS_MS + 1) }
})

function barStyle(item) {
  const s = (new Date(item.start).getTime() - range.value.min) / DAYS_MS
  const width = ((new Date(item.end).getTime() - new Date(item.start).getTime()) / DAYS_MS + 1)
  return {
    left: `${(s / range.value.span) * 100}%`,
    width: `${(width / range.value.span) * 100}%`
  }
}
</script>
