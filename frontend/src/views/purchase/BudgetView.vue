<template>
  <div>
    <CrudTable title="예산 관리" :columns="columns" :data="items" :loading="loading" @create="openModal(null)">
      <template #filters>
        <a-select v-model:value="filterSite" placeholder="현장" style="width:180px" allow-clear @change="load">
          <a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option>
        </a-select>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'total_amount'">{{ Number(record.total_amount).toLocaleString() }}</template>
        <template v-if="column.key === 'status'"><a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status }}</a-tag></template>
        <template v-if="column.key === 'action'"><a @click="openModal(record)">수정</a></template>
      </template>
    </CrudTable>
    <a-modal v-model:open="modalOpen" :title="editItem ? '예산 수정' : '예산 등록'" width="700px" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="24"><a-form-item label="현장" name="site_id" :rules="[{required:true}]"><a-select v-model:value="form.site_id" show-search allow-clear :filter-option="fopt"><a-select-option v-for="s in sites" :key="s.id" :value="s.id">{{ s.site_name }}</a-select-option></a-select></a-form-item></a-col>
          <a-col :span="16"><a-form-item label="예산명" name="budget_name"><a-input v-model:value="form.budget_name" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="버전" name="version"><a-input-number v-model:value="form.version" style="width:100%" :min="1" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="예산 합계금액" name="total_amount"><a-input-number v-model:value="form.total_amount" style="width:100%" /></a-form-item></a-col>
          <a-col :span="24"><a-form-item label="비고"><a-textarea v-model:value="form.notes" :rows="2" /></a-form-item></a-col>
        </a-row>
        <a-divider>예산 항목</a-divider>
        <a-button type="dashed" block @click="addItem" style="margin-bottom:16px">항목 추가</a-button>
        <div v-for="(item, idx) in form.items" :key="idx" style="display:flex;gap:8px;margin-bottom:8px;align-items:center">
          <a-select v-model:value="item.cost_type" style="width:100px" placeholder="원가유형">
            <a-select-option value="material">재료비</a-select-option>
            <a-select-option value="labor">노무비</a-select-option>
            <a-select-option value="subcontract">외주비</a-select-option>
            <a-select-option value="expense">경비</a-select-option>
          </a-select>
          <a-input v-model:value="item.item_name" placeholder="항목명" style="flex:1" />
          <a-input-number v-model:value="item.budgeted_amount" placeholder="예산금액" style="width:130px" />
          <a-button danger @click="removeItem(idx)">삭제</a-button>
        </div>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import CrudTable from '@/components/common/CrudTable.vue'
import { budgetApi, masterApi } from '@/api'

const items = ref([]), sites = ref([]), loading = ref(false), saving = ref(false)
const modalOpen = ref(false), editItem = ref(null), filterSite = ref(null), formRef = ref()
const form = reactive({ site_id: null, contract_id: null, version: 1, budget_name: '', total_amount: 0, notes: '', items: [] })
const fopt = (input, opt) => opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())
const columns = [
  { title: '현장ID',  dataIndex: 'site_id',     width: 110, align: 'center' },
  { title: '예산명',  dataIndex: 'budget_name', width: 220, align: 'center', ellipsis: true },
  { title: '버전',    dataIndex: 'version',     width: 80,  align: 'center' },
  { title: '예산금액', key: 'total_amount',     width: 140, align: 'right' },
  { title: '상태',    key: 'status',            width: 90,  align: 'center' },
  { title: '관리',    key: 'action',            width: 80,  align: 'center', fixed: 'right' },
]
function addItem() { form.items.push({ cost_type: 'material', item_name: '', budgeted_amount: 0, execution_amount: 0 }) }
function removeItem(idx) { form.items.splice(idx, 1) }
async function load() {
  loading.value = true
  try {
    const [b, s] = await Promise.all([budgetApi.getBudgets({ site_id: filterSite.value || undefined }), masterApi.getSites({})])
    items.value = b.data; sites.value = s.data
  } finally { loading.value = false }
}
function openModal(item) {
  editItem.value = item
  if (item) Object.assign(form, { ...item, items: item.items || [] })
  else Object.assign(form, { site_id: null, contract_id: null, version: 1, budget_name: '', total_amount: 0, notes: '', items: [] })
  modalOpen.value = true
}
async function handleSave() {
  try { await formRef.value.validate(); saving.value = true; editItem.value ? await budgetApi.updateBudget(editItem.value.id, form) : await budgetApi.createBudget(form); message.success('저장'); modalOpen.value = false; load() }
  catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') } finally { saving.value = false }
}
onMounted(load)
</script>
