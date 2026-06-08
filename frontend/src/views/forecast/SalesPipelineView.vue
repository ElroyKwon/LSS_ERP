<template>
  <div>
    <a-row :gutter="[16,16]" style="margin-bottom:16px">
      <a-col :span="8"><a-card :bordered="false"><a-statistic title="총 예상수주" :value="totalExpected.toLocaleString()" suffix="원" /></a-card></a-col>
      <a-col :span="8"><a-card :bordered="false"><a-statistic title="가중 수주예상" :value="totalWeighted.toLocaleString()" suffix="원" value-style="color:#1a3a6b" /></a-card></a-col>
    </a-row>
    <CrudTable title="수주 파이프라인" :columns="columns" :data="items" :loading="loading" @create="openModal(null)">
      <template #filters>
        <a-select v-model:value="filterStatus" placeholder="상태" style="width:100px" allow-clear @change="load">
          <a-select-option value="active">진행중</a-select-option>
          <a-select-option value="won">수주</a-select-option>
          <a-select-option value="lost">미수주</a-select-option>
        </a-select>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="['expected_amount','weighted_amount'].includes(column.key)">{{ Number(record[column.key]).toLocaleString() }}</template>
        <template v-if="column.key === 'probability'"><a-progress :percent="record.probability" size="small" style="width:80px" />{{ record.probability }}%</template>
        <template v-if="column.key === 'status'"><a-tag :color="sColor[record.status]">{{ sLabel[record.status] }}</a-tag></template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a @click="openModal(record)">수정</a>
            <a-select :value="record.status" style="width:90px" size="small" @change="v => changeStatus(record.id, v)">
              <a-select-option value="active">진행</a-select-option>
              <a-select-option value="won">수주</a-select-option>
              <a-select-option value="lost">미수주</a-select-option>
            </a-select>
          </a-space>
        </template>
      </template>
    </CrudTable>
    <a-modal v-model:open="modalOpen" :title="editItem ? '수정' : '파이프라인 등록'" @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="24"><a-form-item label="프로젝트명" name="pipeline_name" :rules="[{required:true}]"><a-input v-model:value="form.pipeline_name" /></a-form-item></a-col>
          <a-col :span="24"><a-form-item label="발주처" name="client_id"><a-select v-model:value="form.client_id" show-search allow-clear :filter-option="fopt"><a-select-option v-for="c in clients" :key="c.id" :value="c.id">{{ c.company_name }}</a-select-option></a-select></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="예상금액" name="expected_amount"><a-input-number v-model:value="form.expected_amount" style="width:100%" @change="calcWeighted" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="수주확률(%)" name="probability"><a-input-number v-model:value="form.probability" style="width:100%" :min="0" :max="100" @change="calcWeighted" /></a-form-item></a-col>
          <a-col :span="8"><a-form-item label="예상수주일" name="expected_date"><a-date-picker v-model:value="form.expected_date" style="width:100%" value-format="YYYY-MM-DD" /></a-form-item></a-col>
          <a-col :span="24"><a-form-item label="비고"><a-textarea v-model:value="form.notes" :rows="2" /></a-form-item></a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import CrudTable from '@/components/common/CrudTable.vue'
import { forecastApi, masterApi } from '@/api'
import { showError } from '@/utils/request'

const items = ref([]), clients = ref([]), loading = ref(false), saving = ref(false)
const modalOpen = ref(false), editItem = ref(null), filterStatus = ref('active'), formRef = ref()
const form = reactive({ pipeline_name: '', client_id: null, expected_amount: 0, probability: 50, expected_date: null, notes: '' })
const sColor = { active: 'blue', won: 'green', lost: 'red' }
const sLabel = { active: '진행중', won: '수주', lost: '미수주' }
const fopt = (input, opt) => opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())
const totalExpected = computed(() => items.value.filter(i => i.status === 'active').reduce((s, i) => s + Number(i.expected_amount), 0))
const totalWeighted = computed(() => items.value.filter(i => i.status === 'active').reduce((s, i) => s + Number(i.weighted_amount), 0))
function calcWeighted() {
  form.weighted_amount = Math.round((form.expected_amount || 0) * (form.probability || 0) / 100)
}
const columns = [
  { title: '프로젝트명', dataIndex: 'pipeline_name', ellipsis: true },
  { title: '예상금액', key: 'expected_amount', align: 'right', width: 130 },
  { title: '수주확률', key: 'probability', align: 'center', width: 120 },
  { title: '가중금액', key: 'weighted_amount', align: 'right', width: 130 },
  { title: '예상수주일', dataIndex: 'expected_date', width: 110 },
  { title: '상태', key: 'status', width: 90 },
  { title: '관리', key: 'action', width: 140, fixed: 'right' },
]
async function load() {
  loading.value = true
  try {
    const [p, c] = await Promise.all([forecastApi.getSalesPipelines({ status: filterStatus.value || undefined }), masterApi.getCompanies({ company_type: 'client' })])
    items.value = p.data; clients.value = c.data
  } catch (e) {
    showError(e, '데이터 조회 실패')
  } finally { loading.value = false }
}
function openModal(item) {
  editItem.value = item
  Object.assign(form, item || { pipeline_name: '', client_id: null, expected_amount: 0, probability: 50, expected_date: null, notes: '' })
  modalOpen.value = true
}
async function handleSave() {
  try {
    await formRef.value.validate(); saving.value = true
    editItem.value ? await forecastApi.updateSalesPipeline(editItem.value.id, form) : await forecastApi.createSalesPipeline(form)
    message.success('저장'); modalOpen.value = false; load()
  } catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') } finally { saving.value = false }
}
async function changeStatus(id, status) {
  try { await forecastApi.updatePipelineStatus(id, status); load() }
  catch (e) { showError(e, '상태 변경 실패') }
}
onMounted(load)
</script>
