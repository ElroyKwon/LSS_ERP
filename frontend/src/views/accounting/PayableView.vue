<template>
  <div>
    <CrudTable title="매입채무 (외상매입금)" :columns="columns" :data="items" :loading="loading" :hide-create="true">
      <template #filters>
        <a-select v-model:value="filterStatus" placeholder="상태" style="width:100px" allow-clear @change="load">
          <a-select-option value="outstanding">미지급</a-select-option>
          <a-select-option value="partial">일부지급</a-select-option>
          <a-select-option value="paid">지급완료</a-select-option>
        </a-select>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="['total_amount','paid_amount','outstanding_amount'].includes(column.key)">{{ Number(record[column.key]).toLocaleString() }}</template>
        <template v-if="column.key === 'status'"><a-tag :color="sColor[record.status]">{{ sLabel[record.status] }}</a-tag></template>
      </template>
    </CrudTable>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import CrudTable from '@/components/common/CrudTable.vue'
import { accountingApi } from '@/api'

const items = ref([]), loading = ref(false), filterStatus = ref(null)
const sColor = { outstanding: 'red', partial: 'orange', paid: 'green' }
const sLabel = { outstanding: '미지급', partial: '일부지급', paid: '지급완료' }
const columns = [
  { title: '현장ID',  dataIndex: 'site_id',          width: 90,  align: 'center' },
  { title: '청구일',  dataIndex: 'issue_date',        width: 110, align: 'center' },
  { title: '만기일',  dataIndex: 'due_date',          width: 110, align: 'center' },
  { title: 'INVOICE', dataIndex: 'invoice_no',        width: 130, align: 'center' },
  { title: '청구금액', key: 'total_amount',           width: 140, align: 'right' },
  { title: '지급금액', key: 'paid_amount',            width: 140, align: 'right' },
  { title: '미지급',  key: 'outstanding_amount',     width: 140, align: 'right' },
  { title: '상태',    key: 'status',                 width: 90,  align: 'center' },
]
async function load() {
  loading.value = true
  try { items.value = (await accountingApi.getAP({ status: filterStatus.value || undefined })).data }
  finally { loading.value = false }
}
onMounted(load)
</script>
