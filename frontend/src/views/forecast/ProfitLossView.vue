<template>
  <div>
    <a-card :bordered="false" title="현장별 손익 분석">
      <template #extra>
        <a-space>
          <a-input-number v-model:value="year" placeholder="연도" style="width:90px" :min="2020" />
          <a-select v-model:value="selectedSite" placeholder="전체현장" style="width:180px" allow-clear>
            <a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option>
          </a-select>
          <a-button type="primary" @click="load">조회</a-button>
        </a-space>
      </template>

      <a-table :columns="columns" :data-source="items" :loading="loading" size="middle"
        :pagination="false" :summary="summaryRow">
        <template #bodyCell="{ column, record }">
          <template v-if="['revenue','cost','profit'].includes(column.key)">
            <span :style="{ color: column.key === 'profit' ? (record.profit >= 0 ? '#52c41a' : '#cf1322') : '' }">
              {{ Number(record[column.key]).toLocaleString() }}
            </span>
          </template>
          <template v-if="column.key === 'cost_rate'">
            <a-progress :percent="record.cost_rate" size="small" :status="record.cost_rate > 90 ? 'exception' : 'normal'" style="width:80px" />
            {{ record.cost_rate }}%
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { forecastApi, masterApi } from '@/api'

const items = ref([]), sites = ref([]), loading = ref(false)
const year = ref(new Date().getFullYear()), selectedSite = ref(null)
const columns = [
  { title: '현장코드', dataIndex: 'site_code', width: 120 }, { title: '현장명', dataIndex: 'site_name', ellipsis: true },
  { title: '매출(기성)', key: 'revenue', align: 'right', width: 140 },
  { title: '원가투입', key: 'cost', align: 'right', width: 140 },
  { title: '공사이익', key: 'profit', align: 'right', width: 140 },
  { title: '원가율', key: 'cost_rate', width: 160 },
]
const summaryRow = () => {
  const totRev = items.value.reduce((s, i) => s + i.revenue, 0)
  const totCost = items.value.reduce((s, i) => s + i.cost, 0)
  const totProfit = totRev - totCost
  return {
    children: [
      { colSpan: 2, align: 'right', children: '합계' },
      { align: 'right', children: totRev.toLocaleString() },
      { align: 'right', children: totCost.toLocaleString() },
      { align: 'right', style: { color: totProfit >= 0 ? '#52c41a' : '#cf1322' }, children: totProfit.toLocaleString() },
      { align: 'center', children: totRev > 0 ? (totCost / totRev * 100).toFixed(1) + '%' : '-' },
    ]
  }
}
async function load() {
  loading.value = true
  try { items.value = (await forecastApi.getProfitLossReport({ year: year.value, site_id: selectedSite.value || undefined })).data }
  finally { loading.value = false }
}
onMounted(async () => {
  sites.value = (await masterApi.getSites({})).data
  load()
})
</script>
