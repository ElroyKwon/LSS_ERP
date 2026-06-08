<template>
  <div>
    <a-card :bordered="false">
      <template #title>원가 대비 현황 분석</template>
      <template #extra>
        <a-space>
          <a-select v-model:value="selectedSite" placeholder="현장 선택" style="width:200px" @change="load">
            <a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option>
          </a-select>
        </a-space>
      </template>
      <a-empty v-if="!selectedSite" description="현장을 선택하세요" />
      <div v-else-if="loading" style="text-align:center;padding:40px"><a-spin /></div>
      <div v-else>
        <a-row :gutter="16" style="margin-bottom:24px">
          <a-col :span="8">
            <a-statistic title="총 원가투입" :value="Number(analysis?.total_actual || 0).toLocaleString()" suffix="원" />
          </a-col>
        </a-row>
        <a-table :columns="columns" :data-source="analysis?.items || []" :pagination="false" size="middle">
          <template #bodyCell="{ column, record }">
            <template v-if="['budgeted','execution','actual','remaining'].includes(column.key)">
              {{ Number(record[column.key]).toLocaleString() }}
            </template>
            <template v-if="column.key === 'rate'">
              <a-progress :percent="record.rate" size="small" :status="record.rate > 90 ? 'exception' : 'normal'" />
              {{ record.rate }}%
            </template>
            <template v-if="column.key === 'cost_type'">
              <a-tag>{{ costTypeLabel[record.cost_type] || record.cost_type }}</a-tag>
            </template>
          </template>
        </a-table>
      </div>
    </a-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { budgetApi, masterApi } from '@/api'

const sites = ref([]), analysis = ref(null), selectedSite = ref(null), loading = ref(false)
const costTypeLabel = { material: '재료비', labor: '노무비', subcontract: '외주비', expense: '경비', equipment: '장비' }
const columns = [
  { title: '원가유형', key: 'cost_type',      width: 110, align: 'center' },
  { title: '항목명',  dataIndex: 'item_name',  width: 200, align: 'center', ellipsis: true },
  { title: '예산금액', key: 'budgeted',         width: 130, align: 'right' },
  { title: '실행금액', key: 'execution',        width: 130, align: 'right' },
  { title: '실적투입', key: 'actual',           width: 130, align: 'right' },
  { title: '잔여예산', key: 'remaining',        width: 130, align: 'right' },
  { title: '달성율',  key: 'rate',              width: 150, align: 'center' },
]
async function load() {
  if (!selectedSite.value) return
  loading.value = true
  try { analysis.value = (await budgetApi.getCostAnalysis(selectedSite.value)).data }
  finally { loading.value = false }
}
onMounted(async () => {
  sites.value = (await masterApi.getSites({})).data
})
</script>
