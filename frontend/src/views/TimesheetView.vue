<template>
  <div class="page-wrap">

    <!-- ── 탭 헤더 ── -->
    <a-tabs v-model:activeKey="activeTab" class="main-tabs">

      <!-- ═══════════════════════════════════════════════
           탭 1: 내 타임시트 (주간 입력)
      ═══════════════════════════════════════════════ -->
      <a-tab-pane key="my" tab="내 타임시트">

        <!-- 주간 네비게이터 -->
        <div class="week-nav">
          <a-button @click="prevWeek"><LeftOutlined /></a-button>
          <div class="week-label">
            <span class="week-period">{{ weekLabel }}</span>
            <a-tag :color="statusColor[tsStatus]" style="margin-left:10px">{{ tsStatus }}</a-tag>
          </div>
          <a-button @click="nextWeek"><RightOutlined /></a-button>
          <a-button size="small" @click="goToday" style="margin-left:8px">이번 주</a-button>

          <!-- 직원 선택 (관리자) -->
          <template v-if="auth.isAdmin || auth.user?.role === 'manager'">
            <a-divider type="vertical" />
            <a-select v-model:value="selectedEmpId" style="width:180px"
                      :options="empOptions" option-filter-prop="label" show-search
                      placeholder="직원 선택" @change="loadWeek" />
          </template>
        </div>

        <!-- 주간 합계 KPI -->
        <a-row :gutter="12" style="margin-bottom:12px">
          <a-col :span="6" v-for="s in weekKpis" :key="s.key">
            <a-card :bordered="false" class="kpi-mini" :class="s.cls">
              <div class="kpi-label">{{ s.label }}</div>
              <div class="kpi-value" :style="`color:${s.color}`">{{ s.value }}<span class="kpi-unit">h</span></div>
            </a-card>
          </a-col>
        </a-row>

        <!-- 주간 그리드 -->
        <a-card :bordered="false" class="grid-card">
          <a-spin :spinning="weekLoading">
            <div class="ts-grid-wrap">
              <table class="ts-grid">
                <thead>
                  <tr>
                    <th class="col-project">프로젝트</th>
                    <th class="col-type">작업유형</th>
                    <th v-for="(d, i) in weekDays" :key="d.date"
                        :class="['col-day', d.isWeekend ? 'weekend' : '', d.date === todayStr ? 'today' : '']">
                      <div class="day-header">
                        <span class="day-name">{{ d.label }}</span>
                        <span class="day-date">{{ d.short }}</span>
                      </div>
                    </th>
                    <th class="col-total">주계</th>
                    <th class="col-del"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, idx) in entries" :key="idx">
                    <!-- 프로젝트 -->
                    <td class="col-project">
                      <a-auto-complete
                        v-model:value="row.project_name"
                        :options="projectSuggestions"
                        placeholder="프로젝트명"
                        :disabled="isLocked"
                        style="width:100%"
                        @select="(v, opt) => onProjectSelect(idx, v, opt)"
                      />
                    </td>
                    <!-- 작업유형 -->
                    <td class="col-type">
                      <a-select v-model:value="row.work_type" style="width:100%" :disabled="isLocked">
                        <a-select-option v-for="t in WORK_TYPES" :key="t" :value="t">{{ t }}</a-select-option>
                      </a-select>
                    </td>
                    <!-- 요일별 시간 입력 -->
                    <td v-for="(d, di) in weekDays" :key="d.date"
                        :class="['col-day', d.isWeekend ? 'weekend' : '']">
                      <a-input-number
                        v-model:value="row[DAY_KEYS[di]]"
                        :min="0" :max="24" :step="0.5"
                        :disabled="isLocked"
                        class="hour-input"
                        :class="row[DAY_KEYS[di]] > 0 ? 'has-hours' : ''"
                        controls-position="right"
                        @change="onHoursChange"
                      />
                    </td>
                    <!-- 행 합계 -->
                    <td class="col-total">
                      <span :class="rowTotal(row) > 0 ? 'num-active' : 'num-zero'">
                        {{ rowTotal(row) }}
                      </span>
                    </td>
                    <!-- 삭제 -->
                    <td class="col-del">
                      <a-button v-if="!isLocked" type="text" size="small" danger
                                @click="removeRow(idx)">
                        <template #icon><DeleteOutlined /></template>
                      </a-button>
                    </td>
                  </tr>

                  <!-- 빈 상태 -->
                  <tr v-if="entries.length === 0">
                    <td :colspan="11" class="empty-row">
                      <a-empty :image="Empty.PRESENTED_IMAGE_SIMPLE"
                               description='아래 "행 추가" 버튼으로 프로젝트별 시간을 입력하세요.' />
                    </td>
                  </tr>

                  <!-- 일별 합계 행 -->
                  <tr class="total-row">
                    <td colspan="2" class="total-label">일  계</td>
                    <td v-for="(d, di) in weekDays" :key="d.date"
                        :class="['col-day', d.isWeekend ? 'weekend' : '']">
                      <span :class="dayTotal(di) > 8 ? 'overtime' : dayTotal(di) > 0 ? 'num-active' : 'num-zero'">
                        {{ dayTotal(di) > 0 ? dayTotal(di) : '—' }}
                      </span>
                    </td>
                    <td class="col-total num-bold">{{ weekTotalHours }}</td>
                    <td></td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- 액션 바 -->
            <div class="action-bar">
              <a-button v-if="!isLocked" @click="addRow" icon-placement="start">
                <template #icon><PlusOutlined /></template>행 추가
              </a-button>
              <a-input v-if="!isLocked" v-model:value="tsNotes"
                       placeholder="메모 (선택)" style="width:280px; margin-left:8px" />
              <div style="flex:1" />
              <a-space>
                <a-button v-if="!isLocked" :loading="saving" @click="handleSave">
                  임시 저장
                </a-button>
                <a-popconfirm v-if="tsStatus === '작성중' && tsId"
                              title="타임시트를 제출하시겠습니까? 제출 후에는 수정할 수 없습니다."
                              ok-text="제출" cancel-text="취소" @confirm="handleSubmit">
                  <a-button type="primary" :loading="saving">
                    <template #icon><SendOutlined /></template>제출
                  </a-button>
                </a-popconfirm>
                <a-tag v-if="tsStatus === '제출'" color="orange" style="padding:6px 12px">검토 대기 중</a-tag>
                <a-tag v-if="tsStatus === '승인'" color="green" style="padding:6px 12px">승인됨 ✓</a-tag>
                <div v-if="tsStatus === '반려'" class="reject-bar">
                  <a-tag color="red">반려됨</a-tag>
                  <span v-if="rejectReason" style="margin-left:6px;font-size:12px;color:#f5222d">{{ rejectReason }}</span>
                  <a-button size="small" @click="tsStatus='작성중'" style="margin-left:8px">재작성</a-button>
                </div>
              </a-space>
            </div>
          </a-spin>
        </a-card>
      </a-tab-pane>

      <!-- ═══════════════════════════════════════════════
           탭 2: 팀 현황 / 승인 관리
      ═══════════════════════════════════════════════ -->
      <a-tab-pane key="team" tab="팀 현황 · 승인">

        <!-- 팀 현황 주간 선택 -->
        <div class="week-nav" style="margin-bottom:12px">
          <a-button @click="teamPrevWeek"><LeftOutlined /></a-button>
          <span class="week-period">{{ teamWeekLabel }}</span>
          <a-button @click="teamNextWeek"><RightOutlined /></a-button>
          <a-button size="small" @click="goTeamToday" style="margin-left:8px">이번 주</a-button>
        </div>

        <!-- 팀 제출 현황 카드 -->
        <a-row :gutter="12" style="margin-bottom:14px">
          <a-col :flex="1" v-for="s in teamStats" :key="s.key">
            <a-card :bordered="false" class="kpi-mini" :class="s.cls">
              <div class="kpi-label">{{ s.label }}</div>
              <div class="kpi-value" :style="`color:${s.color}`">{{ s.value }}<span class="kpi-unit">명</span></div>
            </a-card>
          </a-col>
        </a-row>

        <!-- 팀원 타임시트 목록 -->
        <a-card :bordered="false" class="table-card">
          <a-table :columns="teamCols" :data-source="teamStatus" :loading="teamLoading"
                   :pagination="false" size="middle" row-key="employee_id">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'status'">
                <a-tag :color="statusColor[record.status]">{{ record.status }}</a-tag>
              </template>
              <template v-if="column.key === 'total_hours'">
                <span :class="record.total_hours > 0 ? 'num-active' : 'num-zero'">
                  {{ record.total_hours > 0 ? record.total_hours + 'h' : '—' }}
                </span>
              </template>
              <template v-if="column.key === 'action'">
                <a-space size="small" v-if="record.timesheet_id">
                  <a @click="viewDetail(record)">상세</a>
                  <template v-if="record.status === '제출'">
                    <a-divider type="vertical" style="margin:0" />
                    <a-popconfirm title="승인하시겠습니까?" ok-text="승인" cancel-text="취소"
                                  @confirm="handleApprove(record.timesheet_id)">
                      <a-button type="primary" size="small">승인</a-button>
                    </a-popconfirm>
                    <a-button size="small" danger @click="openRejectModal(record)">반려</a-button>
                  </template>
                </a-space>
                <span v-else class="num-zero">미작성</span>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-tab-pane>

    </a-tabs>

    <!-- 반려 모달 -->
    <a-modal v-model:open="rejectOpen" title="타임시트 반려"
             width="420px" @ok="handleReject" :confirm-loading="rejecting"
             ok-text="반려 처리" :ok-button-props="{ danger: true }" cancel-text="취소">
      <a-form layout="vertical" style="margin-top:8px">
        <a-form-item label="반려 사유">
          <a-textarea v-model:value="rejectReason" :rows="3"
                      placeholder="반려 사유를 입력하세요." />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { message, Empty } from 'ant-design-vue'
import {
  LeftOutlined, RightOutlined, PlusOutlined, DeleteOutlined, SendOutlined,
} from '@ant-design/icons-vue'
import { timesheetApi, masterApi, executionApi } from '@/api'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const WORK_TYPES = ['설계', '시공', '감리', 'PM', '영업', '관리', '기타']
const DAY_KEYS   = ['mon_hours', 'tue_hours', 'wed_hours', 'thu_hours', 'fri_hours', 'sat_hours', 'sun_hours']
const DAY_LABELS = ['월', '화', '수', '목', '금', '토', '일']

const statusColor = { 작성중: 'default', 제출: 'orange', 승인: 'green', 반려: 'red', 미작성: 'default' }

// ── 날짜 유틸 ──
const todayStr = new Date().toISOString().slice(0, 10)
function mondayOf(d) {
  const dt = new Date(d)
  dt.setDate(dt.getDate() - dt.getDay() + (dt.getDay() === 0 ? -6 : 1))
  return dt.toISOString().slice(0, 10)
}
function addDays(s, n) {
  const d = new Date(s); d.setDate(d.getDate() + n)
  return d.toISOString().slice(0, 10)
}
function fmtDate(s, fmt = 'MM/DD') {
  const d = new Date(s)
  if (fmt === 'MM/DD') return `${d.getMonth()+1}/${String(d.getDate()).padStart(2,'0')}`
  return `${d.getFullYear()}.${d.getMonth()+1}.${d.getDate()}`
}

// ══════════════════════════════════════════════════
// 탭 1: 내 타임시트
// ══════════════════════════════════════════════════
const activeTab      = ref('my')
const weekStart      = ref(mondayOf(todayStr))
const selectedEmpId  = ref(null)
const employees      = ref([])
const projects       = ref([])
const weekLoading    = ref(false)
const saving         = ref(false)
const tsId           = ref(null)
const tsStatus       = ref('작성중')
const tsNotes        = ref('')
const rejectReason   = ref('')
const entries        = ref([])

const empOptions = computed(() =>
  employees.value.map(e => ({ value: e.id, label: `${e.name} (${e.department || ''})` }))
)
const myEmpId = computed(() => {
  const me = employees.value.find(e => e.name === auth.user?.name)
  return me?.id || null
})

const weekEnd = computed(() => addDays(weekStart.value, 6))
const weekDays = computed(() =>
  DAY_KEYS.map((k, i) => {
    const date = addDays(weekStart.value, i)
    return { date, label: DAY_LABELS[i], short: fmtDate(date), isWeekend: i >= 5, key: k }
  })
)
const weekLabel = computed(() =>
  `${fmtDate(weekStart.value, 'full')} ~ ${fmtDate(weekEnd.value, 'full')}`
)
function fmtDate2(s) {
  const d = new Date(s)
  return `${d.getFullYear()}.${d.getMonth()+1}.${d.getDate()}`
}
const weekLabelFull = computed(() => `${fmtDate2(weekStart.value)} ~ ${fmtDate2(weekEnd.value)}`)

// 실제 weekLabel 사용
const weekLabelDisplay = computed(() => {
  const s = new Date(weekStart.value), e = new Date(weekEnd.value)
  const fmt = d => `${d.getFullYear()}.${d.getMonth()+1}.${String(d.getDate()).padStart(2,'0')}`
  return `${fmt(s)}  ~  ${fmt(e)}`
})

const isLocked = computed(() => ['제출', '승인'].includes(tsStatus.value))

// 프로젝트 자동완성
const projectSuggestions = computed(() =>
  projects.value.map(p => ({ value: p.project_name, id: p.id, project_no: p.project_no }))
)
function onProjectSelect(idx, value, option) {
  entries.value[idx].project_id = option.id || null
}

// 시간 계산
const rowTotal = (row) => DAY_KEYS.reduce((s, k) => s + (Number(row[k]) || 0), 0)
const dayTotal  = (di)  => entries.value.reduce((s, r) => s + (Number(r[DAY_KEYS[di]]) || 0), 0)
const weekTotalHours = computed(() => entries.value.reduce((s, r) => s + rowTotal(r), 0))
function onHoursChange() {} // computed 자동 반응

// KPI 카드
const weekKpis = computed(() => {
  const total = weekTotalHours.value
  const mon = entries.value.filter(r => rowTotal(r) > 0).length
  const ot  = DAY_KEYS.reduce((s, _, di) => s + Math.max(0, dayTotal(di) - 8), 0)
  return [
    { key: 'total', label: '주간 총 시간',   value: total, color: '#1677ff', cls: 'kpi-blue' },
    { key: 'proj',  label: '투입 프로젝트', value: mon,   color: '#52c41a', cls: 'kpi-green' },
    { key: 'ot',    label: '초과 근무',      value: ot.toFixed(1), color: ot > 0 ? '#fa8c16' : '#bfbfbf', cls: 'kpi-orange' },
    { key: 'avg',   label: '일평균 (평일)',  value: (total / 5).toFixed(1), color: '#595959', cls: '' },
  ]
})

function addRow() {
  entries.value.push({
    project_id: null, project_name: '', work_type: '기타',
    mon_hours: 0, tue_hours: 0, wed_hours: 0, thu_hours: 0,
    fri_hours: 0, sat_hours: 0, sun_hours: 0, notes: '',
  })
}
function removeRow(idx) { entries.value.splice(idx, 1) }

function prevWeek() { weekStart.value = addDays(weekStart.value, -7); loadWeek() }
function nextWeek() { weekStart.value = addDays(weekStart.value,  7); loadWeek() }
function goToday()  { weekStart.value = mondayOf(todayStr); loadWeek() }

async function loadWeek() {
  weekLoading.value = true
  const empId = selectedEmpId.value || myEmpId.value
  if (!empId) { weekLoading.value = false; return }
  try {
    const res = await timesheetApi.getWeek(empId, weekStart.value)
    const d   = res.data
    tsId.value     = d.id
    tsStatus.value = d.status || '작성중'
    tsNotes.value  = d.notes  || ''
    rejectReason.value = d.reject_reason || ''
    entries.value  = (d.entries || []).map(e => ({ ...e }))
  } finally { weekLoading.value = false }
}

async function handleSave() {
  const empId = selectedEmpId.value || myEmpId.value
  if (!empId) { message.warning('직원을 선택해주세요.'); return }
  saving.value = true
  try {
    const res = await timesheetApi.save({
      employee_id: empId, week_start: weekStart.value,
      entries: entries.value, notes: tsNotes.value,
    })
    tsId.value = res.data.id
    tsStatus.value = res.data.status
    message.success('저장되었습니다.')
  } catch (e) { message.error(e.response?.data?.detail || '저장 오류') }
  finally { saving.value = false }
}

async function handleSubmit() {
  if (!tsId.value) { await handleSave() }
  if (!tsId.value) return
  saving.value = true
  try {
    await timesheetApi.submit(tsId.value)
    tsStatus.value = '제출'
    message.success('타임시트가 제출되었습니다.')
  } catch (e) { message.error(e.response?.data?.detail || '제출 오류') }
  finally { saving.value = false }
}

// ══════════════════════════════════════════════════
// 탭 2: 팀 현황
// ══════════════════════════════════════════════════
const teamWeekStart = ref(mondayOf(todayStr))
const teamStatus    = ref([])
const teamLoading   = ref(false)
const rejectOpen    = ref(false)
const rejecting     = ref(false)
const rejectTarget  = ref(null)
const rejectInput   = ref('')

const teamWeekEnd = computed(() => addDays(teamWeekStart.value, 6))
const teamWeekLabel = computed(() => {
  const s = new Date(teamWeekStart.value), e = new Date(teamWeekEnd.value)
  const fmt = d => `${d.getFullYear()}.${d.getMonth()+1}.${String(d.getDate()).padStart(2,'0')}`
  return `${fmt(s)}  ~  ${fmt(e)}`
})

function teamPrevWeek() { teamWeekStart.value = addDays(teamWeekStart.value, -7); loadTeam() }
function teamNextWeek() { teamWeekStart.value = addDays(teamWeekStart.value,  7); loadTeam() }
function goTeamToday()  { teamWeekStart.value = mondayOf(todayStr); loadTeam() }

const teamStats = computed(() => {
  const all  = teamStatus.value
  return [
    { key: 'total',  label: '전체',   value: all.length,                                    color: '#1a2535', cls: '' },
    { key: 'sub',    label: '제출',   value: all.filter(r => r.status === '제출').length,   color: '#fa8c16', cls: 'kpi-orange' },
    { key: 'appr',   label: '승인',   value: all.filter(r => r.status === '승인').length,   color: '#52c41a', cls: 'kpi-green' },
    { key: 'none',   label: '미작성', value: all.filter(r => r.status === '미작성').length, color: '#f5222d', cls: 'kpi-red' },
  ]
})

const teamCols = [
  { title: '직원',    dataIndex: 'employee_name', width: 110, align: 'center' },
  { title: '부서',    dataIndex: 'department',    width: 120, align: 'center' },
  { title: '직위',    dataIndex: 'position',      width: 90,  align: 'center' },
  { title: '총 시간', key: 'total_hours',          width: 90,  align: 'center' },
  { title: '상태',    key: 'status',               width: 90,  align: 'center' },
  { title: '처리',    key: 'action',               width: 180, align: 'center', fixed: 'right' },
]

function viewDetail(record) {
  weekStart.value     = mondayOf(teamWeekStart.value)
  selectedEmpId.value = record.employee_id
  activeTab.value     = 'my'
  loadWeek()
}

async function handleApprove(id) {
  try {
    await timesheetApi.approve(id)
    message.success('승인되었습니다.')
    loadTeam()
  } catch (e) { message.error(e.response?.data?.detail || '승인 오류') }
}

function openRejectModal(record) {
  rejectTarget.value = record
  rejectInput.value  = ''
  rejectOpen.value   = true
}

async function handleReject() {
  rejecting.value = true
  try {
    await timesheetApi.reject(rejectTarget.value.timesheet_id, { reason: rejectInput.value })
    message.success('반려 처리되었습니다.')
    rejectOpen.value = false
    loadTeam()
  } catch (e) { message.error(e.response?.data?.detail || '반려 오류') }
  finally { rejecting.value = false }
}

async function loadTeam() {
  teamLoading.value = true
  try { teamStatus.value = (await timesheetApi.teamStatus(teamWeekStart.value)).data }
  finally { teamLoading.value = false }
}

async function loadBase() {
  const [emp, proj] = await Promise.all([masterApi.getEmployees({}), executionApi.getProjects()])
  employees.value = emp.data
  projects.value  = proj.data
  if (!auth.isAdmin) selectedEmpId.value = myEmpId.value
}

onMounted(async () => {
  await loadBase()
  await Promise.all([loadWeek(), loadTeam()])
})
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 0; }
:deep(.main-tabs .ant-tabs-nav) { margin-bottom: 14px; }

/* ── 주간 네비 ── */
.week-nav {
  display: flex; align-items: center; gap: 10px;
  background: #fff; border-radius: 8px; padding: 12px 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07); margin-bottom: 12px;
}
.week-label { display: flex; align-items: center; }
.week-period { font-size: 14px; font-weight: 700; color: #1a2535; min-width: 220px; text-align: center; }

/* ── KPI 미니 카드 ── */
.kpi-mini  { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 3px solid #e0e0e0; padding: 2px 0; }
.kpi-blue  { border-left-color: #1677ff; }
.kpi-green { border-left-color: #52c41a; }
.kpi-orange { border-left-color: #fa8c16; }
.kpi-red   { border-left-color: #f5222d; }
.kpi-label { font-size: 11px; color: #8c8c8c; }
.kpi-value { font-size: 22px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.kpi-unit  { font-size: 12px; font-weight: 400; margin-left: 2px; color: #8c8c8c; }

/* ── 그리드 카드 ── */
.grid-card  { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.ts-grid-wrap { overflow-x: auto; }

/* ── 타임시트 그리드 테이블 ── */
.ts-grid { width: 100%; border-collapse: collapse; font-size: 13px; }
.ts-grid th, .ts-grid td { border: 1px solid #f0f0f0; padding: 6px 4px; }
.ts-grid thead tr { background: #fafafa; }
.ts-grid th { text-align: center; font-weight: 600; color: #595959; white-space: nowrap; }

.col-project { min-width: 180px; max-width: 240px; }
.col-type    { width: 90px; }
.col-day     { width: 72px; text-align: center; }
.col-total   { width: 62px; text-align: center; font-weight: 600; background: #fafafa; }
.col-del     { width: 36px; text-align: center; }

.weekend { background: #fafafa; }
.today   { background: #e6f4ff; }

.day-header  { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.day-name    { font-size: 12px; font-weight: 700; }
.day-date    { font-size: 10px; color: #8c8c8c; }

:deep(.hour-input) { width: 60px !important; }
:deep(.hour-input.has-hours .ant-input-number-input) { color: #1677ff; font-weight: 600; }
:deep(.ant-input-number-input) { text-align: center !important; padding: 0 4px; }

.total-row td { background: #f5f5f5; font-weight: 600; text-align: center; }
.total-label  { text-align: center; color: #595959; font-size: 12px; }
.empty-row td { padding: 30px; }

.num-active  { color: #1677ff; font-weight: 600; }
.num-zero    { color: #bfbfbf; }
.num-bold    { font-weight: 700; }
.overtime    { color: #f5222d; font-weight: 700; }

/* ── 액션 바 ── */
.action-bar {
  display: flex; align-items: center; gap: 8px;
  margin-top: 12px; padding-top: 12px; border-top: 1px solid #f0f0f0;
}
.reject-bar { display: flex; align-items: center; }

/* ── 테이블 카드 ── */
.table-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
