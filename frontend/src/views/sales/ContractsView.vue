<template>
  <div>
    <CrudTable title="계약 관리 (수주)" :columns="columns" :data="items" :loading="loading" @create="openModal(null)">
      <template #filters>
        <a-select v-model:value="filterStatus" placeholder="상태" style="width:100px" allow-clear @change="load">
          <a-select-option value="active">진행중</a-select-option>
          <a-select-option value="completed">완료</a-select-option>
        </a-select>
        <a-input-search v-model:value="search" placeholder="계약명 검색" style="width:200px" @search="load" allow-clear />
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'current_amount'">{{ Number(record.current_amount).toLocaleString() }}</template>
        <template v-if="column.key === 'contract_type'"><a-tag>{{ ctLabel[record.contract_type] }}</a-tag></template>
        <template v-if="column.key === 'status'"><a-tag :color="sColor[record.status]">{{ sLabel[record.status] }}</a-tag></template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a @click="openModal(record)">수정</a>
            <a @click="openChangeModal(record)">변경이력</a>
          </a-space>
        </template>
      </template>
    </CrudTable>

    <!-- 계약 등록/수정 모달 -->
    <a-modal v-model:open="modalOpen" :title="editItem ? '계약 수정' : '계약 등록'" width="700px" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="10"><a-form-item label="계약번호" name="contract_no" :rules="[{required:true}]"><a-input v-model:value="form.contract_no" /></a-form-item></a-col>
          <a-col :span="14"><a-form-item label="계약명" name="contract_name" :rules="[{required:true}]"><a-input v-model:value="form.contract_name" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="현장" name="site_id">
            <a-select v-model:value="form.site_id" show-search allow-clear :filter-option="filterOpt">
              <a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option>
            </a-select>
          </a-form-item></a-col>
          <a-col :span="12"><a-form-item label="발주처" name="client_id">
            <a-select v-model:value="form.client_id" show-search allow-clear :filter-option="filterOpt">
              <a-select-option v-for="c in clients" :key="c.id" :value="c.id">{{ c.company_name }}</a-select-option>
            </a-select>
          </a-form-item></a-col>
          <a-col :span="8"><a-form-item label="계약유형" name="contract_type" :rules="[{required:true}]">
            <a-select v-model:value="form.contract_type"><a-select-option value="lump_sum">총액</a-select-option><a-select-option value="unit_price">단가</a-select-option><a-select-option value="actual_cost">실비</a-select-option></a-select>
          </a-form-item></a-col>
          <a-col :span="8"><a-form-item label="매출인식방식" name="revenue_type">
            <a-select v-model:value="form.revenue_type"><a-select-option value="general">일반</a-select-option><a-select-option value="progress">진행율</a-select-option></a-select>
          </a-form-item></a-col>
          <a-col :span="8"><a-form-item label="계약일" name="contract_date"><a-date-picker v-model:value="form.contract_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="계약금액(원)" name="original_amount"><a-input-number v-model:value="form.original_amount" style="width:100%" :step="1000000" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="원가금액(원)" name="original_cost"><a-input-number v-model:value="form.original_cost" style="width:100%" :step="1000000" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="착공일" name="start_date"><a-date-picker v-model:value="form.start_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="준공예정일" name="end_date"><a-date-picker v-model:value="form.end_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="24"><a-form-item label="비고" name="notes"><a-textarea v-model:value="form.notes" :rows="2" /></a-form-item></a-col>
        </a-row>
      </a-form>
    </a-modal>

    <!-- 변경이력 모달 -->
    <a-modal v-model:open="changeModalOpen" title="계약변경 이력" width="900px" :footer="null">
      <a-button type="primary" @click="openAddChange" style="margin-bottom:16px">변경 추가</a-button>
      <a-table :columns="changeColumns" :data-source="changes" size="small" :pagination="false">
        <template #bodyCell="{ column, record }">
          <template v-if="['amount_before','amount_change','amount_after'].includes(column.key)">{{ Number(record[column.key]).toLocaleString() }}</template>
        </template>
      </a-table>
    </a-modal>

    <!-- 변경 추가 -->
    <a-modal v-model:open="addChangeOpen" title="계약변경 등록" @ok="handleAddChange" :confirm-loading="saving">
      <a-form :model="changeForm" layout="vertical" ref="changeFormRef">
        <a-row :gutter="16">
          <a-col :span="8"><a-form-item label="변경회차" name="change_no" :rules="[{required:true}]"><a-input-number v-model:value="changeForm.change_no" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="변경일" name="change_date" :rules="[{required:true}]"><a-date-picker v-model:value="changeForm.change_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="준공변경일" name="end_date_after"><a-date-picker v-model:value="changeForm.end_date_after" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="계약금액 증감" name="amount_change"><a-input-number v-model:value="changeForm.amount_change" style="width:100%" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="원가 증감" name="cost_change"><a-input-number v-model:value="changeForm.cost_change" style="width:100%" /></a-form-item></a-col>
          <a-col :span="24"><a-form-item label="변경사유" name="reason"><a-textarea v-model:value="changeForm.reason" :rows="3" /></a-form-item></a-col>
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

const items = ref([]), sites = ref([]), clients = ref([])
const loading = ref(false), saving = ref(false), modalOpen = ref(false)
const editItem = ref(null), filterStatus = ref(null), search = ref(''), formRef = ref()
const changeModalOpen = ref(false), addChangeOpen = ref(false), changes = ref([])
const selectedContract = ref(null), changeFormRef = ref()

const form = reactive({ contract_no: '', contract_name: '', site_id: null, estimate_id: null, client_id: null, contract_type: 'lump_sum', revenue_type: 'general', original_amount: 0, current_amount: 0, original_cost: 0, current_cost: 0, contract_date: null, start_date: null, end_date: null, status: 'active', notes: '' })
const changeForm = reactive({ contract_id: null, change_no: 1, change_date: null, amount_change: 0, cost_change: 0, end_date_after: null, reason: '' })
const ctLabel = { lump_sum: '총액', unit_price: '단가', actual_cost: '실비' }
const sColor = { active: 'green', completed: 'blue', cancelled: 'red' }
const sLabel = { active: '진행중', completed: '완료', cancelled: '취소' }

const columns = [
  { title: '계약번호',   dataIndex: 'contract_no',   width: 140, align: 'center' },
  { title: '계약명',    dataIndex: 'contract_name',  width: 220, align: 'center', ellipsis: true },
  { title: '유형',      key: 'contract_type',        width: 90,  align: 'center' },
  { title: '현재계약금액', key: 'current_amount',    width: 140, align: 'right' },
  { title: '계약일',    dataIndex: 'contract_date',  width: 110, align: 'center' },
  { title: '준공예정',  dataIndex: 'end_date',       width: 110, align: 'center' },
  { title: '상태',      key: 'status',               width: 90,  align: 'center' },
  { title: '관리',      key: 'action',               width: 110, align: 'center', fixed: 'right' },
]
const changeColumns = [
  { title: '회차', dataIndex: 'change_no', width: 60 },
  { title: '변경일', dataIndex: 'change_date', width: 110 },
  { title: '변경전금액', key: 'amount_before', align: 'right' },
  { title: '증감금액', key: 'amount_change', align: 'right' },
  { title: '변경후금액', key: 'amount_after', align: 'right' },
  { title: '사유', dataIndex: 'reason', ellipsis: true },
]
const filterOpt = (input, opt) => opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())

async function load() {
  loading.value = true
  try {
    const [c, s, cl] = await Promise.all([
      salesApi.getContracts({ status: filterStatus.value || undefined, search: search.value || undefined }),
      masterApi.getSites({}),
      masterApi.getCompanies({ company_type: 'client' }),
    ])
    items.value = c.data; sites.value = s.data; clients.value = cl.data
  } finally { loading.value = false }
}
function openModal(item) {
  editItem.value = item
  if (item) Object.assign(form, item); else Object.assign(form, { contract_no: '', contract_name: '', site_id: null, estimate_id: null, client_id: null, contract_type: 'lump_sum', revenue_type: 'general', original_amount: 0, current_amount: 0, original_cost: 0, current_cost: 0, contract_date: null, start_date: null, end_date: null, status: 'active', notes: '' })
  modalOpen.value = true
}
async function handleSave() {
  try {
    await formRef.value.validate(); saving.value = true
    if (editItem.value) { await salesApi.updateContract(editItem.value.id, form); message.success('수정') }
    else { await salesApi.createContract(form); message.success('등록') }
    modalOpen.value = false; load()
  } catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') }
  finally { saving.value = false }
}
async function openChangeModal(record) {
  selectedContract.value = record
  const res = await salesApi.getContractChanges(record.id)
  changes.value = res.data
  changeModalOpen.value = true
}
function openAddChange() {
  Object.assign(changeForm, { contract_id: selectedContract.value.id, change_no: changes.value.length + 1, change_date: null, amount_change: 0, cost_change: 0, end_date_after: null, reason: '' })
  addChangeOpen.value = true
}
async function handleAddChange() {
  try {
    saving.value = true
    await salesApi.createContractChange(changeForm); message.success('변경이력 등록')
    addChangeOpen.value = false
    const res = await salesApi.getContractChanges(selectedContract.value.id)
    changes.value = res.data; load()
  } catch (e) { message.error(e.response?.data?.detail || '오류') }
  finally { saving.value = false }
}
onMounted(load)
</script>
