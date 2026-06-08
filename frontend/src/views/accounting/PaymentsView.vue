<template>
  <div>
    <CrudTable title="지급 관리" :columns="columns" :data="items" :loading="loading" @create="openModal(null)">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'payment_amount'">{{ Number(record.payment_amount).toLocaleString() }}</template>
        <template v-if="column.key === 'status'"><a-tag :color="sColor[record.status]">{{ sLabel[record.status] }}</a-tag></template>
        <template v-if="column.key === 'action'"><a @click="openModal(record)">상세</a></template>
      </template>
    </CrudTable>
    <a-modal v-model:open="modalOpen" title="지급 등록" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="10"><a-form-item label="지급번호" name="payment_no" :rules="[{required:true}]"><a-input v-model:value="form.payment_no" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="지급일" name="payment_date" :rules="[{required:true}]"><a-date-picker v-model:value="form.payment_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="6"><a-form-item label="지급방법" name="payment_method"><a-select v-model:value="form.payment_method"><a-select-option value="transfer">계좌이체</a-select-option><a-select-option value="check">수표</a-select-option><a-select-option value="cash">현금</a-select-option></a-select></a-form-item></a-col>
          <a-col :span="24"><a-form-item label="협력사" name="vendor_id"><a-select v-model:value="form.vendor_id" show-search allow-clear :filter-option="fopt"><a-select-option v-for="v in vendors" :key="v.id" :value="v.id">{{ v.company_name }}</a-select-option></a-select></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="지급금액" name="payment_amount" :rules="[{required:true}]"><a-input-number v-model:value="form.payment_amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="은행명" name="bank_name"><a-input v-model:value="form.bank_name" /></a-form-item></a-col>
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
import { accountingApi, masterApi } from '@/api'

const items = ref([]), vendors = ref([]), loading = ref(false), saving = ref(false), modalOpen = ref(false), formRef = ref()
const form = reactive({ payment_no: '', vendor_id: null, site_id: null, payment_date: null, payment_amount: 0, payment_method: 'transfer', bank_name: '', notes: '' })
const sColor = { draft: 'default', approved: 'blue', completed: 'green' }
const sLabel = { draft: '작성중', approved: '승인', completed: '완료' }
const fopt = (input, opt) => opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())
const columns = [
  { title: '지급번호', dataIndex: 'payment_no',     width: 140, align: 'center' },
  { title: '지급일',  dataIndex: 'payment_date',    width: 110, align: 'center' },
  { title: '지급금액', key: 'payment_amount',       width: 140, align: 'right' },
  { title: '지급방법', dataIndex: 'payment_method', width: 110, align: 'center' },
  { title: '은행',    dataIndex: 'bank_name',       width: 120, align: 'center' },
  { title: '상태',    key: 'status',                width: 90,  align: 'center' },
  { title: '관리',    key: 'action',                width: 80,  align: 'center', fixed: 'right' },
]
async function load() {
  loading.value = true
  try { const [p, v] = await Promise.all([accountingApi.getPayments({}), masterApi.getCompanies({ company_type: 'vendor' })]); items.value = p.data; vendors.value = v.data }
  finally { loading.value = false }
}
function openModal(item) { Object.assign(form, item || { payment_no: '', vendor_id: null, site_id: null, payment_date: null, payment_amount: 0, payment_method: 'transfer', bank_name: '', notes: '' }); modalOpen.value = true }
async function handleSave() {
  try { await formRef.value.validate(); saving.value = true; await accountingApi.createPayment(form); message.success('등록'); modalOpen.value = false; load() }
  catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') } finally { saving.value = false }
}
onMounted(load)
</script>
