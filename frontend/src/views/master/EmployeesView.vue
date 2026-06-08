<template>
  <div>
    <CrudTable title="직원 관리" :columns="columns" :data="items" :loading="loading" @create="openModal(null)">
      <template #filters>
        <a-select v-model:value="filterType" placeholder="고용형태" style="width:100px" allow-clear @change="load">
          <a-select-option value="regular">정규직</a-select-option>
          <a-select-option value="daily">일용직</a-select-option>
          <a-select-option value="contract">계약직</a-select-option>
        </a-select>
        <a-input-search v-model:value="search" placeholder="이름 검색" style="width:160px" @search="load" allow-clear />
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'emp_type'">
          <a-tag :color="empTypeColor[record.emp_type]">{{ empTypeLabel[record.emp_type] }}</a-tag>
        </template>
        <template v-if="column.key === 'daily_wage'">{{ Number(record.daily_wage).toLocaleString() }}</template>
        <template v-if="column.key === 'action'"><a @click="openModal(record)">수정</a></template>
      </template>
    </CrudTable>

    <a-modal v-model:open="modalOpen" :title="editItem ? '직원 수정' : '직원 등록'" width="640px" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="8"><a-form-item label="사원코드" name="emp_code" :rules="[{required:true}]"><a-input v-model:value="form.emp_code" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="이름" name="name" :rules="[{required:true}]"><a-input v-model:value="form.name" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="고용형태" name="emp_type"><a-select v-model:value="form.emp_type"><a-select-option value="regular">정규직</a-select-option><a-select-option value="daily">일용직</a-select-option><a-select-option value="contract">계약직</a-select-option></a-select></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="직위" name="position"><a-input v-model:value="form.position" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="입사일" name="hire_date"><a-date-picker v-model:value="form.hire_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="전화번호" name="phone"><a-input v-model:value="form.phone" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="일급(일용직)" name="daily_wage"><a-input-number v-model:value="form.daily_wage" style="width:100%" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="월급(정규직)" name="monthly_salary"><a-input-number v-model:value="form.monthly_salary" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="은행명" name="bank_name"><a-input v-model:value="form.bank_name" /></a-form-item></a-col>
          <a-col :span="16"><a-form-item label="계좌번호" name="bank_account"><a-input v-model:value="form.bank_account" /></a-form-item></a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import CrudTable from '@/components/common/CrudTable.vue'
import { masterApi } from '@/api'

const items = ref([]), loading = ref(false), saving = ref(false)
const modalOpen = ref(false), editItem = ref(null), filterType = ref(null), search = ref(''), formRef = ref()
const form = reactive({ emp_code: '', name: '', emp_type: 'regular', position: '', hire_date: null, phone: '', daily_wage: 0, monthly_salary: 0, bank_name: '', bank_account: '' })
const empTypeColor = { regular: 'blue', daily: 'orange', contract: 'green' }
const empTypeLabel = { regular: '정규직', daily: '일용직', contract: '계약직' }

const columns = [
  { title: '사원코드', dataIndex: 'emp_code', width: 100 },
  { title: '이름', dataIndex: 'name', width: 90 },
  { title: '직위', dataIndex: 'position', width: 90 },
  { title: '고용형태', key: 'emp_type', width: 90 },
  { title: '입사일', dataIndex: 'hire_date', width: 110 },
  { title: '일급', key: 'daily_wage', align: 'right', width: 110 },
  { title: '관리', key: 'action', width: 70, fixed: 'right' },
]

async function load() {
  loading.value = true
  try { items.value = (await masterApi.getEmployees({ emp_type: filterType.value || undefined, search: search.value || undefined })).data }
  finally { loading.value = false }
}
function openModal(item) {
  editItem.value = item
  if (item) Object.assign(form, item)
  else Object.assign(form, { emp_code: '', name: '', emp_type: 'regular', position: '', hire_date: null, phone: '', daily_wage: 0, monthly_salary: 0, bank_name: '', bank_account: '' })
  modalOpen.value = true
}
async function handleSave() {
  try {
    await formRef.value.validate(); saving.value = true
    if (editItem.value) { await masterApi.updateEmployee(editItem.value.id, form); message.success('수정되었습니다.') }
    else { await masterApi.createEmployee(form); message.success('등록되었습니다.') }
    modalOpen.value = false; load()
  } catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') }
  finally { saving.value = false }
}
onMounted(load)
</script>
