<template>
  <div>
    <CrudTable title="노무비 투입" :columns="columns" :data="items" :loading="loading" @create="openModal(null)">
      <template #filters>
        <a-select v-model:value="filterSite" placeholder="현장" style="width:160px" allow-clear @change="load">
          <a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option>
        </a-select>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="['amount','net_amount'].includes(column.key)">{{ Number(record[column.key]).toLocaleString() }}</template>
        <template v-if="column.key === 'status'"><a-tag :color="record.status === 'confirmed' ? 'green' : 'default'">{{ record.status === 'confirmed' ? '확정' : '작성중' }}</a-tag></template>
        <template v-if="column.key === 'action'"><a @click="openModal(record)">수정</a></template>
      </template>
    </CrudTable>
    <a-modal v-model:open="modalOpen" title="노무비 투입 등록" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="24"><a-form-item label="현장" name="site_id" :rules="[{required:true}]"><a-select v-model:value="form.site_id" show-search allow-clear :filter-option="fopt"><a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option></a-select></a-form-item></a-col>
          <a-col :span="24"><a-form-item label="직원" name="employee_id" :rules="[{required:true}]"><a-select v-model:value="form.employee_id" show-search allow-clear :filter-option="fopt" @change="onEmpChange"><a-select-option v-for="e in employees" :key="e.id" :value="e.id">{{ e.name }} ({{ e.emp_type }})</a-select-option></a-select></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="작업일" name="work_date" :rules="[{required:true}]"><a-date-picker v-model:value="form.work_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="6"><a-form-item label="작업일수" name="work_days"><a-input-number v-model:value="form.work_days" style="width:100%" :step="0.5" @change="calcAmount" /></a-form-item></a-col>
          <a-col :span="6"><a-form-item label="일급" name="daily_wage"><a-input-number v-model:value="form.daily_wage" style="width:100%" @change="calcAmount" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="노무비 합계" name="amount"><a-input-number v-model:value="form.amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="4대보험 등" name="insurance_amount"><a-input-number v-model:value="form.insurance_amount" style="width:100%" @change="calcNet" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="실지급액" name="net_amount"><a-input-number v-model:value="form.net_amount" style="width:100%" /></a-form-item></a-col>
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

const items = ref([]), sites = ref([]), employees = ref([])
const loading = ref(false), saving = ref(false), modalOpen = ref(false)
const filterSite = ref(null), formRef = ref()
const form = reactive({ site_id: null, employee_id: null, cost_code_id: null, work_date: null, work_days: 1, daily_wage: 0, amount: 0, insurance_amount: 0, net_amount: 0, notes: '' })
const fopt = (input, opt) => opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())
function calcAmount() { form.amount = form.work_days * form.daily_wage; calcNet() }
function calcNet() { form.net_amount = form.amount - form.insurance_amount }
function onEmpChange(id) { const e = employees.value.find(e => e.id === id); if (e) { form.daily_wage = e.daily_wage; calcAmount() } }
const columns = [
  { title: '현장ID',  dataIndex: 'site_id',     width: 110, align: 'center' },
  { title: '직원ID',  dataIndex: 'employee_id', width: 110, align: 'center' },
  { title: '작업일',  dataIndex: 'work_date',   width: 110, align: 'center' },
  { title: '일수',    dataIndex: 'work_days',   width: 80,  align: 'center' },
  { title: '노무비',  key: 'amount',            width: 130, align: 'right' },
  { title: '실지급액', key: 'net_amount',       width: 130, align: 'right' },
  { title: '상태',    key: 'status',            width: 90,  align: 'center' },
  { title: '관리',    key: 'action',            width: 80,  align: 'center', fixed: 'right' },
]
async function load() {
  loading.value = true
  try {
    const [l, s, e] = await Promise.all([purchaseApi.getLaborInputs({ site_id: filterSite.value || undefined }), masterApi.getSites({}), masterApi.getEmployees({})])
    items.value = l.data; sites.value = s.data; employees.value = e.data
  } finally { loading.value = false }
}
function openModal(item) { Object.assign(form, item || { site_id: null, employee_id: null, cost_code_id: null, work_date: null, work_days: 1, daily_wage: 0, amount: 0, insurance_amount: 0, net_amount: 0, notes: '' }); modalOpen.value = true }
async function handleSave() {
  try { await formRef.value.validate(); saving.value = true; await purchaseApi.createLaborInput(form); message.success('등록'); modalOpen.value = false; load() }
  catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') } finally { saving.value = false }
}
onMounted(load)
</script>
