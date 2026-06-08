<template>
  <div>
    <a-card :bordered="false" title="자금 계획">
      <template #extra>
        <a-input-number v-model:value="year" placeholder="연도" style="width:90px" @change="load" />
      </template>
      <a-table :columns="columns" :data-source="tableData" :loading="loading" size="middle" :pagination="false">
        <template #bodyCell="{ column, record }">
          <template v-if="['planned_income','planned_expense','actual_income','actual_expense'].includes(column.key)">
            <a-input-number v-model:value="record[column.key]" style="width:130px" />
          </template>
          <template v-if="column.key === 'planned_balance'"><span :style="{color: record.planned_income - record.planned_expense >= 0 ? 'green' : 'red'}">{{ ((record.planned_income || 0) - (record.planned_expense || 0)).toLocaleString() }}</span></template>
          <template v-if="column.key === 'actual_balance'"><span :style="{color: (record.actual_income || 0) - (record.actual_expense || 0) >= 0 ? 'green' : 'red'}">{{ ((record.actual_income || 0) - (record.actual_expense || 0)).toLocaleString() }}</span></template>
        </template>
      </a-table>
      <a-button type="primary" @click="saveAll" :loading="saving" style="margin-top:16px">전체 저장</a-button>
    </a-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { forecastApi } from '@/api'

const plans = ref([]), loading = ref(false), saving = ref(false)
const year = ref(new Date().getFullYear())
const months = [1,2,3,4,5,6,7,8,9,10,11,12]
const tableData = computed(() => months.map(m => {
  const p = plans.value.find(p => p.plan_month === m) || {}
  return { plan_year: year.value, plan_month: m, planned_income: p.planned_income || 0, planned_expense: p.planned_expense || 0, actual_income: p.actual_income || 0, actual_expense: p.actual_expense || 0 }
}))
const columns = [
  { title: '월', dataIndex: 'plan_month', width: 50, customRender: ({text}) => text + '월' },
  { title: '계획수입', key: 'planned_income' }, { title: '계획지출', key: 'planned_expense' }, { title: '계획잔액', key: 'planned_balance', align: 'right', width: 130 },
  { title: '실적수입', key: 'actual_income' }, { title: '실적지출', key: 'actual_expense' }, { title: '실적잔액', key: 'actual_balance', align: 'right', width: 130 },
]
async function load() {
  loading.value = true
  try { plans.value = (await forecastApi.getFundPlans({ plan_year: year.value })).data } finally { loading.value = false }
}
async function saveAll() {
  saving.value = true
  try {
    await Promise.all(tableData.value.map(r => forecastApi.upsertFundPlan({ plan_year: r.plan_year, plan_month: r.plan_month, planned_income: r.planned_income, planned_expense: r.planned_expense })))
    message.success('저장되었습니다.'); load()
  } catch { message.error('오류') } finally { saving.value = false }
}
onMounted(load)
</script>
