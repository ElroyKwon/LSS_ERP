<template>
  <div>
    <CrudTable title="하도급 관리" :columns="columns" :data="items" :loading="loading" @create="openModal(null)">
      <template #filters>
        <a-select v-model:value="filterSite" placeholder="현장" style="width:160px" allow-clear @change="load">
          <a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option>
        </a-select>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'contract_amount'">{{ Number(record.contract_amount).toLocaleString() }}</template>
        <template v-if="column.key === 'status'"><a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status === 'active' ? '진행중' : '완료' }}</a-tag></template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a @click="openModal(record)">수정</a>
            <a @click="openBillingModal(record)">기성</a>
          </a-space>
        </template>
      </template>
    </CrudTable>
    <a-modal v-model:open="modalOpen" :title="editItem ? '하도급 수정' : '하도급 등록'" width="680px" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="10"><a-form-item label="계약번호" name="subcontract_no" :rules="[{required:true}]"><a-input v-model:value="form.subcontract_no" /></a-form-item></a-col>
          <a-col :span="14"><a-form-item label="계약명" name="contract_name" :rules="[{required:true}]"><a-input v-model:value="form.contract_name" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="현장" name="site_id"><a-select v-model:value="form.site_id" show-search allow-clear :filter-option="fopt"><a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option></a-select></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="협력사" name="vendor_id"><a-select v-model:value="form.vendor_id" show-search allow-clear :filter-option="fopt"><a-select-option v-for="v in vendors" :key="v.id" :value="v.id">{{ v.company_name }}</a-select-option></a-select></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="계약금액" name="contract_amount"><a-input-number v-model:value="form.contract_amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="선급금" name="advance_payment"><a-input-number v-model:value="form.advance_payment" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="하자보증율(%)" name="retention_rate"><a-input-number v-model:value="form.retention_rate" style="width:100%" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="착공일" name="start_date"><a-date-picker v-model:value="form.start_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="준공일" name="end_date"><a-date-picker v-model:value="form.end_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="24"><a-form-item label="지급조건" name="payment_terms"><a-textarea v-model:value="form.payment_terms" :rows="2" /></a-form-item></a-col>
        </a-row>
      </a-form>
    </a-modal>

    <!-- 기성 모달 -->
    <a-modal v-model:open="billingModalOpen" title="하도급 기성" width="700px" :footer="null">
      <a-button type="primary" @click="addBillingOpen=true" style="margin-bottom:16px">기성 추가</a-button>
      <a-table :columns="bColumns" :data-source="billings" size="small" :pagination="false">
        <template #bodyCell="{ column, record }">
          <template v-if="['billing_amount','total_amount'].includes(column.key)">{{ Number(record[column.key]).toLocaleString() }}</template>
          <template v-if="column.key === 'status'"><a-tag>{{ record.status }}</a-tag></template>
          <template v-if="column.key === 'bAction'">
            <a-popconfirm v-if="record.status === 'draft'" title="승인?" @confirm="approveBilling(record.id)"><a style="color:green">승인</a></a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-modal>

    <a-modal v-model:open="addBillingOpen" title="기성 등록" @ok="handleAddBilling" :confirm-loading="saving">
      <a-form :model="billingForm" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="10"><a-form-item label="기성번호"><a-input v-model:value="billingForm.billing_no" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="기성일"><a-date-picker v-model:value="billingForm.billing_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="6"><a-form-item label="회차"><a-input-number v-model:value="billingForm.billing_seq" style="width:100%" :min="1" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="기성율(%)"><a-input-number v-model:value="billingForm.progress_rate" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="기성금액"><a-input-number v-model:value="billingForm.billing_amount" style="width:100%" @change="calcBVat" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="부가세"><a-input-number v-model:value="billingForm.vat_amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="합계"><a-input-number v-model:value="billingForm.total_amount" style="width:100%" /></a-form-item></a-col>
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

const items = ref([]), sites = ref([]), vendors = ref([]), billings = ref([])
const loading = ref(false), saving = ref(false), modalOpen = ref(false), editItem = ref(null)
const filterSite = ref(null), formRef = ref(), billingModalOpen = ref(false), addBillingOpen = ref(false)
const selectedSub = ref(null)
const form = reactive({ subcontract_no: '', site_id: null, vendor_id: null, contract_name: '', cost_code_id: null, contract_amount: 0, advance_payment: 0, retention_rate: 0, start_date: null, end_date: null, payment_terms: '' })
const billingForm = reactive({ billing_no: '', subcontract_id: null, site_id: null, billing_seq: 1, billing_date: null, progress_rate: 0, billing_amount: 0, vat_amount: 0, total_amount: 0 })
const fopt = (input, opt) => opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())
function calcBVat() { billingForm.vat_amount = Math.round(billingForm.billing_amount * 0.1); billingForm.total_amount = billingForm.billing_amount + billingForm.vat_amount }
const columns = [
  { title: '계약번호', dataIndex: 'subcontract_no', width: 140, align: 'center' },
  { title: '계약명',  dataIndex: 'contract_name',  width: 220, align: 'center', ellipsis: true },
  { title: '계약금액', key: 'contract_amount',      width: 140, align: 'right' },
  { title: '착공',    dataIndex: 'start_date',      width: 110, align: 'center' },
  { title: '준공',    dataIndex: 'end_date',        width: 110, align: 'center' },
  { title: '상태',    key: 'status',                width: 90,  align: 'center' },
  { title: '관리',    key: 'action',                width: 90,  align: 'center', fixed: 'right' },
]
const bColumns = [
  { title: '기성번호', dataIndex: 'billing_no', width: 130 }, { title: '기성일', dataIndex: 'billing_date', width: 110 },
  { title: '기성율', dataIndex: 'progress_rate', width: 80, customRender: ({text}) => text + '%' },
  { title: '기성금액', key: 'billing_amount', align: 'right' }, { title: '합계', key: 'total_amount', align: 'right' },
  { title: '상태', key: 'status', width: 90 }, { title: '관리', key: 'bAction', width: 70 },
]
async function load() {
  loading.value = true
  try {
    const [s, v, sub] = await Promise.all([masterApi.getSites({}), masterApi.getCompanies({ company_type: 'vendor' }), purchaseApi.getSubcontracts({ site_id: filterSite.value || undefined })])
    sites.value = s.data; vendors.value = v.data; items.value = sub.data
  } finally { loading.value = false }
}
function openModal(item) {
  editItem.value = item
  Object.assign(form, item || { subcontract_no: '', site_id: null, vendor_id: null, contract_name: '', cost_code_id: null, contract_amount: 0, advance_payment: 0, retention_rate: 0, start_date: null, end_date: null, payment_terms: '' })
  modalOpen.value = true
}
async function handleSave() {
  try { saving.value = true; editItem.value ? await purchaseApi.updateSubcontract(editItem.value.id, form) : await purchaseApi.createSubcontract(form); message.success('저장'); modalOpen.value = false; load() }
  catch (e) { message.error(e.response?.data?.detail || '오류') } finally { saving.value = false }
}
async function openBillingModal(sub) {
  selectedSub.value = sub
  billings.value = (await purchaseApi.getSubcontractBillings({ subcontract_id: sub.id })).data
  billingModalOpen.value = true
}
async function handleAddBilling() {
  try { saving.value = true; billingForm.subcontract_id = selectedSub.value.id; billingForm.site_id = selectedSub.value.site_id; await purchaseApi.createSubcontractBilling(billingForm); message.success('등록'); addBillingOpen.value = false; billings.value = (await purchaseApi.getSubcontractBillings({ subcontract_id: selectedSub.value.id })).data }
  catch (e) { message.error(e.response?.data?.detail || '오류') } finally { saving.value = false }
}
async function approveBilling(id) {
  try { await purchaseApi.approveSubcontractBilling(id); message.success('승인'); billings.value = (await purchaseApi.getSubcontractBillings({ subcontract_id: selectedSub.value.id })).data }
  catch (e) { message.error(e.response?.data?.detail || '오류') }
}
onMounted(load)
</script>
