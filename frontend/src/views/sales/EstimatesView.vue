<template>
  <div>
    <CrudTable title="견적 관리" :columns="columns" :data="items" :loading="loading" @create="openModal(null)">
      <template #filters>
        <a-input-search v-model:value="search" placeholder="견적명 검색" style="width:200px" @search="load" allow-clear />
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'total_amount'">{{ Number(record.total_amount).toLocaleString() }}</template>
        <template v-if="column.key === 'status'"><a-tag :color="sColor[record.status]">{{ sLabel[record.status] }}</a-tag></template>
        <template v-if="column.key === 'action'"><a @click="openModal(record)">수정</a></template>
      </template>
    </CrudTable>
    <a-modal v-model:open="modalOpen" :title="editItem ? '견적 수정' : '견적 등록'" width="800px" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="10"><a-form-item label="견적번호" name="estimate_no" :rules="[{required:true}]"><a-input v-model:value="form.estimate_no" /></a-form-item></a-col>
          <a-col :span="14"><a-form-item label="견적제목" name="title" :rules="[{required:true}]"><a-input v-model:value="form.title" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="발주처" name="client_id">
            <a-select v-model:value="form.client_id" show-search allow-clear :filter-option="filterOpt">
              <a-select-option v-for="c in clients" :key="c.id" :value="c.id">{{ c.company_name }}</a-select-option>
            </a-select>
          </a-form-item></a-col>
          <a-col :span="6"><a-form-item label="견적일" name="estimate_date"><a-date-picker v-model:value="form.estimate_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="6"><a-form-item label="유형" name="estimate_type"><a-select v-model:value="form.estimate_type"><a-select-option value="bas">BAS</a-select-option><a-select-option value="other">기타</a-select-option></a-select></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="재료비"><a-input-number v-model:value="form.material_amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="노무비"><a-input-number v-model:value="form.labor_amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="외주비"><a-input-number v-model:value="form.subcontract_amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="경비"><a-input-number v-model:value="form.expense_amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="제경비(판관비)"><a-input-number v-model:value="form.overhead_amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="이익금"><a-input-number v-model:value="form.profit_amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="합계금액" name="total_amount"><a-input-number v-model:value="form.total_amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="상태" name="status"><a-select v-model:value="form.status"><a-select-option value="draft">작성중</a-select-option><a-select-option value="submitted">제출</a-select-option><a-select-option value="approved">승인</a-select-option></a-select></a-form-item></a-col>
          <a-col :span="24"><a-form-item label="비고" name="notes"><a-textarea v-model:value="form.notes" :rows="2" /></a-form-item></a-col>
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

const items = ref([]), clients = ref([]), loading = ref(false), saving = ref(false)
const modalOpen = ref(false), editItem = ref(null), search = ref(''), formRef = ref()
const form = reactive({ estimate_no: '', title: '', client_id: null, estimate_type: 'bas', estimate_date: null, total_amount: 0, labor_amount: 0, material_amount: 0, subcontract_amount: 0, expense_amount: 0, overhead_amount: 0, profit_amount: 0, status: 'draft', notes: '' })
const sColor = { draft: 'default', submitted: 'blue', approved: 'green', converted: 'purple' }
const sLabel = { draft: '작성중', submitted: '제출', approved: '승인', converted: '수주전환' }
const filterOpt = (input, opt) => opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())
const columns = [
  { title: '견적번호', dataIndex: 'estimate_no', width: 140, align: 'center' },
  { title: '제목',    dataIndex: 'title',        width: 220, align: 'center', ellipsis: true },
  { title: '견적금액', key: 'total_amount',       width: 140, align: 'right' },
  { title: '견적일',  dataIndex: 'estimate_date', width: 110, align: 'center' },
  { title: '상태',    key: 'status',              width: 90,  align: 'center' },
  { title: '관리',    key: 'action',              width: 80,  align: 'center', fixed: 'right' },
]
async function load() {
  loading.value = true
  try {
    const [e, c] = await Promise.all([salesApi.getEstimates({ search: search.value || undefined }), masterApi.getCompanies({ company_type: 'client' })])
    items.value = e.data; clients.value = c.data
  } finally { loading.value = false }
}
function openModal(item) {
  editItem.value = item
  if (item) Object.assign(form, item); else Object.assign(form, { estimate_no: '', title: '', client_id: null, estimate_type: 'bas', estimate_date: null, total_amount: 0, labor_amount: 0, material_amount: 0, subcontract_amount: 0, expense_amount: 0, overhead_amount: 0, profit_amount: 0, status: 'draft', notes: '' })
  modalOpen.value = true
}
async function handleSave() {
  try {
    await formRef.value.validate(); saving.value = true
    if (editItem.value) { await salesApi.updateEstimate(editItem.value.id, form); message.success('수정') }
    else { await salesApi.createEstimate(form); message.success('등록') }
    modalOpen.value = false; load()
  } catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') }
  finally { saving.value = false }
}
onMounted(load)
</script>
