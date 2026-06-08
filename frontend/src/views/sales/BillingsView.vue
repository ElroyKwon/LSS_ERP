<template>
  <div>
    <CrudTable title="기성 청구" :columns="columns" :data="items" :loading="loading" @create="openModal(null)">
      <template #filters>
        <a-select v-model:value="filterStatus" placeholder="상태" style="width:100px" allow-clear @change="load">
          <a-select-option value="draft">작성중</a-select-option>
          <a-select-option value="approved">승인</a-select-option>
          <a-select-option value="invoiced">세금계산서</a-select-option>
        </a-select>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'billing_amount'">{{ Number(record.billing_amount).toLocaleString() }}</template>
        <template v-if="column.key === 'total_amount'">{{ Number(record.total_amount).toLocaleString() }}</template>
        <template v-if="column.key === 'status'"><a-tag :color="sColor[record.status]">{{ sLabel[record.status] }}</a-tag></template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a @click="openModal(record)">수정</a>
            <a-popconfirm v-if="record.status === 'draft'" title="승인하시겠습니까?" @confirm="approve(record.id)">
              <a style="color:#52c41a">승인</a>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </CrudTable>
    <a-modal v-model:open="modalOpen" :title="editItem ? '기성 수정' : '기성 등록'" width="680px" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="10"><a-form-item label="기성번호" name="billing_no" :rules="[{required:true}]"><a-input v-model:value="form.billing_no" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="기성일" name="billing_date" :rules="[{required:true}]"><a-date-picker v-model:value="form.billing_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="6"><a-form-item label="회차" name="billing_seq" :rules="[{required:true}]"><a-input-number v-model:value="form.billing_seq" style="width:100%" :min="1" /></a-form-item></a-col>
          <a-col :span="24"><a-form-item label="계약" name="contract_id" :rules="[{required:true}]">
            <a-select v-model:value="form.contract_id" show-search allow-clear :filter-option="filterOpt" @change="onContractChange">
              <a-select-option v-for="c in contracts" :key="c.id" :value="c.id">{{ c.contract_no }} {{ c.contract_name }}</a-select-option>
            </a-select>
          </a-form-item></a-col>
          <a-col :span="8"><a-form-item label="기성율(%)" name="progress_rate"><a-input-number v-model:value="form.progress_rate" style="width:100%" :min="0" :max="100" :step="0.1" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="기성금액(공급가액)" name="billing_amount" :rules="[{required:true}]"><a-input-number v-model:value="form.billing_amount" style="width:100%" @change="calcVat" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="부가세" name="vat_amount"><a-input-number v-model:value="form.vat_amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="합계(VAT포함)" name="total_amount"><a-input-number v-model:value="form.total_amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="만기일" name="due_date"><a-date-picker v-model:value="form.due_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
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
import { salesApi } from '@/api'

const items = ref([]), contracts = ref([]), loading = ref(false), saving = ref(false)
const modalOpen = ref(false), editItem = ref(null), filterStatus = ref(null), formRef = ref()
const form = reactive({ billing_no: '', contract_id: null, site_id: null, billing_seq: 1, billing_date: null, progress_rate: 0, billing_amount: 0, vat_amount: 0, total_amount: 0, due_date: null, notes: '' })
const sColor = { draft: 'default', submitted: 'blue', approved: 'green', invoiced: 'purple' }
const sLabel = { draft: '작성중', submitted: '제출', approved: '승인', invoiced: '세금계산서' }
const filterOpt = (input, opt) => opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())
const columns = [
  { title: '기성번호',   dataIndex: 'billing_no',    width: 140, align: 'center' },
  { title: '기성일',    dataIndex: 'billing_date',   width: 110, align: 'center' },
  { title: '회차',      dataIndex: 'billing_seq',    width: 70,  align: 'center' },
  { title: '기성율',    dataIndex: 'progress_rate',  width: 90,  align: 'center', customRender: ({text}) => text + '%' },
  { title: '기성금액',  key: 'billing_amount',       width: 140, align: 'right' },
  { title: '합계(VAT)', key: 'total_amount',         width: 140, align: 'right' },
  { title: '상태',      key: 'status',               width: 90,  align: 'center' },
  { title: '관리',      key: 'action',               width: 110, align: 'center', fixed: 'right' },
]
function calcVat() {
  form.vat_amount = Math.round(form.billing_amount * 0.1)
  form.total_amount = form.billing_amount + form.vat_amount
}
function onContractChange(id) {
  const c = contracts.value.find(c => c.id === id)
  if (c) form.site_id = c.site_id
}
async function load() {
  loading.value = true
  try {
    const [b, c] = await Promise.all([salesApi.getBillings({ status: filterStatus.value || undefined }), salesApi.getContracts({})])
    items.value = b.data; contracts.value = c.data
  } finally { loading.value = false }
}
function openModal(item) {
  editItem.value = item
  if (item) Object.assign(form, item); else Object.assign(form, { billing_no: '', contract_id: null, site_id: null, billing_seq: 1, billing_date: null, progress_rate: 0, billing_amount: 0, vat_amount: 0, total_amount: 0, due_date: null, notes: '' })
  modalOpen.value = true
}
async function handleSave() {
  try {
    await formRef.value.validate(); saving.value = true
    await salesApi.createBilling(form); message.success('등록')
    modalOpen.value = false; load()
  } catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') }
  finally { saving.value = false }
}
async function approve(id) {
  try { await salesApi.approveBilling(id); message.success('승인되었습니다.'); load() }
  catch (e) { message.error(e.response?.data?.detail || '오류') }
}
onMounted(load)
</script>
