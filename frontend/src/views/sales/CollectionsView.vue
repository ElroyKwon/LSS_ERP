<template>
  <div>
    <CrudTable title="수금 관리" :columns="columns" :data="items" :loading="loading" @create="openModal(null)">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'collected_amount'">{{ Number(record.collected_amount).toLocaleString() }}</template>
        <template v-if="column.key === 'action'"><a @click="openModal(record)">상세</a></template>
      </template>
    </CrudTable>
    <a-modal v-model:open="modalOpen" title="수금 등록" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="12"><a-form-item label="수금번호" name="collection_no" :rules="[{required:true}]"><a-input v-model:value="form.collection_no" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="수금일" name="collected_date" :rules="[{required:true}]"><a-date-picker v-model:value="form.collected_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="24"><a-form-item label="기성청구 연결" name="billing_id">
            <a-select v-model:value="form.billing_id" show-search allow-clear :filter-option="filterOpt">
              <a-select-option v-for="b in billings" :key="b.id" :value="b.id">{{ b.billing_no }} ({{ Number(b.total_amount).toLocaleString() }}원)</a-select-option>
            </a-select>
          </a-form-item></a-col>
          <a-col :span="24"><a-form-item label="발주처" name="client_id">
            <a-select v-model:value="form.client_id" show-search allow-clear :filter-option="filterOpt">
              <a-select-option v-for="c in clients" :key="c.id" :value="c.id">{{ c.company_name }}</a-select-option>
            </a-select>
          </a-form-item></a-col>
          <a-col :span="12"><a-form-item label="수금금액" name="collected_amount" :rules="[{required:true}]"><a-input-number v-model:value="form.collected_amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="입금은행" name="bank_name"><a-input v-model:value="form.bank_name" /></a-form-item></a-col>
          <a-col :span="24"><a-form-item label="비고"><a-textarea v-model:value="form.notes" :rows="2" /></a-form-item></a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import CrudTable from '@/components/common/CrudTable.vue'
import { salesApi, masterApi } from '@/api'

const items = ref([]), billings = ref([]), clients = ref([])
const loading = ref(false), saving = ref(false), modalOpen = ref(false), formRef = ref()
const form = reactive({ collection_no: '', billing_id: null, contract_id: null, site_id: null, client_id: null, collected_date: null, collected_amount: 0, bank_name: '', notes: '' })
const filterOpt = (input, opt) => opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())
const columns = [
  { title: '수금번호', dataIndex: 'collection_no',  width: 140, align: 'center' },
  { title: '수금일',  dataIndex: 'collected_date',  width: 110, align: 'center' },
  { title: '수금금액', key: 'collected_amount',     width: 140, align: 'right' },
  { title: '입금은행', dataIndex: 'bank_name',      width: 130, align: 'center' },
  { title: '비고',    dataIndex: 'notes',           width: 200, align: 'center', ellipsis: true },
  { title: '관리',    key: 'action',                width: 80,  align: 'center', fixed: 'right' },
]
async function load() {
  loading.value = true
  try {
    const [col, b, c] = await Promise.all([salesApi.getCollections({}), salesApi.getBillings({ status: 'approved' }), masterApi.getCompanies({ company_type: 'client' })])
    items.value = col.data; billings.value = b.data; clients.value = c.data
  } finally { loading.value = false }
}
function openModal(item) {
  Object.assign(form, item || { collection_no: '', billing_id: null, contract_id: null, site_id: null, client_id: null, collected_date: null, collected_amount: 0, bank_name: '', notes: '' })
  modalOpen.value = true
}
async function handleSave() {
  try {
    await formRef.value.validate(); saving.value = true
    await salesApi.createCollection(form); message.success('등록')
    modalOpen.value = false; load()
  } catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') }
  finally { saving.value = false }
}
onMounted(load)
</script>
