<template>
  <div>
    <a-card :bordered="false" title="매출 예측 입력">
      <template #extra>
        <a-space>
          <a-input-number v-model:value="year" placeholder="연도" style="width:90px" @change="load" />
          <a-select v-model:value="selectedSite" placeholder="현장 선택" style="width:200px" allow-clear @change="load">
            <a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option>
          </a-select>
        </a-space>
      </template>
      <a-table :columns="columns" :data-source="tableData" :loading="loading" size="middle" :pagination="false">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'forecast_amount'">
            <a-input-number v-model:value="record.forecast_amount" style="width:130px" @change="markDirty(record)" />
          </template>
          <template v-if="column.key === 'actual_amount'">{{ Number(record.actual_amount).toLocaleString() }}</template>
          <template v-if="column.key === 'rate'">
            <template v-if="record.forecast_amount > 0">
              {{ (record.actual_amount / record.forecast_amount * 100).toFixed(1) }}%
            </template>
            <template v-else>-</template>
          </template>
        </template>
      </a-table>
      <a-button type="primary" @click="saveAll" :loading="saving" style="margin-top:16px">전체 저장</a-button>
    </a-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { forecastApi, masterApi } from '@/api'

const sites = ref([]), forecasts = ref([]), loading = ref(false), saving = ref(false)
const year = ref(new Date().getFullYear()), selectedSite = ref(null)
const dirty = ref(new Set())

const months = [1,2,3,4,5,6,7,8,9,10,11,12]
const tableData = computed(() => months.map(m => {
  const f = forecasts.value.find(f => f.forecast_month === m) || {}
  return { site_id: selectedSite.value, forecast_year: year.value, forecast_month: m, forecast_amount: f.forecast_amount || 0, actual_amount: f.actual_amount || 0 }
}))
const columns = [
  { title: '월', dataIndex: 'forecast_month', width: 60, align: 'center', customRender: ({text}) => text + '월' },
  { title: '예측금액(원)', key: 'forecast_amount', width: 160 },
  { title: '실적금액(원)', key: 'actual_amount', align: 'right', width: 130 },
  { title: '달성율', key: 'rate', align: 'center', width: 90 },
]
function markDirty(record) { dirty.value.add(record.forecast_month) }
async function load() {
  if (!selectedSite.value) return
  loading.value = true
  try { forecasts.value = (await forecastApi.getRevenueForecasts({ forecast_year: year.value, site_id: selectedSite.value })).data }
  finally { loading.value = false }
}
async function saveAll() {
  if (!selectedSite.value) { message.warning('현장을 선택하세요'); return }
  saving.value = true
  try {
    await Promise.all(tableData.value.map(r => forecastApi.upsertRevenueForecast({ site_id: selectedSite.value, forecast_year: year.value, forecast_month: r.forecast_month, forecast_amount: r.forecast_amount })))
    message.success('저장되었습니다.'); dirty.value.clear(); load()
  } catch (e) { message.error('오류') } finally { saving.value = false }
}
onMounted(async () => { sites.value = (await masterApi.getSites({})).data })
</script>
