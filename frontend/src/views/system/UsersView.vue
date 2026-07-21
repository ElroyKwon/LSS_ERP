<template>
  <div class="page-wrap">

    <!-- 통계 카드 -->
    <a-row :gutter="16">
      <a-col :flex="1">
        <a-card :bordered="false" class="stat-card">
          <div class="stat-inner">
            <div class="stat-icon icon-gray"><TeamOutlined /></div>
            <div>
              <div class="stat-label">전체 사용자</div>
              <div class="stat-value">{{ userStats.total }}<span class="stat-unit">명</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :flex="1">
        <a-card :bordered="false" class="stat-card stat-red">
          <div class="stat-inner">
            <div class="stat-icon icon-red"><SafetyCertificateOutlined /></div>
            <div>
              <div class="stat-label">관리자</div>
              <div class="stat-value" style="color:#f5222d">{{ userStats.admin }}<span class="stat-unit">명</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :flex="1">
        <a-card :bordered="false" class="stat-card stat-blue">
          <div class="stat-inner">
            <div class="stat-icon icon-blue"><UserOutlined /></div>
            <div>
              <div class="stat-label">일반 사용자</div>
              <div class="stat-value" style="color:#1677ff">{{ userStats.user }}<span class="stat-unit">명</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :flex="1">
        <a-card :bordered="false" class="stat-card stat-orange">
          <div class="stat-inner">
            <div class="stat-icon icon-orange"><ClockCircleOutlined /></div>
            <div>
              <div class="stat-label">가입 신청 대기</div>
              <div class="stat-value" style="color:#fa8c16">{{ regStats.pending }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 메인 카드 (탭) -->
    <a-card :bordered="false" class="table-card">
      <template #extra>
        <a-button v-if="activeTab === 'users'" type="primary" @click="openModal(null)">
          <template #icon><PlusOutlined /></template>사용자 추가
        </a-button>
      </template>

      <a-tabs v-model:activeKey="activeTab" class="main-tabs">
        <!-- ── 사용자 목록 탭 ── -->
        <a-tab-pane key="users" tab="사용자 목록">
          <a-table
            :columns="userColumns"
            :data-source="users"
            :loading="userLoading"
            :pagination="{ defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'] }"
            row-key="id" size="middle" :scroll="{ x: 1290 }"
          
        :sticky="{ offsetHeader: 56 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'role'">
                <a-tag :color="getRoleColor(record.role)">{{ getRoleLabel(record.role) }}</a-tag>
              </template>
              <template v-if="column.key === 'labor_type'">
                <a-tag :color="record.labor_type === '판관' ? 'purple' : 'blue'">{{ record.labor_type || '원가' }}</a-tag>
              </template>
              <template v-if="column.key === 'is_active'">
                <a-tag :color="record.is_active ? 'green' : 'default'">
                  {{ record.is_active ? '활성' : '비활성' }}
                </a-tag>
              </template>
              <template v-if="column.key === 'action'">
                <a-space size="small">
                  <a @click="openModal(record)">수정</a>
                  <a-divider type="vertical" style="margin:0" />
                  <a-tooltip v-if="record.id === auth.user?.id"
                             title="현재 로그인 중인 계정은 삭제할 수 없습니다">
                    <span class="del-disabled">삭제</span>
                  </a-tooltip>
                  <a-popconfirm v-else
                    :title="`'${record.name}' 계정을 삭제하시겠습니까?`"
                    ok-text="삭제" ok-type="danger" cancel-text="취소"
                    @confirm="handleDeleteUser(record)"
                  >
                    <a class="del-link">삭제</a>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-tab-pane>

        <!-- ── 가입 신청 탭 ── -->
        <a-tab-pane key="registrations">
          <template #tab>
            가입 신청
            <a-badge v-if="regStats.pending > 0" :count="regStats.pending"
                     style="margin-left:6px" />
          </template>

          <a-table
            :columns="regColumns"
            :data-source="displayRegistrations"
            :loading="regLoading"
            :pagination="{ defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'] }"
            row-key="id" size="middle" :scroll="{ x: 1160 }"
          
        :sticky="{ offsetHeader: 56 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'created_at'">
                {{ record.created_at ? record.created_at.slice(0, 16).replace('T', ' ') : '-' }}
              </template>
              <template v-if="column.key === 'status'">
                <a-tag :color="regStatusColor[record.status]">{{ regStatusLabel[record.status] }}</a-tag>
              </template>
              <template v-if="column.key === 'action'">
                <a-space size="small">
                  <!-- 대기 중: 승인 + 거절 -->
                  <template v-if="record.status === 'pending'">
                    <a-button type="primary" size="small" @click="openApproveModal(record)">승인</a-button>
                    <a-button size="small" danger @click="openRejectModal(record)">거절</a-button>
                  </template>
                  <!-- 거절: 거절 사유 표시 -->
                  <template v-else>
                    <a-tooltip v-if="record.rejection_reason"
                               :title="`거절 사유: ${record.rejection_reason}`">
                      <span class="done-text">거절됨 ⓘ</span>
                    </a-tooltip>
                    <span v-else class="done-text">거절됨</span>
                  </template>
                  <!-- 모든 행: 삭제 버튼 -->
                  <a-divider type="vertical" style="margin:0" />
                  <a-popconfirm title="이 신청 항목을 삭제하시겠습니까?"
                                ok-text="삭제" ok-type="danger" cancel-text="취소"
                                @confirm="handleDeleteReg(record)">
                    <a class="del-link">삭제</a>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <!-- 사용자 등록/수정 모달 -->
    <a-modal :mask-closable="false" v-model:open="modalOpen" :title="editItem ? '사용자 수정' : '사용자 등록'"
             width="560px" @ok="handleSave" :confirm-loading="saving" ok-text="저장" cancel-text="취소">
      <a-form :model="form" layout="vertical" ref="formRef" style="margin-top:8px">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="아이디" name="username" :rules="[{ required: true, message: '아이디를 입력하세요.' }]">
              <a-input v-model:value="form.username" :disabled="!!editItem" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="이름" name="name" :rules="[{ required: true, message: '이름을 입력하세요.' }]">
              <a-input v-model:value="form.name" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="사원번호" name="employee_code">
              <a-input v-model:value="form.employee_code" placeholder="사원번호" />
            </a-form-item>
          </a-col>
          <a-col :span="12" v-if="!editItem">
            <a-form-item label="비밀번호" name="password" :rules="[{ required: true, message: '비밀번호를 입력하세요.' }]">
              <a-input-password v-model:value="form.password" autocomplete="new-password" />
            </a-form-item>
          </a-col>
          <a-col :span="12" v-if="editItem">
            <a-form-item label="새 비밀번호" name="new_password" extra="변경하지 않으려면 비워두세요.">
              <a-input-password v-model:value="form.new_password" placeholder="변경 시에만 입력" autocomplete="new-password" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="이메일" name="email">
              <a-input v-model:value="form.email" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="직위" name="position">
              <a-input v-model:value="form.position" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="부서" name="department_id">
              <a-select
                v-model:value="form.department_id"
                :options="departmentOptions"
                allow-clear
                show-search
                option-filter-prop="label"
                placeholder="부서 선택"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="권한" name="role">
              <a-select v-model:value="form.role" :options="roleOptions" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="원가구분" name="labor_type">
              <a-select v-model:value="form.labor_type" :options="laborTypeOptions" />
            </a-form-item>
          </a-col>
          <a-col :span="12" v-if="editItem">
            <a-form-item label="계정 상태" name="is_active">
              <a-select v-model:value="form.is_active">
                <a-select-option :value="true">활성</a-select-option>
                <a-select-option :value="false">비활성</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>

    <!-- 가입 승인 권한 지정 모달 -->
    <a-modal :mask-closable="false" v-model:open="approveOpen" title="가입 승인"
             width="440px" @ok="handleApprove" :confirm-loading="approving"
             ok-text="권한 부여 후 승인" cancel-text="취소">
      <div style="margin:16px 0 12px">
        <strong>{{ approveTarget?.name }}</strong> ({{ approveTarget?.username }}) 님에게 부여할 권한을 선택하세요.
      </div>
      <a-form layout="vertical">
        <a-form-item label="권한" required>
          <a-select v-model:value="approveRole" :options="roleOptions" placeholder="권한 선택" />
        </a-form-item>
        <a-form-item label="원가구분" required>
          <a-select v-model:value="approveLaborType" :options="laborTypeOptions" placeholder="원가구분 선택" />
        </a-form-item>
        <a-alert
          v-if="approveTarget?.department"
          class="approve-dept-alert"
          :type="approveDepartmentId ? 'success' : 'warning'"
          show-icon
          :message="approveDepartmentId
            ? `신청 부서 '${approveTarget.department}'와 일치하는 부서를 자동 선택했습니다.`
            : `신청 부서 '${approveTarget.department}'와 일치하는 부서가 없습니다. 확정 부서를 직접 선택하세요.`"
        />
        <a-form-item label="확정 부서" required>
          <a-select
            v-model:value="approveDepartmentId"
            :options="departmentOptions"
            show-search
            option-filter-prop="label"
            placeholder="확정 부서 선택"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 거절 사유 모달 -->
    <a-modal :mask-closable="false" v-model:open="rejectOpen" title="가입 신청 거절" width="440px"
             @ok="handleReject" :confirm-loading="rejecting"
             ok-text="거절 처리" :ok-button-props="{ danger: true }" cancel-text="취소">
      <div style="margin:16px 0 8px">
        <strong>{{ rejectTarget?.name }}</strong> ({{ rejectTarget?.username }}) 님의 가입 신청을 거절합니다.
      </div>
      <a-form layout="vertical">
        <a-form-item label="거절 사유 (선택)">
          <a-textarea v-model:value="rejectReason" :rows="3" placeholder="거절 사유를 입력하면 기록에 남습니다." />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import { masterApi, authApi } from '@/api'
import { useAuthStore } from '@/store/auth'
import { ROLE_OPTIONS, getRoleColor, getRoleLabel } from '@/utils/permissions'
import {
  TeamOutlined, UserOutlined, SafetyCertificateOutlined,
  ClockCircleOutlined, PlusOutlined,
} from '@ant-design/icons-vue'

const auth = useAuthStore()

// ── 탭 ──
const activeTab = ref('users')

// ── 사용자 ──
const users      = ref([])
const departments = ref([])
const userLoading = ref(false)
const saving     = ref(false)
const modalOpen  = ref(false)
const editItem   = ref(null)
const formRef    = ref()
const form = reactive({
  username: '', name: '', password: '', new_password: '',
  employee_code: '', email: '', role: 'sales_staff', labor_type: '원가', position: '', department_id: null, is_active: true,
})

const roleOptions = ROLE_OPTIONS.map(({ value, label }) => ({ value, label }))
const laborTypeOptions = [
  { value: '원가', label: '원가' },
  { value: '판관', label: '판관' },
]
const departmentOptions = computed(() =>
  departments.value.map(dept => ({
    value: dept.id,
    label: dept.path_name || dept.name,
  }))
)
const userStats = computed(() => ({
  total: users.value.length,
  admin: users.value.filter(u => u.role === 'system_admin' || u.role === 'admin').length,
  user:  users.value.filter(u => u.role !== 'system_admin' && u.role !== 'admin').length,
}))

const userColumns = [
  { title: '사원번호', dataIndex: 'employee_code', width: 110, align: 'center' },
  { title: '이름',     dataIndex: 'name',            width: 120, align: 'center' },
  { title: '아이디',   dataIndex: 'username',        width: 140, align: 'center' },
  { title: '부서',     dataIndex: 'department_name', width: 140, align: 'center', ellipsis: true },
  { title: '직위',     dataIndex: 'position',        width: 120, align: 'center' },
  { title: '이메일',   dataIndex: 'email',           width: 220, align: 'center', ellipsis: true },
  { title: '권한',     key: 'role',                  width: 120, align: 'center' },
  { title: '원가구분', key: 'labor_type',            width: 100, align: 'center' },
  { title: '상태',     key: 'is_active',             width: 90,  align: 'center' },
  { title: '관리',     key: 'action',                width: 130, align: 'center', fixed: 'right' },
]

async function loadUsers() {
  userLoading.value = true
  try { users.value = (await masterApi.getUsers()).data }
  finally { userLoading.value = false }
}

async function loadDepartments() {
  departments.value = (await masterApi.getDepartments({ include_inactive: false })).data
}

function openModal(item) {
  editItem.value = item
  Object.assign(form, item
    ? { ...item, password: '', new_password: '' }
    : { username: '', name: '', password: '', new_password: '', employee_code: '', email: '', role: 'sales_staff', labor_type: '원가', position: '', department_id: null, is_active: true }
  )
  modalOpen.value = true
}

async function handleSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    if (editItem.value) {
      await masterApi.updateUser(editItem.value.id, form)
      message.success('수정되었습니다.')
    } else {
      await masterApi.createUser(form)
      message.success('등록되었습니다.')
    }
    modalOpen.value = false
    loadUsers()
  } catch (e) {
    if (e?.errorFields) return
    message.error(e.response?.data?.detail || '오류가 발생했습니다.')
  } finally { saving.value = false }
}

async function handleDeleteUser(record) {
  try {
    await masterApi.deleteUser(record.id)
    message.success(`'${record.name}' 계정이 삭제되었습니다.`)
    loadUsers()
  } catch (e) {
    message.error(e.response?.data?.detail || '삭제 중 오류가 발생했습니다.')
  }
}

// ── 가입 신청 ──
const registrations = ref([])
const regLoading    = ref(false)
const regFilter     = ref('')
const rejectOpen    = ref(false)
const rejecting     = ref(false)
const rejectTarget  = ref(null)
const rejectReason  = ref('')
const approveOpen   = ref(false)
const approving     = ref(false)
const approveTarget = ref(null)
const approveRole   = ref('sales_staff')
const approveLaborType = ref('원가')
const approveDepartmentId = ref(null)

const regStatusColor = { pending: 'orange', rejected: 'red' }
const regStatusLabel = { pending: '대기', rejected: '거절' }

// 승인된 항목은 목록에서 숨김 (승인 → 사용자 목록으로 이동)
const displayRegistrations = computed(() =>
  registrations.value.filter(r => r.status !== 'approved')
    .sort((a, b) => {
      // 대기 먼저, 거절 아래로
      if (a.status === b.status) return new Date(b.created_at) - new Date(a.created_at)
      return a.status === 'pending' ? -1 : 1
    })
)

const regStats = computed(() => ({
  pending:  registrations.value.filter(r => r.status === 'pending').length,
  rejected: registrations.value.filter(r => r.status === 'rejected').length,
}))

const regColumns = [
  { title: '신청일시',  key: 'created_at',       width: 150, align: 'center' },
  { title: '아이디',   dataIndex: 'username',    width: 120, align: 'center' },
  { title: '이름',     dataIndex: 'name',        width: 90,  align: 'center' },
  { title: '사원번호', dataIndex: 'employee_code', width: 110, align: 'center' },
  { title: '부서',     dataIndex: 'department',  width: 120, align: 'center' },
  { title: '직위',     dataIndex: 'position',    width: 90,  align: 'center' },
  { title: '이메일',   dataIndex: 'email',       width: 180, align: 'center', ellipsis: true },
  { title: '상태',     key: 'status',            width: 80,  align: 'center' },
  { title: '처리',     key: 'action',            width: 190, align: 'center', fixed: 'right' },
]

async function loadRegistrations() {
  regLoading.value = true
  try {
    const res = await authApi.getRegistrations(regFilter.value || undefined)
    registrations.value = res.data
  } finally { regLoading.value = false }
}

function openApproveModal(record) {
  approveTarget.value = record
  approveRole.value = 'sales_staff'
  approveLaborType.value = '원가'
  const department = departments.value.find(dept => dept.name === record.department || dept.path_name === record.department)
  approveDepartmentId.value = department?.id || null
  approveOpen.value = true
}

async function handleApprove() {
  if (!approveRole.value) {
    message.warning('권한을 선택하세요.')
    return
  }
  if (!approveDepartmentId.value) {
    message.warning('확정 부서를 선택하세요.')
    return
  }
  approving.value = true
  try {
    await authApi.approveRegistration(approveTarget.value.id, {
      role: approveRole.value,
      labor_type: approveLaborType.value,
      department_id: approveDepartmentId.value,
    })
    await loadUsers()
    await loadRegistrations()
    message.success(`${approveTarget.value.name} 님이 승인되었습니다.`)
    approveOpen.value = false
  } catch (e) {
    message.error(e.response?.data?.detail || '승인 중 오류가 발생했습니다.')
  } finally { approving.value = false }
}

function openRejectModal(record) {
  rejectTarget.value = record
  rejectReason.value = ''
  rejectOpen.value = true
}

async function handleDeleteReg(record) {
  try {
    await authApi.deleteRegistration(record.id)
    message.success('신청 항목이 삭제되었습니다.')
    loadRegistrations()
  } catch (e) {
    message.error(e.response?.data?.detail || '삭제 중 오류가 발생했습니다.')
  }
}

async function handleReject() {
  rejecting.value = true
  try {
    await authApi.rejectRegistration(rejectTarget.value.id, { rejection_reason: rejectReason.value })
    message.success('거절 처리되었습니다.')
    rejectOpen.value = false
    loadRegistrations()
  } catch (e) {
    message.error(e.response?.data?.detail || '처리 중 오류가 발생했습니다.')
  } finally { rejecting.value = false }
}

// 탭 전환 시 항상 해당 데이터 재로드
watch(activeTab, (tab) => {
  if (tab === 'registrations') loadRegistrations()
  if (tab === 'users') loadUsers()
})

onMounted(() => {
  loadDepartments()
  loadUsers()
  loadRegistrations()
})
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }

.stat-card {
  border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07);
  border-left: 4px solid #e0e0e0;
}
.stat-red    { border-left-color: #f5222d; }
.stat-blue   { border-left-color: #1677ff; }
.stat-orange { border-left-color: #fa8c16; }

.stat-inner { display: flex; align-items: center; gap: 14px; }
.stat-icon  {
  width: 44px; height: 44px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; flex-shrink: 0;
}
.icon-gray   { background: #f0f2f5; color: #595959; }
.icon-red    { background: #fff1f0; color: #f5222d; }
.icon-blue   { background: #e6f4ff; color: #1677ff; }
.icon-orange { background: #fff7e6; color: #fa8c16; }

.stat-label { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value { font-size: 24px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit  { font-size: 13px; font-weight: 400; margin-left: 3px; color: #8c8c8c; }

.table-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }

/* 탭 상단 여백 제거 */
.main-tabs :deep(.ant-tabs-nav) { margin-bottom: 16px; }

.reg-filter { margin-bottom: 16px; }
.approve-dept-alert { margin-bottom: 12px; }

.del-link     { color: #e74c3c; }
.del-link:hover { color: #c0392b; }
.del-disabled { color: #bfbfbf; cursor: not-allowed; font-size: 13px; }
.done-text    { font-size: 12px; color: #8c8c8c; }

:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
