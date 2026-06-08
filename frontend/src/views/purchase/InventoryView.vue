<template>
  <div>
    <CrudTable title="재고 현황" :columns="columns" :data="items" :loading="loading" :hide-create="true">
      <template #filters>
        <a-select v-model:value="filterSite" placeholder="현장 선택" style="width:200px" allow-clear @change="load">
          <a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option>
        </a-select>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="['current_qty','available_qty'].includes(column.key)">{{ Number(record[column.key]).toLocaleString() }}</template>
        <template v-if="column.key === 'avg_unit_price'">{{ Number(record.avg_unit_price).toLocaleString() }}</template>
        <template v-if="column.key === 'alert'">
          <a-tag color="red" v-if="Number(record.available_qty) <= 0">재고없음</a-tag>
          <a-tag color="orange" v-else-if="Number(record.available_qty) < 10">부족</a-tag>
          <a-tag color="green" v-else>정상</a-tag>
        </template>
      </template>
    </CrudTable>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import CrudTable from '@/components/common/CrudTable.vue'
import { purchaseApi, masterApi } from '@/api'

const items = ref([]), sites = ref([]), loading = ref(false), filterSite = ref(null)
const columns = [
  { title: '현장ID',  dataIndex: 'site_id',      width: 110, align: 'center' },
  { title: '자재ID',  dataIndex: 'material_id',  width: 110, align: 'center' },
  { title: '현재수량', key: 'current_qty',         width: 120, align: 'center' },
  { title: '가용수량', key: 'available_qty',       width: 120, align: 'center' },
  { title: '평균단가', key: 'avg_unit_price',      width: 130, align: 'right' },
  { title: '재고상태', key: 'alert',               width: 110, align: 'center' },
]
async function load() {
  loading.value = true
  try {
    const [inv, s] = await Promise.all([purchaseApi.getInventory({ site_id: filterSite.value || undefined }), masterApi.getSites({})])
    items.value = inv.data; sites.value = s.data
  } finally { loading.value = false }
}
onMounted(load)
</script>
