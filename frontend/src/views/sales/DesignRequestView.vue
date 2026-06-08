<template>
  <div>
    <CrudTable
      title="설계 의뢰"
      :columns="columns"
      :data="items"
      :loading="loading"
      :scroll-x="1100"
      @create="openModal(null)"
    >
      <template #filters>
        <a-input-search
          v-model:value="search"
          placeholder="프로젝트명 검색"
          style="width: 200px"
          allow-clear
          @search="load"
        />
        <a-select
          v-model:value="filterStatus"
          placeholder="상태"
          style="width: 110px"
          allow-clear
          @change="load"
        >
          <a-select-option v-for="(label, val) in statusLabel" :key="val" :value="val">{{ label }}</a-select-option>
        </a-select>
      </template>

      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor[record.status]">{{ statusLabel[record.status] }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a @click="openModal(record)">수정</a>
            <a-divider type="vertical" />
            <a-popconfirm title="삭제하시겠습니까?" @confirm="handleDelete(record.id)">
              <a style="color: #e74c3c">삭제</a>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </CrudTable>

    <!-- 등록/수정 모달 -->
    <a-modal
      v-model:open="modalOpen"
      :title="editItem ? '설계의뢰 수정' : '설계의뢰 신규 등록'"
      width="720px"
      @ok="handleSave"
      :confirm-loading="saving"
      ok-text="저장"
      cancel-text="취소"
    >
      <a-form :model="form" layout="vertical" ref="formRef" style="margin-top: 8px">
        <a-row :gutter="16">
          <a-col :span="24">
            <a-form-item label="프로젝트명" name="project_name" :rules="[{ required: true, message: '프로젝트명을 입력하세요.' }]">
              <a-input v-model:value="form.project_name" placeholder="프로젝트명 입력" />
            </a-form-item>
          </a-col>

          <a-col :span="12">
            <a-form-item label="요청 부서" name="department">
              <a-input v-model:value="form.department" placeholder="부서명 입력" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="요청자 성명" name="requester_name">
              <a-input v-model:value="form.requester_name" placeholder="성명 입력" />
            </a-form-item>
          </a-col>

          <a-col :span="12">
            <a-form-item label="발주처" name="order_company_id">
              <a-select v-model:value="form.order_company_id" show-search allow-clear
                        placeholder="발주처 선택" :filter-option="filterOpt">
                <a-select-option v-for="c in companies" :key="c.id" :value="c.id">{{ c.company_name }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="건설사" name="construction_company_id">
              <a-select v-model:value="form.construction_company_id" show-search allow-clear
                        placeholder="건설사 선택" :filter-option="filterOpt">
                <a-select-option v-for="c in companies" :key="c.id" :value="c.id">{{ c.company_name }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>

          <a-col :span="12">
            <a-form-item label="거래처" name="partner_company_id">
              <a-select v-model:value="form.partner_company_id" show-search allow-clear
                        placeholder="거래처 선택" :filter-option="filterOpt">
                <a-select-option v-for="c in companies" :key="c.id" :value="c.id">{{ c.company_name }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="상태" name="status">
              <a-select v-model:value="form.status">
                <a-select-option v-for="(label, val) in statusLabel" :key="val" :value="val">{{ label }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>

          <a-col :span="12">
            <a-form-item label="의뢰일" name="request_date">
              <a-date-picker v-model:value="form.request_date" style="width: 100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="완료(요구)일" name="due_date">
              <a-date-picker v-model:value="form.due_date" style="width: 100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>

          <a-col :span="24">
            <a-form-item label="비고" name="notes">
              <a-textarea v-model:value="form.notes" :rows="3" placeholder="비고 입력" />
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
import { salesApi, masterApi } from '@/api'

const items = ref([])
const companies = ref([])
const loading = ref(false)
const saving = ref(false)
const modalOpen = ref(false)
const editItem = ref(null)
const search = ref('')
const filterStatus = ref(undefined)
const formRef = ref()

const statusLabel = {
  received: '접수',
  in_progress: '진행중',
  completed: '완료',
  cancelled: '취소',
}
const statusColor = {
  received: 'orange',
  in_progress: 'blue',
  completed: 'green',
  cancelled: 'red',
}

const emptyForm = {
  project_name: '',
  department: '',
  requester_name: '',
  order_company_id: null,
  construction_company_id: null,
  partner_company_id: null,
  request_date: null,
  due_date: null,
  status: 'received',
  notes: '',
}
const form = reactive({ ...emptyForm })

const columns = [
  { title: '프로젝트명', dataIndex: 'project_name', width: 200, align: 'center', ellipsis: true },
  { title: '요청 부서', dataIndex: 'department', width: 120, align: 'center' },
  { title: '요청자 성명', dataIndex: 'requester_name', width: 110, align: 'center' },
  { title: '발주처', dataIndex: 'order_company_name', width: 150, ellipsis: true, align: 'center' },
  { title: '건설사', dataIndex: 'construction_company_name', width: 150, ellipsis: true, align: 'center' },
  { title: '거래처', dataIndex: 'partner_company_name', width: 150, ellipsis: true, align: 'center' },
  { title: '의뢰일', dataIndex: 'request_date', width: 110, align: 'center' },
  { title: '완료(요구)일', dataIndex: 'due_date', width: 115, align: 'center' },
  { title: '상태', key: 'status', width: 90, align: 'center' },
  { title: '관리', key: 'action', width: 90, align: 'center', fixed: 'right' },
]

const filterOpt = (input, opt) =>
  opt.children?.[0]?.toLowerCase().includes(input.toLowerCase())

async function load() {
  loading.value = true
  try {
    const [dr, co] = await Promise.all([
      salesApi.getDesignRequests({
        search: search.value || undefined,
        status: filterStatus.value || undefined,
      }),
      masterApi.getCompanies(),
    ])
    items.value = dr.data
    companies.value = co.data
  } finally {
    loading.value = false
  }
}

function openModal(item) {
  editItem.value = item
  if (item) {
    Object.assign(form, {
      project_name: item.project_name || '',
      department: item.department || '',
      requester_name: item.requester_name || '',
      order_company_id: item.order_company_id || null,
      construction_company_id: item.construction_company_id || null,
      partner_company_id: item.partner_company_id || null,
      request_date: item.request_date || null,
      due_date: item.due_date || null,
      status: item.status || 'received',
      notes: item.notes || '',
    })
  } else {
    Object.assign(form, emptyForm)
  }
  modalOpen.value = true
}

async function handleSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    if (editItem.value) {
      await salesApi.updateDesignRequest(editItem.value.id, form)
      message.success('수정되었습니다.')
    } else {
      await salesApi.createDesignRequest(form)
      message.success('등록되었습니다.')
    }
    modalOpen.value = false
    load()
  } catch (e) {
    if (e?.errorFields) return
    message.error(e.response?.data?.detail || '저장 중 오류가 발생했습니다.')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id) {
  try {
    await salesApi.deleteDesignRequest(id)
    message.success('삭제되었습니다.')
    load()
  } catch (e) {
    message.error(e.response?.data?.detail || '삭제 중 오류가 발생했습니다.')
  }
}

onMounted(load)
</script>

<style scoped>
:deep(.ant-table-thead > tr > th) {
  text-align: center !important;
}
</style>
