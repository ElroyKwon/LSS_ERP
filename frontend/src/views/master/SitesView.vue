<template>
  <div>
    <CrudTable title="현장 관리" :columns="columns" :data="sites" :loading="loading"
      @create="openModal(null)">
      <template #filters>
        <a-select v-model:value="filterStatus" placeholder="상태" style="width:100px" allow-clear @change="load">
          <a-select-option value="active">진행중</a-select-option>
          <a-select-option value="completed">완료</a-select-option>
          <a-select-option value="suspended">중단</a-select-option>
        </a-select>
        <a-input-search v-model:value="search" placeholder="현장명/코드 검색" style="width:200px" @search="load" allow-clear />
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor[record.status]">{{ statusLabel[record.status] }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a @click="openModal(record)">수정</a>
          </a-space>
        </template>
      </template>
    </CrudTable>

    <a-modal v-model:open="modalOpen" :title="editItem ? '현장 수정' : '현장 등록'" width="640px"
      @ok="handleSave" :confirm-loading="saving">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="현장코드" name="site_code" :rules="[{required:true}]">
              <a-input v-model:value="form.site_code" :disabled="!!editItem" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="Job No." name="job_no">
              <a-input v-model:value="form.job_no" />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="현장명" name="site_name" :rules="[{required:true}]">
              <a-input v-model:value="form.site_name" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="발주처" name="client_id">
              <a-select v-model:value="form.client_id" show-search :filter-option="filterOption" allow-clear>
                <a-select-option v-for="c in clients" :key="c.id" :value="c.id">{{ c.company_name }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="계약유형" name="contract_type">
              <a-select v-model:value="form.contract_type" allow-clear>
                <a-select-option value="lump_sum">총액</a-select-option>
                <a-select-option value="unit_price">단가</a-select-option>
                <a-select-option value="actual_cost">실비</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="착공일" name="start_date">
              <a-date-picker v-model:value="form.start_date" style="width:100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="준공예정일" name="end_date">
              <a-date-picker v-model:value="form.end_date" style="width:100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="상태" name="status">
              <a-select v-model:value="form.status">
                <a-select-option value="active">진행중</a-select-option>
                <a-select-option value="completed">완료</a-select-option>
                <a-select-option value="suspended">중단</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="위치" name="location">
              <a-input v-model:value="form.location" />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="비고" name="notes">
              <a-textarea v-model:value="form.notes" :rows="2" />
            </a-form-item>
          </a-col>
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

const sites = ref([])
const clients = ref([])
const loading = ref(false)
const saving = ref(false)
const modalOpen = ref(false)
const editItem = ref(null)
const filterStatus = ref(null)
const search = ref('')
const formRef = ref()
const form = reactive({
  site_code: '', job_no: '', site_name: '', client_id: null,
  contract_type: null, start_date: null, end_date: null,
  status: 'active', location: '', notes: '',
})

const statusColor = { active: 'green', completed: 'blue', suspended: 'red' }
const statusLabel = { active: '진행중', completed: '완료', suspended: '중단' }

const columns = [
  { title: '현장코드', dataIndex: 'site_code', key: 'site_code', width: 120 },
  { title: 'Job No.', dataIndex: 'job_no', key: 'job_no', width: 120 },
  { title: '현장명', dataIndex: 'site_name', key: 'site_name', ellipsis: true },
  { title: '착공일', dataIndex: 'start_date', key: 'start_date', width: 110 },
  { title: '준공예정', dataIndex: 'end_date', key: 'end_date', width: 110 },
  { title: '상태', key: 'status', width: 90 },
  { title: '관리', key: 'action', width: 80, fixed: 'right' },
]

const filterOption = (input, option) =>
  option.children?.toLowerCase().includes(input.toLowerCase())

async function load() {
  loading.value = true
  try {
    const [s, c] = await Promise.all([
      masterApi.getSites({ status: filterStatus.value || undefined, search: search.value || undefined }),
      masterApi.getCompanies({ company_type: 'client' }),
    ])
    sites.value = s.data
    clients.value = c.data
  } finally { loading.value = false }
}

function openModal(item) {
  editItem.value = item
  if (item) {
    Object.assign(form, { ...item })
  } else {
    Object.assign(form, {
      site_code: '', job_no: '', site_name: '', client_id: null,
      contract_type: null, start_date: null, end_date: null,
      status: 'active', location: '', notes: '',
    })
  }
  modalOpen.value = true
}

async function handleSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    if (editItem.value) {
      await masterApi.updateSite(editItem.value.id, form)
      message.success('수정되었습니다.')
    } else {
      await masterApi.createSite(form)
      message.success('등록되었습니다.')
    }
    modalOpen.value = false
    load()
  } catch (e) {
    if (e?.errorFields) return
    message.error(e.response?.data?.detail || '오류가 발생했습니다.')
  } finally { saving.value = false }
}

onMounted(load)
</script>
