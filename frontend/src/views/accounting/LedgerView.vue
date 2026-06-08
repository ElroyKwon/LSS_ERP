<template>
  <div>
    <a-card :bordered="false" title="총계정원장">
      <template #extra>
        <a-space>
          <a-select v-model:value="params.account_id" placeholder="계정과목" style="width:160px" show-search allow-clear :filter-option="fopt">
            <a-select-option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.code }} {{ a.name }}</a-select-option>
          </a-select>
          <a-select v-model:value="params.site_id" placeholder="현장" style="width:160px" show-search allow-clear :filter-option="fopt">
            <a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option>
          </a-select>
          <a-range-picker v-model:value="dateRange" value-format="YYYY-MM-DD" style="width:240px" />
          <a-button type="primary" @click="load">조회</a-button>
        </a-space>
      </template>
      <a-table :columns="columns" :data-source="items" :loading="loading" size="small" :pagination="false"
        :summary="summaryRow" :scroll="{ x: 900 }">
        <template #bodyCell="{ column, record }">
          <template v-if="['debit','credit','balance'].includes(column.key)">{{ Number(record[column.key]).toLocaleString() }}</template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { accountingApi, masterApi } from '@/api'

const items = ref([]), accounts = ref([]), sites = ref([]), loading = ref(false)
const params = reactive({ account_id: null, site_id: null })
const dateRange = ref([])
const fopt = (input, opt) => opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())
const columns = [
  { title: '전표일', dataIndex: 'entry_date',  width: 110, align: 'center' },
  { title: '전표ID', dataIndex: 'entry_id',    width: 90,  align: 'center' },
  { title: '적요',   dataIndex: 'description', width: 220, align: 'center', ellipsis: true },
  { title: '차변',   key: 'debit',             width: 140, align: 'right' },
  { title: '대변',   key: 'credit',            width: 140, align: 'right' },
  { title: '잔액',   key: 'balance',           width: 140, align: 'right' },
]
const summaryRow = () => ({
  children: [{ colSpan: 3, align: 'right', children: '합계' }, { align: 'right', children: items.value.reduce((s, i) => s + i.debit, 0).toLocaleString() }, { align: 'right', children: items.value.reduce((s, i) => s + i.credit, 0).toLocaleString() }, { align: 'right', children: '' }]
})
async function load() {
  loading.value = true
  try {
    const res = await accountingApi.getLedger({ ...params, date_from: dateRange.value?.[0] || undefined, date_to: dateRange.value?.[1] || undefined })
    items.value = res.data
  } finally { loading.value = false }
}
onMounted(async () => {
  const [a, s] = await Promise.all([masterApi.getAccountCodes(), masterApi.getSites({})])
  accounts.value = a.data; sites.value = s.data
})
</script>
