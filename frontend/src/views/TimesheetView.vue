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
          <template v-if="canApproveTimesheet">
            <a-divider type="vertical" />
            <a-select v-model:value="selectedEmpId" style="width:180px"
                      :options="empOptions" option-filter-prop="label" show-search
                      placeholder="직원 선택" @change="handleEmployeeChange" />
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
          <div class="grid-toolbar">
            <span class="grid-toolbar-title">{{ timesheetMode === 'week' ? '주간 입력' : monthLabel }}</span>
            <a-segmented v-model:value="timesheetMode" :options="timesheetModeOptions" @change="handleModeChange" />
          </div>
          <a-alert
            v-if="timesheetMode === 'week'"
            class="save-guide"
            type="info"
            show-icon
            message="입력한 내용은 자동 저장되지 않습니다. 하루 입력 후 저장 버튼을 눌러야 반영됩니다."
          />

          <a-spin :spinning="weekLoading || monthLoading">
            <div class="ts-grid-wrap">
              <table v-if="timesheetMode === 'week'" class="ts-grid">
                <thead>
                  <tr>
                    <th class="col-project">프로젝트</th>
                    <th class="col-spg">SPG</th>
                    <th class="col-labor">인건비 구분</th>
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
                    <!-- SPG -->
                    <td class="col-spg">
                      <a-select v-model:value="row.spg" style="width:100%" :disabled="isLocked">
                        <a-select-option v-for="spg in SPG_TYPES" :key="spg" :value="spg">{{ spg }}</a-select-option>
                      </a-select>
                    </td>
                    <!-- 인건비 구분 -->
                    <td class="col-labor">
                      <a-select v-model:value="row.labor_type" style="width:100%" :disabled="isLocked">
                        <a-select-option v-for="labor in LABOR_TYPES" :key="labor" :value="labor">{{ labor }}</a-select-option>
                      </a-select>
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
                    <td :colspan="13" class="empty-row">
                      <a-empty :image="Empty.PRESENTED_IMAGE_SIMPLE"
                               description='아래 "행 추가" 버튼으로 프로젝트별 시간을 입력하세요.' />
                    </td>
                  </tr>

                  <!-- 일별 합계 행 -->
                  <tr class="total-row">
                    <td colspan="4" class="total-label">일  계</td>
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

              <table v-else class="ts-grid month-grid">
                <thead>
                  <tr>
                    <th class="col-project">프로젝트</th>
                    <th class="col-spg">SPG</th>
                    <th class="col-labor">인건비 구분</th>
                    <th class="col-type">작업유형</th>
                    <th v-for="d in monthDays" :key="d.date"
                        :class="['col-month-day', d.isWeekend ? 'weekend' : '', d.date === todayStr ? 'today' : '']">
                      <div class="day-header">
                        <span class="day-name">{{ d.day }}</span>
                        <span class="day-date">{{ d.label }}</span>
                      </div>
                    </th>
                    <th class="col-total">합계</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in monthlyRows" :key="row.key">
                    <td class="col-project text-left">{{ row.project_name || '기타' }}</td>
                    <td class="col-spg">{{ row.spg }}</td>
                    <td class="col-labor">{{ row.labor_type }}</td>
                    <td class="col-type">{{ row.work_type }}</td>
                    <td v-for="d in monthDays" :key="d.date"
                        :class="['col-month-day', d.isWeekend ? 'weekend' : '']">
                      <span :class="row.days[d.day] > 0 ? 'num-active' : 'num-zero'">
                        {{ row.days[d.day] > 0 ? row.days[d.day] : '—' }}
                      </span>
                    </td>
                    <td class="col-total num-bold">{{ row.total }}</td>
                  </tr>
                  <tr v-if="monthlyRows.length === 0">
                    <td :colspan="monthDays.length + 5" class="empty-row">
                      <a-empty :image="Empty.PRESENTED_IMAGE_SIMPLE" description="해당 월의 타임시트 내용이 없습니다." />
                    </td>
                  </tr>
                  <tr class="total-row">
                    <td colspan="4" class="total-label">일  계</td>
                    <td v-for="d in monthDays" :key="d.date"
                        :class="['col-month-day', d.isWeekend ? 'weekend' : '']">
                      <span :class="monthlyDayTotal(d.day) > 0 ? 'num-active' : 'num-zero'">
                        {{ monthlyDayTotal(d.day) > 0 ? monthlyDayTotal(d.day) : '—' }}
                      </span>
                    </td>
                    <td class="col-total num-bold">{{ monthlyTotalHours }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- 액션 바 -->
            <div v-if="timesheetMode === 'week'" class="action-bar">
              <a-button v-if="!isLocked" @click="addRow" icon-placement="start">
                <template #icon><PlusOutlined /></template>행 추가
              </a-button>
              <a-input v-if="!isLocked" v-model:value="tsNotes"
                       placeholder="메모 (선택)" style="width:280px; margin-left:8px" />
              <div style="flex:1" />
              <a-space>
                <a-button v-if="!isLocked" :loading="saving" @click="handleSave">
                  저장
                </a-button>
              </a-space>
            </div>
          </a-spin>
        </a-card>
      </a-tab-pane>

      <!-- ═══════════════════════════════════════════════
           탭 2: 타임시트 종합
      ═══════════════════════════════════════════════ -->
      <a-tab-pane key="team" tab="타임시트 종합">

        <div class="week-nav" style="margin-bottom:12px">
          <a-button @click="prevSummaryMonth"><LeftOutlined /></a-button>
          <span class="week-period">{{ summaryMonthLabel }}</span>
          <a-button @click="nextSummaryMonth"><RightOutlined /></a-button>
          <a-button size="small" @click="goSummaryThisMonth" style="margin-left:8px">이번 달</a-button>
          <a-divider type="vertical" />
          <a-select v-model:value="summaryEmpId" style="width:180px"
                    :options="empOptions" option-filter-prop="label" show-search
                    placeholder="직원 선택" @change="loadSummary" />
        </div>

        <a-row :gutter="12" style="margin-bottom:14px">
          <a-col :span="8" v-for="s in summaryStats" :key="s.key">
            <a-card :bordered="false" class="kpi-mini" :class="s.cls">
              <div class="kpi-label">{{ s.label }}</div>
              <div class="kpi-value" :style="`color:${s.color}`">{{ s.value }}<span class="kpi-unit">{{ s.unit }}</span></div>
            </a-card>
          </a-col>
        </a-row>

        <a-card :bordered="false" class="table-card">
          <a-table :columns="summaryCols" :data-source="summaryRows" :loading="summaryLoading"
                   :pagination="{ pageSize: 20, showSizeChanger: true }" size="middle" row-key="key" :scroll="{ x: 760 }"
        :sticky="{ offsetHeader: 56 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'total_hours'">
                <span :class="record.total_hours > 0 ? 'num-active' : 'num-zero'">
                  {{ record.total_hours > 0 ? record.total_hours + 'h' : '—' }}
                </span>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-tab-pane>

    </a-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { message, Empty } from 'ant-design-vue'
import {
  LeftOutlined, RightOutlined, PlusOutlined, DeleteOutlined,
} from '@ant-design/icons-vue'
import { timesheetApi, masterApi, executionApi } from '@/api'
import { useAuthStore } from '@/store/auth'
import { canAccess } from '@/utils/permissions'

const auth = useAuthStore()
const canApproveTimesheet = computed(() => canAccess(auth.user?.role, '/timesheet', 'A'))
const SPG_TYPES = ['에너지', '빌딩', '시스템']
const LABOR_TYPES = ['판관', '원가']
const WORK_TYPES = ['설계', '시공', 'PM', '영업', '관리', '연차', '교육', '공통', '기타']
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
function formatLocalDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
function firstDayOfMonth(s) {
  const d = new Date(s)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`
}
function lastDayOfMonth(s) {
  const d = new Date(s)
  return formatLocalDate(new Date(d.getFullYear(), d.getMonth() + 1, 0))
}
function dayOfMonth(s) {
  return new Date(s).getDate()
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
const timesheetMode  = ref('week')
const monthLoading   = ref(false)
const monthlyRows    = ref([])
const timesheetModeOptions = [
  { label: '주간', value: 'week' },
  { label: '월간', value: 'month' },
]

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
const monthStart = computed(() => firstDayOfMonth(weekStart.value))
const monthEnd = computed(() => lastDayOfMonth(weekStart.value))
const monthLabel = computed(() => {
  const d = new Date(monthStart.value)
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월`
})
const monthDays = computed(() => {
  const start = new Date(monthStart.value)
  const last = new Date(monthEnd.value).getDate()
  return Array.from({ length: last }, (_, i) => {
    const date = formatLocalDate(new Date(start.getFullYear(), start.getMonth(), i + 1))
    const dow = new Date(date).getDay()
    return {
      date,
      day: i + 1,
      label: DAY_LABELS[(dow + 6) % 7],
      isWeekend: dow === 0 || dow === 6,
    }
  })
})
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

const isLocked = computed(() => false)

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
const monthlyDayTotal = (day) => monthlyRows.value.reduce((s, r) => s + (Number(r.days[day]) || 0), 0)
const monthlyTotalHours = computed(() => monthlyRows.value.reduce((s, r) => s + (Number(r.total) || 0), 0))
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
    project_id: null, project_name: '', spg: '에너지', labor_type: '원가', work_type: '기타',
    mon_hours: 0, tue_hours: 0, wed_hours: 0, thu_hours: 0,
    fri_hours: 0, sat_hours: 0, sun_hours: 0, notes: '',
  })
}
function removeRow(idx) { entries.value.splice(idx, 1) }

function prevWeek() { weekStart.value = addDays(weekStart.value, -7); refreshCurrentMode() }
function nextWeek() { weekStart.value = addDays(weekStart.value,  7); refreshCurrentMode() }
function goToday()  { weekStart.value = mondayOf(todayStr); refreshCurrentMode() }

function handleModeChange(value) {
  if (value === 'month') loadMonth()
}

function handleEmployeeChange() {
  loadWeek()
  if (timesheetMode.value === 'month') loadMonth()
}

function refreshCurrentMode() {
  loadWeek()
  if (timesheetMode.value === 'month') loadMonth()
}

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
    entries.value  = (d.entries || []).map(e => ({
      ...e,
      spg: e.spg || '에너지',
      labor_type: e.labor_type || '원가',
      work_type: e.work_type || '기타',
    }))
  } finally { weekLoading.value = false }
}

async function loadMonth() {
  monthLoading.value = true
  const empId = selectedEmpId.value || myEmpId.value
  if (!empId) { monthLoading.value = false; return }
  try {
    const list = (await timesheetApi.getList({ employee_id: empId })).data || []
    const targetWeeks = list.filter(ts => {
      const start = ts.week_start
      const end = ts.week_end || addDays(start, 6)
      return start <= monthEnd.value && end >= monthStart.value
    })
    const details = await Promise.all(targetWeeks.map(ts => timesheetApi.getWeek(empId, ts.week_start)))
    const rowMap = new Map()

    details.forEach(res => {
      const sheet = res.data
      ;(sheet.entries || []).forEach(entry => {
        const projectName = entry.project_name || '기타'
        const spg = entry.spg || '에너지'
        const laborType = entry.labor_type || '원가'
        const workType = entry.work_type || '기타'
        const key = `${entry.project_id || projectName}::${spg}::${laborType}::${workType}`
        if (!rowMap.has(key)) {
          rowMap.set(key, {
            key,
            project_name: projectName,
            spg,
            labor_type: laborType,
            work_type: workType,
            days: {},
            total: 0,
          })
        }
        const row = rowMap.get(key)
        DAY_KEYS.forEach((hourKey, index) => {
          const date = addDays(sheet.week_start, index)
          if (date < monthStart.value || date > monthEnd.value) return
          const hours = Number(entry[hourKey]) || 0
          if (!hours) return
          const day = dayOfMonth(date)
          row.days[day] = (row.days[day] || 0) + hours
          row.total += hours
        })
      })
    })

    monthlyRows.value = [...rowMap.values()]
      .filter(row => row.total > 0)
      .sort((a, b) => (a.project_name || '').localeCompare(b.project_name || ''))
  } finally {
    monthLoading.value = false
  }
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

// ══════════════════════════════════════════════════
// 탭 2: 타임시트 종합
// ══════════════════════════════════════════════════
const summaryMonthStart = ref(firstDayOfMonth(todayStr))
const summaryEmpId = ref(null)
const summaryRows = ref([])
const summaryLoading = ref(false)

const summaryMonthEnd = computed(() => lastDayOfMonth(summaryMonthStart.value))
const summaryMonthLabel = computed(() => {
  const d = new Date(summaryMonthStart.value)
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}`
})

const summaryStats = computed(() => {
  const all = summaryRows.value
  const total = all.reduce((sum, row) => sum + (Number(row.total_hours) || 0), 0)
  return [
    { key: 'total', label: '월 투입시간', value: total, unit: 'h', color: '#1677ff', cls: 'kpi-blue' },
    { key: 'project', label: '투입 프로젝트', value: new Set(all.map(row => row.project_name)).size, unit: '건', color: '#52c41a', cls: 'kpi-green' },
    { key: 'row', label: '통계 행', value: all.length, unit: '건', color: '#595959', cls: '' },
  ]
})

const summaryCols = [
  { title: '프로젝트', dataIndex: 'project_name', width: 280, align: 'center', ellipsis: true },
  { title: 'SPG', dataIndex: 'spg', width: 120, align: 'center' },
  { title: '인건비 구분', dataIndex: 'labor_type', width: 130, align: 'center' },
  { title: '월 투입시간 합계', key: 'total_hours', width: 160, align: 'right' },
]

function addMonths(s, n) {
  const d = new Date(s)
  return formatLocalDate(new Date(d.getFullYear(), d.getMonth() + n, 1))
}

function prevSummaryMonth() {
  summaryMonthStart.value = addMonths(summaryMonthStart.value, -1)
  loadSummary()
}

function nextSummaryMonth() {
  summaryMonthStart.value = addMonths(summaryMonthStart.value, 1)
  loadSummary()
}

function goSummaryThisMonth() {
  summaryMonthStart.value = firstDayOfMonth(todayStr)
  loadSummary()
}

async function loadSummary() {
  summaryLoading.value = true
  const empId = summaryEmpId.value || selectedEmpId.value || myEmpId.value
  if (!empId) {
    summaryRows.value = []
    summaryLoading.value = false
    return
  }
  try {
    const list = (await timesheetApi.getList({ employee_id: empId })).data || []
    const targetWeeks = list.filter(ts => {
      const start = ts.week_start
      const end = ts.week_end || addDays(start, 6)
      return start <= summaryMonthEnd.value && end >= summaryMonthStart.value
    })
    const details = await Promise.all(targetWeeks.map(ts => timesheetApi.getWeek(empId, ts.week_start)))
    const rowMap = new Map()

    details.forEach(res => {
      const sheet = res.data
      ;(sheet.entries || []).forEach(entry => {
        const projectName = entry.project_name || '기타'
        const spg = entry.spg || '에너지'
        const laborType = entry.labor_type || '원가'
        const key = `${entry.project_id || projectName}::${spg}::${laborType}`
        if (!rowMap.has(key)) {
          rowMap.set(key, {
            key,
            project_name: projectName,
            spg,
            labor_type: laborType,
            total_hours: 0,
          })
        }
        const row = rowMap.get(key)
        DAY_KEYS.forEach((hourKey, index) => {
          const date = addDays(sheet.week_start, index)
          if (date < summaryMonthStart.value || date > summaryMonthEnd.value) return
          row.total_hours += Number(entry[hourKey]) || 0
        })
      })
    })

    summaryRows.value = [...rowMap.values()]
      .filter(row => row.total_hours > 0)
      .sort((a, b) => (a.project_name || '').localeCompare(b.project_name || ''))
  } finally {
    summaryLoading.value = false
  }
}

async function loadBase() {
  const [emp, proj] = await Promise.all([masterApi.getEmployees({}), executionApi.getProjects()])
  employees.value = emp.data
  projects.value  = proj.data
  if (!canApproveTimesheet.value) selectedEmpId.value = myEmpId.value
  summaryEmpId.value = selectedEmpId.value || myEmpId.value || employees.value[0]?.id || null
}

onMounted(async () => {
  await loadBase()
  await Promise.all([loadWeek(), loadSummary()])
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
.grid-toolbar {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.grid-toolbar-title { font-size: 12px; color: #8c8c8c; }
.save-guide { margin-bottom: 12px; }
.ts-grid-wrap { overflow-x: auto; }

/* ── 타임시트 그리드 테이블 ── */
.ts-grid { width: 100%; border-collapse: collapse; font-size: 13px; }
.ts-grid th, .ts-grid td { border: 1px solid #f0f0f0; padding: 6px 4px; }
.ts-grid thead tr { background: #fafafa; }
.ts-grid th { text-align: center; font-weight: 600; color: #595959; white-space: nowrap; }

.col-project { min-width: 180px; max-width: 240px; }
.col-spg     { width: 96px; min-width: 96px; }
.col-labor   { width: 104px; min-width: 104px; }
.col-type    { width: 96px; min-width: 96px; }
.col-day     { width: 72px; text-align: center; }
.col-month-day { width: 54px; min-width: 54px; text-align: center; }
.col-total   { width: 62px; text-align: center; font-weight: 600; background: #fafafa; }
.col-del     { width: 36px; text-align: center; }
.month-grid { width: max-content; min-width: 100%; }
.text-left { text-align: left; }

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
