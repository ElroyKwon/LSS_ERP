<template>
  <div>
    <CrudTable title="경비 신청" :columns="columns" :data="items" :loading="loading" @create="openModal(null)">
      <template #filters>
        <a-select v-model:value="filterSite" placeholder="현장" style="width:160px" allow-clear @change="load">
          <a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option>
        </a-select>
        <a-select v-model:value="filterStatus" placeholder="상태" style="width:100px" allow-clear @change="load">
          <a-select-option value="draft">작성중</a-select-option>
          <a-select-option value="approved">승인</a-select-option>
          <a-select-option value="paid">지급완료</a-select-option>
        </a-select>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'amount'">{{ Number(record.amount).toLocaleString() }}</template>
        <template v-if="column.key === 'status'"><a-tag :color="sColor[record.status]">{{ sLabel[record.status] }}</a-tag></template>
        <template v-if="column.key === 'action'"><a @click="openModal(record)">수정</a></template>
      </template>
    </CrudTable>
    <a-modal v-model:open="modalOpen" title="경비 등록" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="10"><a-form-item label="경비번호" name="expense_no" :rules="[{required:true}]"><a-input v-model:value="form.expense_no" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="경비일" name="expense_date" :rules="[{required:true}]"><a-date-picker v-model:value="form.expense_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="6"><a-form-item label="경비유형" name="expense_type"><a-select v-model:value="form.expense_type" allow-clear><a-select-option value="travel">출장</a-select-option><a-select-option value="meal">식대</a-select-option><a-select-option value="supplies">소모품</a-select-option><a-select-option value="other">기타</a-select-option></a-select></a-form-item></a-col>
          <a-col :span="24"><a-form-item label="현장" name="site_id"><a-select v-model:value="form.site_id" show-search allow-clear :filter-option="fopt"><a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option></a-select></a-form-item></a-col>
          <a-col :span="24"><a-form-item label="내용" name="description"><a-input v-model:value="form.description" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="공급가액" name="amount" :rules="[{required:true}]"><a-input-number v-model:value="form.amount" style="width:100%" @change="calcVat" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="부가세" name="vat_amount"><a-input-number v-model:value="form.vat_amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="영수증번호" name="receipt_no"><a-input v-model:value="form.receipt_no" /></a-form-item></a-col>
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
import { purchaseApi, masterApi } from '@/api'

const items = ref([]), sites = ref([])
const loading = ref(false), saving = ref(false), modalOpen = ref(false)
const filterSite = ref(null), filterStatus = ref(null), formRef = ref()
const form = reactive({ expense_no: '', site_id: null, cost_code_id: null, expense_date: null, expense_type: null, description: '', amount: 0, vat_amount: 0, vendor_id: null, receipt_no: '', notes: '' })
const sColor = { draft: 'default', approved: 'green', paid: 'blue' }
const sLabel = { draft: '작성중', approved: '승인', paid: '지급완료' }
const fopt = (input, opt) => opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())
function calcVat() { form.vat_amount = Math.round(form.amount * 0.1) }
const columns = [
  { title: '경비번호', dataIndex: 'expense_no',   width: 140, align: 'center' },
  { title: '경비일',  dataIndex: 'expense_date',  width: 110, align: 'center' },
  { title: '유형',    dataIndex: 'expense_type',  width: 100, align: 'center' },
  { title: '내용',    dataIndex: 'description',   width: 220, align: 'center', ellipsis: true },
  { title: '금액',    key: 'amount',              width: 130, align: 'right' },
  { title: '상태',    key: 'status',              width: 90,  align: 'center' },
  { title: '관리',    key: 'action',              width: 80,  align: 'center', fixed: 'right' },
]
async function load() {
  loading.value = true
  try {
    const [e, s] = await Promise.all([purchaseApi.getExpenses({ site_id: filterSite.value || undefined, status: filterStatus.value || undefined }), masterApi.getSites({})])
    items.value = e.data; sites.value = s.data
  } finally { loading.value = false }
}
function openModal(item) { Object.assign(form, item || { expense_no: '', site_id: null, cost_code_id: null, expense_date: null, expense_type: null, description: '', amount: 0, vat_amount: 0, vendor_id: null, receipt_no: '', notes: '' }); modalOpen.value = true }
async function handleSave() {
  try { await formRef.value.validate(); saving.value = true; await purchaseApi.createExpense(form); message.success('등록'); modalOpen.value = false; load() }
  catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') } finally { saving.value = false }
}
onMounted(load)
</script>
