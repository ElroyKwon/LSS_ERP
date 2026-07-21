<template>
  <div class="page-wrap">
    <!-- 상단 통계 카드 -->
    <a-row :gutter="16">
      <a-col :flex="1">
        <a-card :bordered="false" class="stat-card">
          <div class="stat-inner">
            <div class="stat-icon icon-gray"><TeamOutlined /></div>
            <div>
              <div class="stat-label">전체 신청</div>
              <div class="stat-value">{{ stats.total }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :flex="1">
        <a-card :bordered="false" class="stat-card stat-orange">
          <div class="stat-inner">
            <div class="stat-icon icon-orange"><ClockCircleOutlined /></div>
            <div>
              <div class="stat-label">승인 대기</div>
              <div class="stat-value" style="color:#fa8c16">{{ stats.pending }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :flex="1">
        <a-card :bordered="false" class="stat-card stat-green">
          <div class="stat-inner">
            <div class="stat-icon icon-green"><CheckCircleOutlined /></div>
            <div>
              <div class="stat-label">승인 완료</div>
              <div class="stat-value" style="color:#52c41a">{{ stats.approved }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :flex="1">
        <a-card :bordered="false" class="stat-card stat-red">
          <div class="stat-inner">
            <div class="stat-icon icon-red"><CloseCircleOutlined /></div>
            <div>
              <div class="stat-label">거절</div>
              <div class="stat-value" style="color:#f5222d">{{ stats.rejected }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 테이블 카드 -->
    <a-card :bordered="false" class="table-card">
      <template #title><span class="card-title">가입 신청 관리</span></template>
      <template #extra>
        <a-radio-group v-model:value="filterStatus" button-style="solid" size="small" @change="load">
          <a-radio-button value="">전체</a-radio-button>
          <a-radio-button value="pending">
            대기
            <a-badge v-if="stats.pending > 0" :count="stats.pending" :offset="[4,-2]"
                     style="--ant-badge-color:#fa8c16" />
          </a-radio-button>
          <a-radio-button value="approved">승인</a-radio-button>
          <a-radio-button value="rejected">거절</a-radio-button>
        </a-radio-group>
      </template>

      <a-table :columns="columns" :data-source="items" :loading="loading"
               :pagination="{ defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'] }"
               row-key="id" size="middle" :scroll="{ x: 1000 }"
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor[record.status]">{{ statusLabel[record.status] }}</a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <template v-if="record.status === 'pending'">
              <a-space size="small">
                <a-button type="primary" size="small" @click="openApproveModal(record)">승인</a-button>
                <a-button size="small" danger @click="openRejectModal(record)">거절</a-button>
              </a-space>
            </template>
            <template v-else>
              <a-tooltip :title="record.rejection_reason || ''" v-if="record.status === 'rejected'">
                <span class="reviewed-text">거절됨</span>
              </a-tooltip>
              <span v-else class="reviewed-text">처리 완료</span>
            </template>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 거절 사유 모달 -->
    <a-modal :mask-closable="false" v-model:open="rejectOpen" title="가입 신청 거절" width="440px"
             @ok="handleReject" :confirm-loading="rejecting" ok-text="거절 처리" :ok-button-props="{ danger: true }" cancel-text="취소">
      <div style="margin: 16px 0 8px">
        <strong>{{ rejectTarget?.name }}</strong> ({{ rejectTarget?.username }}) 님의 가입 신청을 거절합니다.
      </div>
      <a-form layout="vertical">
        <a-form-item label="거절 사유 (선택)">
          <a-textarea v-model:value="rejectReason" :rows="4"
                      placeholder="거절 사유를 입력하면 기록에 남습니다." />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 가입 승인 권한 지정 모달 -->
    <a-modal :mask-closable="false" v-model:open="approveOpen" title="가입 승인" width="440px"
             @ok="handleApprove" :confirm-loading="approving"
             ok-text="권한 부여 후 승인" cancel-text="취소">
      <div style="margin: 16px 0 12px">
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { authApi, masterApi } from '@/api'
import { ROLE_OPTIONS } from '@/utils/permissions'
import {
  TeamOutlined, ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined,
} from '@ant-design/icons-vue'

const items = ref([])
const loading = ref(false)
const filterStatus = ref('')
const rejectOpen = ref(false)
const rejecting = ref(false)
const rejectTarget = ref(null)
const rejectReason = ref('')
const approveOpen = ref(false)
const approving = ref(false)
const approveTarget = ref(null)
const approveRole = ref('sales_staff')
const approveLaborType = ref('원가')
const approveDepartmentId = ref(null)
const departments = ref([])
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

const statusColor = { pending: 'orange', approved: 'green', rejected: 'red' }
const statusLabel = { pending: '대기', approved: '승인', rejected: '거절' }

const stats = computed(() => ({
  total:    items.value.length,
  pending:  items.value.filter(r => r.status === 'pending').length,
  approved: items.value.filter(r => r.status === 'approved').length,
  rejected: items.value.filter(r => r.status === 'rejected').length,
}))

const columns = [
  { title: '신청일시',  dataIndex: 'created_at',  width: 160, align: 'center',
    customRender: ({ text }) => text ? text.slice(0, 16).replace('T', ' ') : '-' },
  { title: '아이디',   dataIndex: 'username',    width: 120, align: 'center' },
  { title: '이름',     dataIndex: 'name',        width: 90,  align: 'center' },
  { title: '부서',     dataIndex: 'department',  width: 110, align: 'center' },
  { title: '직위',     dataIndex: 'position',    width: 90,  align: 'center' },
  { title: '이메일',   dataIndex: 'email',       ellipsis: true, align: 'center' },
  { title: '전화번호', dataIndex: 'phone',       width: 130, align: 'center' },
  { title: '상태',     key: 'status',            width: 80,  align: 'center' },
  { title: '처리',     key: 'action',            width: 150, align: 'center', fixed: 'right' },
]

async function load() {
  loading.value = true
  try {
    const res = await authApi.getRegistrations(filterStatus.value || undefined)
    items.value = res.data
  } finally { loading.value = false }
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
    message.success(`${approveTarget.value.name} 님의 가입이 승인되었습니다.`)
    approveOpen.value = false
    load()
  } catch (e) {
    message.error(e.response?.data?.detail || '승인 중 오류가 발생했습니다.')
  } finally { approving.value = false }
}

function openRejectModal(record) {
  rejectTarget.value = record
  rejectReason.value = ''
  rejectOpen.value = true
}

async function handleReject() {
  rejecting.value = true
  try {
    await authApi.rejectRegistration(rejectTarget.value.id, { rejection_reason: rejectReason.value })
    message.success('거절 처리되었습니다.')
    rejectOpen.value = false
    load()
  } catch (e) {
    message.error(e.response?.data?.detail || '처리 중 오류가 발생했습니다.')
  } finally { rejecting.value = false }
}

async function loadDepartments() {
  departments.value = (await masterApi.getDepartments({ include_inactive: false })).data
}

onMounted(() => {
  loadDepartments()
  load()
})
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }

.stat-card {
  border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07);
  border-left: 4px solid #e0e0e0;
}
.stat-orange { border-left-color: #fa8c16; }
.stat-green  { border-left-color: #52c41a; }
.stat-red    { border-left-color: #f5222d; }

.stat-inner { display: flex; align-items: center; gap: 14px; }
.stat-icon  {
  width: 44px; height: 44px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; flex-shrink: 0;
}
.icon-gray   { background: #f0f2f5; color: #595959; }
.icon-orange { background: #fff7e6; color: #fa8c16; }
.icon-green  { background: #f6ffed; color: #52c41a; }
.icon-red    { background: #fff1f0; color: #f5222d; }

.stat-label { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value { font-size: 24px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit  { font-size: 13px; font-weight: 400; margin-left: 3px; color: #8c8c8c; }

.table-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size: 15px; font-weight: 600; color: #1a2535; }

.reviewed-text { font-size: 12px; color: #8c8c8c; }
.approve-dept-alert { margin-bottom: 12px; }

:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
