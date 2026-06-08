<template>
  <div>
    <CrudTable title="원가코드 관리" :columns="columns" :data="items" :loading="loading" @create="openModal(null)" :scroll-x="800">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'cost_type'"><a-tag>{{ costTypeLabel[record.cost_type] || '-' }}</a-tag></template>
        <template v-if="column.key === 'action'"><a @click="openModal(record)">수정</a></template>
      </template>
    </CrudTable>
    <a-modal v-model:open="modalOpen" :title="editItem ? '원가코드 수정' : '원가코드 등록'" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="10"><a-form-item label="코드" name="code" :rules="[{required:true}]"><a-input v-model:value="form.code" /></a-form-item></a-col>
          <a-col :span="14"><a-form-item label="코드명" name="name" :rules="[{required:true}]"><a-input v-model:value="form.name" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="레벨" name="level"><a-input-number v-model:value="form.level" style="width:100%" :min="1" :max="5" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="원가유형" name="cost_type">
            <a-select v-model:value="form.cost_type" allow-clear>
              <a-select-option value="material">재료비</a-select-option>
              <a-select-option value="labor">노무비</a-select-option>
              <a-select-option value="subcontract">외주비</a-select-option>
              <a-select-option value="expense">경비</a-select-option>
              <a-select-option value="equipment">장비</a-select-option>
            </a-select>
          </a-form-item></a-col>
          <a-col :span="8"><a-form-item label="상위코드" name="parent_id">
            <a-select v-model:value="form.parent_id" allow-clear show-search :filter-option="filterOption">
              <a-select-option v-for="c in items" :key="c.id" :value="c.id">{{ c.code }} {{ c.name }}</a-select-option>
            </a-select>
          </a-form-item></a-col>
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
const modalOpen = ref(false), editItem = ref(null), formRef = ref()
const form = reactive({ code: '', name: '', level: 1, cost_type: null, parent_id: null })
const costTypeLabel = { material: '재료비', labor: '노무비', subcontract: '외주비', expense: '경비', equipment: '장비' }
const columns = [
  { title: '코드', dataIndex: 'code', width: 100 },
  { title: '코드명', dataIndex: 'name' },
  { title: '레벨', dataIndex: 'level', width: 60, align: 'center' },
  { title: '원가유형', key: 'cost_type', width: 90 },
  { title: '관리', key: 'action', width: 70, fixed: 'right' },
]
const filterOption = (input, opt) => opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())
async function load() {
  loading.value = true
  try { items.value = (await masterApi.getCostCodes()).data } finally { loading.value = false }
}
function openModal(item) {
  editItem.value = item
  if (item) Object.assign(form, item); else Object.assign(form, { code: '', name: '', level: 1, cost_type: null, parent_id: null })
  modalOpen.value = true
}
async function handleSave() {
  try {
    await formRef.value.validate(); saving.value = true
    if (editItem.value) { await masterApi.updateCostCode(editItem.value.id, form); message.success('수정') }
    else { await masterApi.createCostCode(form); message.success('등록') }
    modalOpen.value = false; load()
  } catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') }
  finally { saving.value = false }
}
onMounted(load)
</script>
