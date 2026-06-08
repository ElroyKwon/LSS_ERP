<template>
  <div>
    <CrudTable title="단가 관리" :columns="columns" :data="items" :loading="loading" @create="openModal(null)">
      <template #filters>
        <a-select v-model:value="filterYear" placeholder="적용연도" style="width:100px" allow-clear @change="load">
          <a-select-option v-for="y in years" :key="y" :value="y">{{ y }}년</a-select-option>
        </a-select>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'price'">{{ Number(record.price).toLocaleString() }}</template>
        <template v-if="column.key === 'action'"><a @click="openModal(record)">수정</a></template>
      </template>
    </CrudTable>
    <a-modal v-model:open="modalOpen" title="단가 등록" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="24"><a-form-item label="자재" name="material_id" :rules="[{required:true}]">
            <a-select v-model:value="form.material_id" show-search :filter-option="filterOption">
              <a-select-option v-for="m in materials" :key="m.id" :value="m.id">{{ m.material_code }} {{ m.material_name }}</a-select-option>
            </a-select>
          </a-form-item></a-col>
          <a-col :span="24"><a-form-item label="협력사(선택)" name="vendor_id">
            <a-select v-model:value="form.vendor_id" show-search allow-clear :filter-option="filterOption">
              <a-select-option v-for="v in vendors" :key="v.id" :value="v.id">{{ v.company_name }}</a-select-option>
            </a-select>
          </a-form-item></a-col>
          <a-col :span="8"><a-form-item label="적용연도" name="apply_year" :rules="[{required:true}]"><a-input-number v-model:value="form.apply_year" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="단가" name="price" :rules="[{required:true}]"><a-input-number v-model:value="form.price" style="width:100%" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="단위" name="unit"><a-input v-model:value="form.unit" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="적용시작" name="apply_from"><a-date-picker v-model:value="form.apply_from" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="12"><a-form-item label="적용종료" name="apply_to"><a-date-picker v-model:value="form.apply_to" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import CrudTable from '@/components/common/CrudTable.vue'
import { masterApi } from '@/api'

const items = ref([]), materials = ref([]), vendors = ref([])
const loading = ref(false), saving = ref(false), modalOpen = ref(false), editItem = ref(null)
const filterYear = ref(null), formRef = ref()
const form = reactive({ material_id: null, vendor_id: null, price: 0, unit: '', apply_year: new Date().getFullYear(), apply_from: null, apply_to: null })
const years = computed(() => { const y = new Date().getFullYear(); return [y+1, y, y-1, y-2] })
const filterOption = (input, opt) => opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())
const columns = [
  { title: '자재ID', dataIndex: 'material_id', width: 80 },
  { title: '단가', key: 'price', align: 'right', width: 120 },
  { title: '단위', dataIndex: 'unit', width: 60 },
  { title: '적용연도', dataIndex: 'apply_year', width: 90 },
  { title: '적용시작', dataIndex: 'apply_from', width: 110 },
  { title: '적용종료', dataIndex: 'apply_to', width: 110 },
  { title: '관리', key: 'action', width: 70, fixed: 'right' },
]
async function load() {
  loading.value = true
  try {
    const [up, mat, ven] = await Promise.all([
      masterApi.getUnitPrices({ apply_year: filterYear.value || undefined }),
      masterApi.getMaterials({}),
      masterApi.getCompanies({ company_type: 'vendor' }),
    ])
    items.value = up.data; materials.value = mat.data; vendors.value = ven.data
  } finally { loading.value = false }
}
function openModal(item) {
  editItem.value = item
  Object.assign(form, item || { material_id: null, vendor_id: null, price: 0, unit: '', apply_year: new Date().getFullYear(), apply_from: null, apply_to: null })
  modalOpen.value = true
}
async function handleSave() {
  try {
    await formRef.value.validate(); saving.value = true
    await masterApi.createUnitPrice(form); message.success('등록되었습니다.')
    modalOpen.value = false; load()
  } catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') }
  finally { saving.value = false }
}
onMounted(load)
</script>
