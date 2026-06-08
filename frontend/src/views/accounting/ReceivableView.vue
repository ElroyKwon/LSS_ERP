<template>
  <div>
    <a-row :gutter="[16,16]" style="margin-bottom:16px">
      <a-col :span="8"><a-card :bordered="false"><a-statistic title="총 청구금액" :value="summary.total_billing?.toLocaleString()" suffix="원" /></a-card></a-col>
      <a-col :span="8"><a-card :bordered="false"><a-statistic title="수금완료" :value="summary.total_collected?.toLocaleString()" suffix="원" value-style="color:#52c41a" /></a-card></a-col>
      <a-col :span="8"><a-card :bordered="false"><a-statistic title="미수금" :value="summary.total_outstanding?.toLocaleString()" suffix="원" value-style="color:#cf1322" /></a-card></a-col>
    </a-row>
    <CrudTable title="매출채권 (공사미수금)" :columns="columns" :data="items" :loading="loading" :hide-create="true">
      <template #filters>
        <a-select v-model:value="filterStatus" placeholder="상태" style="width:100px" allow-clear @change="load">
          <a-select-option value="outstanding">미수</a-select-option>
          <a-select-option value="partial">일부수금</a-select-option>
          <a-select-option value="collected">완료</a-select-option>
          <a-select-option value="overdue">연체</a-select-option>
        </a-select>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="['billing_amount','collected_amount','outstanding_amount'].includes(column.key)">{{ Number(record[column.key]).toLocaleString() }}</template>
        <template v-if="column.key === 'status'"><a-tag :color="sColor[record.status]">{{ sLabel[record.status] }}</a-tag></template>
      </template>
    </CrudTable>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import CrudTable from '@/components/common/CrudTable.vue'
import { accountingApi } from '@/api'

const items = ref([]), loading = ref(false), filterStatus = ref(null)
const summary = reactive({ total_billing: 0, total_collected: 0, total_outstanding: 0 })
const sColor = { outstanding: 'red', partial: 'orange', collected: 'green', overdue: 'purple' }
const sLabel = { outstanding: '미수', partial: '일부수금', collected: '수금완료', overdue: '연체' }
const columns = [
  { title: '청구ID',  dataIndex: 'billing_id',      width: 90,  align: 'center' },
  { title: '청구일',  dataIndex: 'issue_date',       width: 110, align: 'center' },
  { title: '만기일',  dataIndex: 'due_date',         width: 110, align: 'center' },
  { title: '청구금액', key: 'billing_amount',        width: 140, align: 'right' },
  { title: '수금금액', key: 'collected_amount',      width: 140, align: 'right' },
  { title: '미수금',  key: 'outstanding_amount',    width: 140, align: 'right' },
  { title: '상태',    key: 'status',                width: 90,  align: 'center' },
]
async function load() {
  loading.value = true
  try {
    const [ar, s] = await Promise.all([accountingApi.getAR({ status: filterStatus.value || undefined }), accountingApi.getARSummary()])
    items.value = ar.data; Object.assign(summary, s.data)
  } finally { loading.value = false }
}
onMounted(load)
</script>
