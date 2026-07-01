<template>
  <div class="page-wrap">
    <a-row :gutter="16">
      <a-col :span="6">
        <a-card :bordered="false" class="stat-card stat-blue">
          <div class="stat-inner">
            <div class="stat-icon icon-blue"><TeamOutlined /></div>
            <div>
              <div class="stat-label">전체 직원</div>
              <div class="stat-value">{{ items.length }}<span class="stat-unit">명</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card :bordered="false" class="stat-card stat-green">
          <div class="stat-inner">
            <div class="stat-icon icon-green"><CheckCircleOutlined /></div>
            <div>
              <div class="stat-label">활성</div>
              <div class="stat-value">{{ activeCount }}<span class="stat-unit">명</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card :bordered="false" class="stat-card stat-red">
          <div class="stat-inner">
            <div class="stat-icon icon-red"><StopOutlined /></div>
            <div>
              <div class="stat-label">비활성</div>
              <div class="stat-value">{{ inactiveCount }}<span class="stat-unit">명</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-card :bordered="false" class="table-card">
      <template #title>
        <span class="card-title">사원관리</span>
      </template>
      <template #extra>
        <a-space>
          <a-input-search
            v-model:value="search"
            placeholder="사번/이름/부서 검색"
            allow-clear
            style="width: 220px"
            @search="load"
          />
          <a-select v-model:value="statusFilter" style="width: 120px" @change="load">
            <a-select-option value="all">전체</a-select-option>
            <a-select-option value="active">활성</a-select-option>
            <a-select-option value="inactive">비활성</a-select-option>
          </a-select>
          <a-button type="primary" @click="openDrawer(null)">
            <template #icon><PlusOutlined /></template>
            직원 등록
          </a-button>
        </a-space>
      </template>

      <a-table
        :columns="columns"
        :data-source="filteredItems"
        :loading="loading"
        :pagination="{ pageSize: 20, showSizeChanger: true }"
        row-key="id"
        size="middle"
        :scroll="{ x: 2180 }"
      
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'is_active'">
            <a-tag :color="record.is_active ? 'green' : 'red'">
              {{ record.is_active ? '활성' : '비활성' }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'settings'">
            <a-space size="small">
              <a-button size="small" @click="openDrawer(record)">수정</a-button>
              <a-switch
                size="small"
                :checked="record.is_active"
                checked-children="활성"
                un-checked-children="비활성"
                @change="(checked) => toggleActive(record, checked)"
              />
              <a-popconfirm
                title="직원 정보를 삭제하시겠습니까?"
                ok-text="삭제"
                cancel-text="취소"
                @confirm="deleteEmployee(record)"
              >
                <a-button danger size="small">삭제</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-modal
      v-model:open="drawerOpen"
      :title="editItem ? '직원 수정' : '직원 등록'"
      width="560"
      :body-style="{ paddingBottom: '72px' }"
    
      centered>
      <a-form ref="formRef" :model="form" layout="vertical">
        <a-divider orientation="left">기본 정보</a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="입사일" name="hire_date">
              <a-date-picker v-model:value="form.hire_date" value-format="YYYY-MM-DD" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="사번" name="emp_code" :rules="[{ required: true, message: '사번을 입력하세요.' }]">
              <a-input v-model:value="form.emp_code" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="이름" name="name" :rules="[{ required: true, message: '이름을 입력하세요.' }]">
              <a-input v-model:value="form.name" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="전화번호" name="phone">
              <a-input v-model:value="form.phone" />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="메일주소" name="email">
              <a-input v-model:value="form.email" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left">조직 정보</a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="부서" name="department_name">
              <a-select
                v-model:value="form.department_name"
                allow-clear
                show-search
                placeholder="부서 선택"
                :options="departmentOptions"
                option-filter-prop="label"
                option-label-prop="shortLabel"
                @change="onDepartmentChange"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="담당업무" name="task">
              <a-input v-model:value="form.task" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="직급" name="position">
              <a-input v-model:value="form.position" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="직책" name="job_title">
              <a-input v-model:value="form.job_title" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left">개인/기타 정보</a-divider>
        <a-row :gutter="16">
          <a-col :span="24">
            <a-form-item label="주소(집)" name="home_address">
              <a-input v-model:value="form.home_address" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="생년월일" name="birth_date">
              <a-date-picker v-model:value="form.birth_date" value-format="YYYY-MM-DD" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="결혼기념일" name="wedding_anniversary">
              <a-date-picker v-model:value="form.wedding_anniversary" value-format="YYYY-MM-DD" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="법인카드 번호" name="corporate_card_no">
              <a-input v-model:value="form.corporate_card_no" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="퇴사일" name="resign_date">
              <a-date-picker v-model:value="form.resign_date" value-format="YYYY-MM-DD" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="활성 여부" name="is_active">
              <a-switch v-model:checked="form.is_active" checked-children="활성" un-checked-children="비활성" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>

      <template #footer>
        <div class="drawer-footer">
          <a-button @click="drawerOpen = false">취소</a-button>
          <a-button type="primary" :loading="saving" @click="saveEmployee">저장</a-button>
        </div>
      </template>
    </a-modal>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  CheckCircleOutlined,
  PlusOutlined,
  StopOutlined,
  TeamOutlined,
} from '@ant-design/icons-vue'
import { masterApi } from '@/api'
import { flattenDepartmentTree } from '@/utils/departments'

const items = ref([])
const departments = ref([])
const loading = ref(false)
const saving = ref(false)
const drawerOpen = ref(false)
const editItem = ref(null)
const formRef = ref()
const search = ref('')
const statusFilter = ref('all')

const emptyForm = {
  hire_date: null,
  emp_code: '',
  name: '',
  phone: '',
  email: '',
  department_id: null,
  department_name: '',
  task: '',
  position: '',
  job_title: '',
  home_address: '',
  birth_date: null,
  wedding_anniversary: null,
  corporate_card_no: '',
  resign_date: null,
  is_active: true,
  emp_type: 'regular',
}

const form = reactive({ ...emptyForm })

const columns = [
  { title: '입사일', dataIndex: 'hire_date', width: 110, align: 'center' },
  { title: '사번', dataIndex: 'emp_code', width: 120, align: 'center' },
  { title: '이름', dataIndex: 'name', width: 110, align: 'center', ellipsis: true },
  { title: '전화번호', dataIndex: 'phone', width: 140, align: 'center' },
  { title: '메일주소', dataIndex: 'email', width: 190, align: 'center', ellipsis: true },
  { title: '부서', dataIndex: 'department_name', width: 130, align: 'center', ellipsis: true },
  { title: '담당업무', dataIndex: 'task', width: 160, align: 'center', ellipsis: true },
  { title: '직급', dataIndex: 'position', width: 110, align: 'center' },
  { title: '직책', dataIndex: 'job_title', width: 110, align: 'center' },
  { title: '주소(집)', dataIndex: 'home_address', width: 220, align: 'center', ellipsis: true },
  { title: '생년월일', dataIndex: 'birth_date', width: 110, align: 'center' },
  { title: '결혼기념일', dataIndex: 'wedding_anniversary', width: 120, align: 'center' },
  { title: '법인카드 번호', dataIndex: 'corporate_card_no', width: 170, align: 'center' },
  { title: '퇴사일', dataIndex: 'resign_date', width: 110, align: 'center' },
  { title: '상태', key: 'is_active', dataIndex: 'is_active', width: 90, align: 'center' },
  { title: '설정', key: 'settings', width: 210, align: 'center', fixed: 'right' },
]

const activeCount = computed(() => items.value.filter(item => item.is_active).length)
const inactiveCount = computed(() => items.value.filter(item => !item.is_active).length)
const filteredItems = computed(() => {
  if (statusFilter.value === 'active') return items.value.filter(item => item.is_active)
  if (statusFilter.value === 'inactive') return items.value.filter(item => !item.is_active)
  return items.value
})
const orgYear = new Date().getFullYear()
const flatDepartments = computed(() => flattenDepartmentTree(departments.value))
const departmentOptions = computed(() =>
  flatDepartments.value
    .filter(dept => dept.is_active !== false)
    .map(dept => ({
      value: dept.name,
      label: dept.path,
      shortLabel: dept.name,
      id: dept.id,
    }))
)

function normalizeEmployee(item) {
  return {
    ...emptyForm,
    ...item,
    department_id: item.department_id || item.department?.id || null,
    department_name: item.department_name || item.department?.name || '',
    is_active: item.is_active !== false,
  }
}

async function load() {
  loading.value = true
  try {
    const [res, deptRes] = await Promise.all([
      masterApi.getEmployees({
        search: search.value || undefined,
        include_inactive: true,
      }),
      masterApi.getDepartments({ org_year: orgYear, include_inactive: false, tree: true }),
    ])
    items.value = res.data.map(normalizeEmployee)
    departments.value = deptRes.data || []
  } finally {
    loading.value = false
  }
}

function onDepartmentChange(value) {
  const selected = departmentOptions.value.find(option => option.value === value)
  form.department_id = selected?.id || null
}

function openDrawer(item) {
  editItem.value = item
  Object.assign(form, item ? normalizeEmployee(item) : { ...emptyForm })
  drawerOpen.value = true
}

async function saveEmployee() {
  try {
    await formRef.value.validate()
    saving.value = true
    const payload = { ...form }
    if (editItem.value) {
      await masterApi.updateEmployee(editItem.value.id, payload)
      message.success('직원 정보가 수정되었습니다.')
    } else {
      await masterApi.createEmployee(payload)
      message.success('직원이 등록되었습니다.')
    }
    drawerOpen.value = false
    await load()
  } catch (e) {
    if (e?.errorFields) return
    message.error(e.response?.data?.detail || '저장 중 오류가 발생했습니다.')
  } finally {
    saving.value = false
  }
}

async function toggleActive(record, checked) {
  try {
    await masterApi.setEmployeeActive(record.id, checked)
    message.success(checked ? '활성화되었습니다.' : '비활성화되었습니다.')
    await load()
  } catch (e) {
    message.error(e.response?.data?.detail || '상태 변경 중 오류가 발생했습니다.')
  }
}

async function deleteEmployee(record) {
  try {
    await masterApi.deleteEmployee(record.id)
    message.success('직원 정보가 삭제되었습니다.')
    await load()
  } catch (e) {
    message.error(e.response?.data?.detail || '삭제 중 오류가 발생했습니다.')
  }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.stat-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue { border-left-color: #1677ff; }
.stat-green { border-left-color: #52c41a; }
.stat-red { border-left-color: #f5222d; }
.stat-inner { display: flex; align-items: center; gap: 14px; }
.stat-icon { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.icon-blue { background: #e6f4ff; color: #1677ff; }
.icon-green { background: #f6ffed; color: #52c41a; }
.icon-red { background: #fff1f0; color: #f5222d; }
.stat-label { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value { font-size: 24px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit { font-size: 13px; font-weight: 400; margin-left: 3px; color: #8c8c8c; }
.table-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size: 15px; font-weight: 600; color: #1a2535; }
.drawer-footer { display: flex; justify-content: flex-end; gap: 8px; }

:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
:deep(.ant-table-cell) { white-space: nowrap; }
</style>
