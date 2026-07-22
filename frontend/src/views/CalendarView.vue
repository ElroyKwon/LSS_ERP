<template>
  <div class="page-wrap">
    <a-tabs v-model:activeKey="activeTab" class="main-tabs">
      
      <a-tab-pane key="company-calendar" tab="전사 일정(외근·출장)">
        <div class="calendar-nav">
          <div style="display: flex; align-items: center; gap: 10px;">
            <a-button @click="prevCompanyMonth"><LeftOutlined /></a-button>
            <span class="calendar-period-label">
              {{ companyYearMonth }}
            </span>
            <a-button @click="nextCompanyMonth"><RightOutlined /></a-button>
            <a-button size="small" @click="goCompanyToday" style="margin-left: 8px;">이번 달</a-button>
          </div>
          <a-button type="primary" size="small" @click="openCompanyModal">
            <template #icon><PlusOutlined /></template>일정 등록
          </a-button>
        </div>

        <a-card :bordered="false" class="grid-card" style="padding: 10px; min-height: 600px;">
          <a-calendar v-model:value="companyCalendarValue" :fullscreen="true" @panelChange="handleCompanyPanelChange">
            <template #dateFullCellRender="{ current }">
              <div :class="['ant-picker-cell-inner', 'ant-picker-calendar-date', getCompanyCellClass(current)]" 
                   style="cursor: pointer;" 
                   @click="openCompanyDetailModal(current)">
                <div class="ant-picker-calendar-date-value">
                  {{ current.date() }}
                </div>
                <div class="ant-picker-calendar-date-content">
                  <ul class="events calendar-event-list">
                    <li v-for="item in getCompanyVisibleListData(current)" :key="item.id" 
                        :style="getEventStyle(item, current)"
                        class="calendar-event-chip">
                      {{ shouldShowEventText(item, current) ? item.content : '\u00A0' }}
                    </li>
                    <li v-if="getCompanyHiddenCount(current) > 0" class="calendar-more-link" @click.stop="openCompanyDetailModal(current)">
                      {{ '+' + getCompanyHiddenCount(current) + ' \ub354\ubcf4\uae30' }}
                    </li>
                  </ul>
                </div>
              </div>
            </template>
          </a-calendar>
        </a-card>	

        <a-modal :mask-closable="false" v-model:open="isCompanyDetailModalOpen" :title="`${selectedCompanyDate} 일정 상세`" :footer="null">
          <div style="margin-top: 16px;">
            <a-list item-layout="horizontal" :data-source="companyDetailList">
              <template #renderItem="{ item }">
                <a-list-item style="padding: 12px 4px;">
                  <div style="display: flex; flex-direction: column; gap: 4px; width: 100%;">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                      <a-badge :color="item.type" :text="item.raw_content" style="font-size: 14px; font-weight: 500;" />
                      <div v-if="canManageSchedule(item)" style="display: flex; gap: 4px; margin-left: 12px;">
                        <a-button type="link" size="small" @click.stop="openCompanyEditModal(item)">수정</a-button>
                        <a-button type="link" danger size="small" @click.stop="deleteCompanySchedule(item)">삭제</a-button>
                      </div>
                    </div>
                    <div style="font-size: 12px; color: #8c8c8c; padding-left: 14px;">
                      <span v-if="item.is_all_day">종일</span>
                      <span v-else>{{ formatTimeRange(item.start_time, item.end_time) }}</span>
                      <span style="margin-left: 8px; font-weight: 500; color: #595959;">등록자: {{ item.user_name }}</span>
                    </div>
                  </div>
                </a-list-item>
              </template>
              <template #empty>
                <a-empty description="등록된 일정이 없습니다." />
              </template>
            </a-list>
          </div>
        </a-modal>

        <a-modal v-model:open="isCompanyModalOpen" :title="editingCompanySchedule ? '\uc804\uc0ac \uc77c\uc815(\uc678\uadfc\u00b7\ucd9c\uc7a5) \uc218\uc815' : '\uc804\uc0ac \uc77c\uc815(\uc678\uadfc\u00b7\ucd9c\uc7a5) \ub4f1\ub85d'" @ok="handleCompanySubmit" @cancel="closeCompanyModal" :ok-text="editingCompanySchedule ? '\uc800\uc7a5' : '\ub4f1\ub85d'" :cancel-text="'\ucde8\uc18c'">
          <a-form layout="vertical" style="margin-top: 16px;">
            <a-form-item label="일정명" required>
              <a-auto-complete
                v-model:value="newCompanySchedule.content"
                :options="companyProjectOptions"
                :filter-option="filterCompanyProjectOption"
                @search="searchCompanyCommonProjects"
                @select="selectCompanyProject"
                @change="changeCompanyProjectInput"
              />
            </a-form-item>
            <a-form-item label="일정 유형">
              <a-select v-model:value="newCompanySchedule.type">
                <a-select-option value="#52c41a">외근</a-select-option>
                <a-select-option value="#722ed1">국내 출장</a-select-option>
                <a-select-option value="#fa8c16">국외 출장</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="일정 선택" required v-if="isCompanyFieldWork">
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <a-date-picker v-model:value="newCompanySchedule.workDate" placeholder="일자 선택" style="flex: 1 1 180px; min-width: 160px;" />
                <a-time-picker v-model:value="newCompanySchedule.startTime" format="HH:mm" :minute-step="30" style="width: 110px;" />
                <span>~</span>
                <a-time-picker v-model:value="newCompanySchedule.endTime" format="HH:mm" :minute-step="30" style="width: 110px;" />
              </div>
            </a-form-item>
            <a-form-item label="기간" required v-else>
              <a-range-picker v-model:value="newCompanySchedule.dateValue" format="YYYY-MM-DD" :placeholder="['시작일', '종료일']" style="width: 100%" />
            </a-form-item>
          </a-form>
        </a-modal>
      </a-tab-pane>

      <a-tab-pane key="refresh-calendar" tab="전사 일정(휴가)">
        <div class="calendar-nav">
          <div style="display: flex; align-items: center; gap: 10px;">
            <a-button @click="prevRefreshMonth"><LeftOutlined /></a-button>
            <span class="calendar-period-label">
              {{ refreshYearMonth }}
            </span>
            <a-button @click="nextRefreshMonth"><RightOutlined /></a-button>
            <a-button size="small" @click="goRefreshToday" style="margin-left: 8px;">이번 달</a-button>
          </div>
          <a-button type="primary" size="small" @click="openRefreshModal">
            <template #icon><PlusOutlined /></template>일정 등록
          </a-button>
        </div>

        <a-card :bordered="false" class="grid-card" style="padding: 10px; min-height: 600px;">
          <a-calendar v-model:value="refreshCalendarValue" :fullscreen="true" @panelChange="handleRefreshPanelChange">
            <template #dateFullCellRender="{ current }">
              <div :class="['ant-picker-cell-inner', 'ant-picker-calendar-date', getRefreshCellClass(current)]" 
                   style="cursor: pointer; height: 100%; overflow: visible;" 
                   @click="openRefreshDetailModal(current)">
                <div class="ant-picker-calendar-date-value">
                  {{ current.date() }}
                </div>
                <div class="ant-picker-calendar-date-content">
                  <ul class="events calendar-event-list">
                    <li v-for="item in getRefreshVisibleListData(current)" :key="item.id" 
                        :style="getEventStyle(item, current)"
                        class="calendar-event-chip">
                      {{ shouldShowEventText(item, current) ? item.content : '\u00A0' }}
                    </li>
                    <li v-if="getRefreshHiddenCount(current) > 0" class="calendar-more-link" @click.stop="openRefreshDetailModal(current)">
                      {{ '+' + getRefreshHiddenCount(current) + ' \ub354\ubcf4\uae30' }}
                    </li>
                  </ul>
                </div>
              </div>
            </template>
          </a-calendar>
        </a-card>	

        <a-modal :mask-closable="false" v-model:open="isRefreshDetailModalOpen" :title="`${selectedRefreshDate} 휴가 상세`" :footer="null">
          <div style="margin-top: 16px;">
            <a-list item-layout="horizontal" :data-source="refreshDetailList">
              <template #renderItem="{ item }">
                <a-list-item style="padding: 12px 4px;">
                  <div style="display: flex; flex-direction: column; gap: 4px; width: 100%;">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                      <a-badge :color="item.type" :text="item.raw_content" style="font-size: 14px; font-weight: 500;" />
                      <div v-if="canManageSchedule(item)" style="display: flex; gap: 4px; margin-left: 12px;">
                        <a-button type="link" size="small" @click.stop="openRefreshEditModal(item)">수정</a-button>
                        <a-button type="link" danger size="small" @click.stop="deleteRefreshSchedule(item)">삭제</a-button>
                      </div>
                    </div>
                    <div style="font-size: 12px; color: #8c8c8c; padding-left: 14px;">
                      <span v-if="item.is_all_day">종일</span>
                      <span v-else>{{ formatTimeRange(item.start_time, item.end_time) }}</span>
                      <span style="margin-left: 8px; font-weight: 500; color: #595959;">등록자: {{ item.user_name }}</span>
                    </div>
                  </div>
                </a-list-item>
              </template>
              <template #empty>
                <a-empty description="등록된 휴가 일정이 없습니다." />
              </template>
            </a-list>
          </div>
        </a-modal>

        <a-modal v-model:open="isRefreshModalOpen" :title="editingRefreshSchedule ? '\uc804\uc0ac \uc77c\uc815(\ud734\uac00) \uc218\uc815' : '\uc804\uc0ac \uc77c\uc815(\ud734\uac00) \ub4f1\ub85d'" @ok="handleRefreshSubmit" @cancel="closeRefreshModal" :ok-text="editingRefreshSchedule ? '\uc800\uc7a5' : '\ub4f1\ub85d'" :cancel-text="'\ucde8\uc18c'">
          <a-form layout="vertical" style="margin-top: 16px;">
            <a-form-item label="일정명" required>
              <a-input v-model:value="newRefreshSchedule.content" placeholder="예시 : 하계휴가, 연차" />
            </a-form-item>
            <a-form-item label="일정 유형">
              <a-select v-model:value="newRefreshSchedule.type">
                <a-select-option value="#bae7ff">연차</a-select-option>
                <a-select-option value="#13c2c2">반차</a-select-option>
                <a-select-option value="#eb2f96">반반차</a-select-option>
                <a-select-option value="#1890ff">대체휴가</a-select-option>
                <a-select-option value="#bfbfbf">하계휴가</a-select-option>
                <a-select-option value="#ff7a45">병가</a-select-option>
                <a-select-option value="#d9d9d9">기타</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="기간" required>
              <a-range-picker v-model:value="newRefreshSchedule.dateValue" format="YYYY-MM-DD" :placeholder="['시작일', '종료일']" style="width: 100%" />
            </a-form-item>
          </a-form>
        </a-modal>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import api, { timesheetApi, executionApi, salesApi } from '@/api'
import dayjs from 'dayjs'
import { message, Modal } from 'ant-design-vue'
import { LeftOutlined, RightOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const activeTab = ref('company-calendar')
const currentUserName = computed(() => (auth.user?.name || '').trim())
const CALENDAR_VISIBLE_EVENT_LIMIT = 2
const COMPANY_PROJECT_SOURCES = new Set(['실행', '영업', '공통'])

function getScheduleErrorMessage(error, fallback) {
  const detail = error?.response?.data?.detail
  return detail ? `${fallback} (${detail})` : fallback
}

// ══════════════════════════════════════════════════
// 탭 1: 전사 월간 일정 데이터 및 로직
// ══════════════════════════════════════════════════
const companyCalendarValue = ref(dayjs()) 
const companySchedules     = ref([])
const companyHoliday       = ref([]) 
const companyHolidayCache  = ref({})
const companyProjects      = ref([])
const companySalesProjects = ref([])
const companyCommonProjectSuggestions = ref([])
let companyCommonSearchTimer = null

const isCompanyModalOpen   = ref(false)
const newCompanySchedule   = ref(createDefaultCompanySchedule())
const editingCompanySchedule = ref(null)
const isCompanyFieldWork  = computed(() => newCompanySchedule.value.type === '#52c41a')


function createDefaultCompanySchedule() {
  return {
    content: '',
    dateValue: null,
    rangeValue: null,
    workDate: null,
    startTime: dayjs('2026-01-01 08:30'),
    endTime: dayjs('2026-01-01 17:30'),
    type: '#52c41a',
    timesheet_project_id: null,
    timesheet_project_name: '',
    timesheet_project_source: '공통',
  }
}

function labelCompanyProjectOption(option) {
  const source = option.source || '공통'
  return `[${source}] ${option.value || option.project_name || ''}`
}

const companyProjectOptions = computed(() => {
  const executionOptions = companyProjects.value.map(project => {
    const projectNo = (project.project_no || '').trim()
    const projectName = (project.project_name || '').trim()
    const value = [projectNo, projectName].filter(Boolean).join(' ') || projectName || projectNo
    return {
      value,
      label: labelCompanyProjectOption({ source: '실행', value }),
      searchText: `${projectNo} ${projectName}`.toLowerCase(),
      id: project.id,
      project_name: projectName || value,
      source: '실행',
    }
  }).filter(option => option.value)

  const salesOptions = companySalesProjects.value.map(row => {
    const projectNo = (row.project_no || row.sales_no || '').trim()
    const projectName = (row.project_name || '').trim()
    const value = [projectNo, projectName].filter(Boolean).join(' ') || projectName || projectNo
    if (!value) return null
    return {
      value,
      label: labelCompanyProjectOption({ source: '영업', value }),
      searchText: `${projectNo} ${projectName} ${row.client_name || ''} ${row.sales_status || ''}`.toLowerCase(),
      id: null,
      project_name: projectName || value,
      source: '영업',
    }
  }).filter(Boolean)

  const commonOptions = companyCommonProjectSuggestions.value.map(item => {
    const value = item.project_name || item.value || item.label || ''
    return {
      value,
      label: labelCompanyProjectOption({ source: '공통', value }),
      searchText: value.toLowerCase(),
      id: null,
      project_name: value,
      source: '공통',
    }
  }).filter(option => option.value)

  return [...executionOptions, ...salesOptions, ...commonOptions]
})

function filterCompanyProjectOption(input, option) {
  const keyword = String(input || '').trim().toLowerCase()
  if (!keyword) return true
  return String(option.searchText || option.value || option.label || '').toLowerCase().includes(keyword)
}

function findCompanyProjectOption(value, option = null) {
  const selectedValue = String(value || '').trim()
  const optionValue = String(option?.value || '').trim()
  return companyProjectOptions.value.find(item =>
    item === option
    || item.value === selectedValue
    || item.value === optionValue
    || item.project_name === selectedValue
  ) || option || null
}

function applyCompanyProjectOption(selected, fallbackValue = '') {
  const source = COMPANY_PROJECT_SOURCES.has(selected?.source) ? selected.source : '공통'
  newCompanySchedule.value.timesheet_project_id = source === '실행' ? (selected?.id || null) : null
  newCompanySchedule.value.timesheet_project_name = selected?.project_name || selected?.value || fallbackValue || ''
  newCompanySchedule.value.timesheet_project_source = source
}

function selectCompanyProject(value, option) {
  applyCompanyProjectOption(findCompanyProjectOption(value, option), value)
}

function changeCompanyProjectInput(value) {
  const typed = String(value || '').trim()
  const selected = findCompanyProjectOption(typed)
  if (selected) {
    applyCompanyProjectOption(selected, typed)
    return
  }
  newCompanySchedule.value.timesheet_project_id = null
  newCompanySchedule.value.timesheet_project_name = typed
  newCompanySchedule.value.timesheet_project_source = '공통'
}

async function loadCompanyCommonProjectSuggestions(keyword = '') {
  try {
    const res = await timesheetApi.searchCommonProjects({ q: String(keyword || '').trim(), limit: 20 })
    companyCommonProjectSuggestions.value = res.data || []
  } catch (_) {
    companyCommonProjectSuggestions.value = []
  }
}

function searchCompanyCommonProjects(value) {
  if (companyCommonSearchTimer) clearTimeout(companyCommonSearchTimer)
  companyCommonSearchTimer = setTimeout(() => loadCompanyCommonProjectSuggestions(value), 180)
}

async function loadCompanySalesProjects() {
  try {
    const weekStart = dayjs().startOf('week').add(1, 'day').format('YYYY-MM-DD')
    const current = await salesApi.getSalesManagementRows(weekStart)
    if ((current.data || []).length) {
      companySalesProjects.value = current.data || []
      return
    }
    const latest = await salesApi.getLatestSalesManagementRowsBefore(weekStart)
    companySalesProjects.value = latest.data?.rows || []
  } catch (_) {
    companySalesProjects.value = []
  }
}

async function loadCompanyProjectSources() {
  const [projects] = await Promise.all([
    executionApi.getProjects().catch(() => ({ data: [] })),
    loadCompanySalesProjects(),
    loadCompanyCommonProjectSuggestions(),
  ])
  companyProjects.value = projects.data || []
}

const isCompanyDetailModalOpen = ref(false)
const selectedCompanyDate      = ref('')
const companyDetailList        = ref([])

const companyYearMonth = computed(() => {
  return companyCalendarValue.value ? companyCalendarValue.value.format('YYYY년 MM월') : ''
})

async function fetchCompanyHolidayFromServer(year) {
  if (!year) return
  if (companyHolidayCache.value[year]) {
    companyHoliday.value = companyHolidayCache.value[year]
    return
  }
  try {
    const response = await api.get('/holiday', { params: { year } })
    if (response.data && Array.isArray(response.data)) {
      companyHolidayCache.value[year] = response.data
      companyHoliday.value = response.data
    } else {
      companyHolidayCache.value[year] = []
      companyHoliday.value = []
    }
  } catch (error) {
    console.error('전사 일정 공휴일 조회 실패:', error)
    companyHoliday.value = []
  }
}

function getCompanyCellClass(currentDate) {
  if (!currentDate || !companyCalendarValue.value) return ''
  const dateStr = currentDate.format('YYYY-MM-DD')
  const day = currentDate.day()
  const isWeekend = (day === 0 || day === 6)
  
  const isHoliday = companyHoliday.value.includes(dateStr)
  const isCurrentMonth = currentDate.month() === companyCalendarValue.value.month()

  let cls = ''
  if (!isCurrentMonth) cls += ' is-out-view'
  if (isWeekend || isHoliday) cls += ' is-red-day'
  if (dateStr === dayjs().format('YYYY-MM-DD')) cls += ' is-today'
  return cls
}

function prevCompanyMonth() {
  companyCalendarValue.value = companyCalendarValue.value.subtract(1, 'month')
  loadCompanyCalendarData()
}

function nextCompanyMonth() {
  companyCalendarValue.value = companyCalendarValue.value.add(1, 'month')
  loadCompanyCalendarData()
}

function goCompanyToday() {
  companyCalendarValue.value = dayjs()
  loadCompanyCalendarData()
}

function handleCompanyPanelChange(value) {
  companyCalendarValue.value = value
}

function getCompanyListData(currentDate) {
  const dateStr = currentDate.format('YYYY-MM-DD')
  const list = companySchedules.value.filter(item => {
    if (item.start_date && item.end_date) {
      return dateStr >= item.start_date && dateStr <= item.end_date
    }
    return item.date === dateStr
  })
  return sortCalendarEvents(list, dateStr)
}

function getCompanyVisibleListData(currentDate) {
  return getCompanyListData(currentDate).slice(0, CALENDAR_VISIBLE_EVENT_LIMIT)
}

function getCompanyHiddenCount(currentDate) {
  return Math.max(getCompanyListData(currentDate).length - CALENDAR_VISIBLE_EVENT_LIMIT, 0)
}

async function loadCompanyCalendarData() {
  try {
    const response = await api.get('/schedules', { params: { category: 'company' } }) 
    const events = response.data || []
    companySchedules.value = events.map(item => {
      let timePrefix = ''
      if (!item.is_all_day && item.start_time) {
        timePrefix = `${item.start_time.slice(11, 16)} `
      }
      return {
        id: item.id,
        date: item.date,
        is_all_day: item.is_all_day,
        start_time: item.start_time,
        end_time: item.end_time,
        start_date: item.start_date,
        end_date: item.end_date,
        content: item.user_name ? `${timePrefix}[${item.user_name}] ${item.content}` : `${timePrefix}${item.content}`,
        raw_content: item.content,
        user_name: item.user_name,
        type: item.type,
        schedule_kind: item.schedule_kind,
        timesheet_project_id: item.timesheet_project_id,
        timesheet_project_name: item.timesheet_project_name,
        timesheet_project_source: item.timesheet_project_source
      }
    })
  } catch (error) {
    console.error('전사 일정 조회 실패:', error)
    message.error(getScheduleErrorMessage(error, '전사 월간 일정을 불러오지 못했습니다.'))
  }
}

function resetCompanyForm() {
  editingCompanySchedule.value = null
  newCompanySchedule.value = createDefaultCompanySchedule()
}

function openCompanyModal() {
  resetCompanyForm()
  isCompanyModalOpen.value = true
}

function closeCompanyModal() {
  isCompanyModalOpen.value = false
  resetCompanyForm()
}

function openCompanyEditModal(item) {
  if (!canManageSchedule(item)) return
  editingCompanySchedule.value = item
  newCompanySchedule.value = {
    content: item.raw_content || '',
    dateValue: item.is_all_day ? [dayjs(item.start_date || item.date), dayjs(item.end_date || item.date)] : null,
    rangeValue: null,
    workDate: item.is_all_day ? null : dayjs(item.date || item.start_time?.slice(0, 10)),
    startTime: item.start_time ? dayjs(item.start_time) : dayjs('2026-01-01 08:30'),
    endTime: item.end_time ? dayjs(item.end_time) : dayjs('2026-01-01 17:30'),
    type: item.type || '#52c41a',
    timesheet_project_id: item.timesheet_project_id || null,
    timesheet_project_name: item.timesheet_project_name || item.raw_content || '',
    timesheet_project_source: COMPANY_PROJECT_SOURCES.has(item.timesheet_project_source) ? item.timesheet_project_source : '공통'
  }
  isCompanyDetailModalOpen.value = false
  isCompanyModalOpen.value = true
}

async function handleCompanySubmit() {
  if (!newCompanySchedule.value.content) {
    message.warning('\uc77c\uc815\uba85\uc744 \uc785\ub825\ud574 \uc8fc\uc138\uc694.')
    return
  }
  if (isCompanyFieldWork.value) {
    if (!newCompanySchedule.value.workDate || !newCompanySchedule.value.startTime || !newCompanySchedule.value.endTime) {
      message.warning('\uc77c\uc790\uc640 \uc2dc\uac04\uc744 \uc120\ud0dd\ud574 \uc8fc\uc138\uc694.')
      return
    }
    if (!newCompanySchedule.value.endTime.isAfter(newCompanySchedule.value.startTime)) {
      message.warning('\uc885\ub8cc \uc2dc\uac04\uc740 \uc2dc\uc791 \uc2dc\uac04\ubcf4\ub2e4 \ub2a6\uc5b4\uc57c \ud569\ub2c8\ub2e4.')
      return
    }
  } else {
    if (!newCompanySchedule.value.dateValue || newCompanySchedule.value.dateValue.length < 2) {
      message.warning('\uae30\uac04\uc744 \uc120\ud0dd\ud574 \uc8fc\uc138\uc694.')
      return
    }
  }
  try {
    const payload = {
      content: newCompanySchedule.value.content,
      type: newCompanySchedule.value.type,
      category: 'company',
      user_name: auth.user?.name || '\ubbf8\ud655\uc778',
      is_all_day: !isCompanyFieldWork.value,
      schedule_kind: isCompanyFieldWork.value ? '외근' : '출장',
      timesheet_project_id: newCompanySchedule.value.timesheet_project_id || null,
      timesheet_project_name: newCompanySchedule.value.timesheet_project_name || newCompanySchedule.value.content,
      timesheet_project_source: newCompanySchedule.value.timesheet_project_source || '공통'
    }
    if (isCompanyFieldWork.value) {
      const workDate = newCompanySchedule.value.workDate.format('YYYY-MM-DD')
      payload.start_time = `${workDate} ${newCompanySchedule.value.startTime.format('HH:mm')}:00`
      payload.end_time = `${workDate} ${newCompanySchedule.value.endTime.format('HH:mm')}:00`
    } else {
      payload.date = newCompanySchedule.value.dateValue[0].format('YYYY-MM-DD')
      payload.end_date = newCompanySchedule.value.dateValue[1].format('YYYY-MM-DD')
    }

    if (editingCompanySchedule.value) {
      await api.put(`/schedules/${editingCompanySchedule.value.id}`, payload)
      message.success('\uc804\uc0ac \uc77c\uc815 \uc218\uc815\uc774 \uc644\ub8cc\ub418\uc5c8\uc2b5\ub2c8\ub2e4.')
    } else {
      await api.post('/schedules', payload)
      message.success('\uc804\uc0ac \uc77c\uc815 \ub4f1\ub85d\uc774 \uc644\ub8cc\ub418\uc5c8\uc2b5\ub2c8\ub2e4.')
    }
    isCompanyModalOpen.value = false
    resetCompanyForm()
    await loadCompanyCalendarData()
  } catch (error) {
    console.error('\uc804\uc0ac \uc77c\uc815 \uc800\uc7a5 \uc2e4\ud328:', error)
    message.error(error.response?.data?.detail || '\uc77c\uc815 \uc800\uc7a5 \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4.')
  }
}

function getSchedulesForDate(list, currentDate) {
  const dateStr = currentDate.format('YYYY-MM-DD')
  return list.filter(item => {
    if (item.start_date && item.end_date) {
      return dateStr >= item.start_date && dateStr <= item.end_date
    }
    return item.date === dateStr
  })
}

function canManageSchedule(item) {
  return Boolean(item?.user_name && currentUserName.value && item.user_name === currentUserName.value)
}

function openCompanyDetailModal(currentDate) {
  selectedCompanyDate.value = currentDate.format('YYYY\ub144 MM\uc6d4 DD\uc77c')
  companyDetailList.value = getSchedulesForDate(companySchedules.value, currentDate)
  isCompanyDetailModalOpen.value = true
}

function deleteCompanySchedule(item) {
  if (!canManageSchedule(item)) return
  Modal.confirm({
    title: '\uc77c\uc815\uc744 \uc0ad\uc81c\ud558\uc2dc\uaca0\uc2b5\ub2c8\uae4c?',
    content: '\uc0ad\uc81c\ud55c \uc77c\uc815\uc740 \ubcf5\uad6c\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.',
    okText: '\uc0ad\uc81c',
    okType: 'danger',
    cancelText: '\ucde8\uc18c',
    async onOk() {
      try {
        await api.delete(`/schedules/${item.id}`, { params: { category: 'company' } })
        message.success('\uc804\uc0ac \uc77c\uc815\uc774 \uc0ad\uc81c\ub418\uc5c8\uc2b5\ub2c8\ub2e4.')
        isCompanyDetailModalOpen.value = false
        await loadCompanyCalendarData()
      } catch (error) {
        console.error('\uc804\uc0ac \uc77c\uc815 \uc0ad\uc81c \uc2e4\ud328:', error)
        message.error(error.response?.data?.detail || '\uc77c\uc815 \uc0ad\uc81c \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4.')
      }
    }
  })
}

// ══════════════════════════════════════════════════
// 탭 2: 전사 휴가 일정 데이터 및 로직
// ══════════════════════════════════════════════════
const refreshCalendarValue = ref(dayjs()) 
const refreshSchedules     = ref([])
const refreshHoliday       = ref([]) 
const refreshHolidayCache  = ref({})

const isRefreshModalOpen   = ref(false)
const newRefreshSchedule   = ref({ content: '', dateValue: null, rangeValue: null, type: '#bae7ff' })
const editingRefreshSchedule = ref(null)

const isRefreshDetailModalOpen = ref(false)
const selectedRefreshDate      = ref('')
const refreshDetailList        = ref([])

const refreshYearMonth = computed(() => {
  return refreshCalendarValue.value ? refreshCalendarValue.value.format('YYYY년 MM월') : ''
})

async function fetchRefreshHolidayFromServer(year) {
  if (!year) return
  if (refreshHolidayCache.value[year]) {
    refreshHoliday.value = refreshHolidayCache.value[year]
    return
  }
  try {
    const response = await api.get('/holiday', { params: { year } })
    if (response.data && Array.isArray(response.data)) {
      refreshHolidayCache.value[year] = response.data
      refreshHoliday.value = response.data
    } else {
      refreshHolidayCache.value[year] = []
      refreshHoliday.value = []
    }
  } catch (error) {
    console.error('휴가 일정 공휴일 조회 실패:', error)
    refreshHoliday.value = []
  }
}

function getRefreshCellClass(currentDate) {
  if (!currentDate || !refreshCalendarValue.value) return ''
  const dateStr = currentDate.format('YYYY-MM-DD')
  const day = currentDate.day()
  const isWeekend = (day === 0 || day === 6)
  
  const isHoliday = refreshHoliday.value.includes(dateStr)
  const isCurrentMonth = currentDate.month() === refreshCalendarValue.value.month()

  let cls = ''
  if (!isCurrentMonth) cls += ' is-out-view'
  if (isWeekend || isHoliday) cls += ' is-red-day'
  if (dateStr === dayjs().format('YYYY-MM-DD')) cls += ' is-today'
  return cls
}

function prevRefreshMonth() {
  refreshCalendarValue.value = refreshCalendarValue.value.subtract(1, 'month')
  loadRefreshCalendarData()
}

function nextRefreshMonth() {
  refreshCalendarValue.value = refreshCalendarValue.value.add(1, 'month')
  loadRefreshCalendarData()
}

function goRefreshToday() {
  refreshCalendarValue.value = dayjs()
  loadRefreshCalendarData()
}

function handleRefreshPanelChange(value) {
  refreshCalendarValue.value = value
}

function getRefreshListData(currentDate) {
  const dateStr = currentDate.format('YYYY-MM-DD')
  const list = refreshSchedules.value.filter(item => {
    if (item.start_date && item.end_date) {
      return dateStr >= item.start_date && dateStr <= item.end_date
    }
    return item.date === dateStr
  })
  return sortCalendarEvents(list, dateStr)
}

function getRefreshVisibleListData(currentDate) {
  return getRefreshListData(currentDate).slice(0, CALENDAR_VISIBLE_EVENT_LIMIT)
}

function getRefreshHiddenCount(currentDate) {
  return Math.max(getRefreshListData(currentDate).length - CALENDAR_VISIBLE_EVENT_LIMIT, 0)
}

async function loadRefreshCalendarData() {
  try {
    const response = await api.get('/schedules', { params: { category: 'refresh' } }) 
    const events = response.data || []
    refreshSchedules.value = events.map(item => {
      let timePrefix = ''
      if (!item.is_all_day && item.start_time) {
        timePrefix = `${item.start_time.slice(11, 16)} `
      }
      return {
        id: item.id,
        date: item.date,
        is_all_day: item.is_all_day,
        start_time: item.start_time,
        end_time: item.end_time,
        start_date: item.start_date,
        end_date: item.end_date,
        content: item.user_name ? `${timePrefix}[${item.user_name}] ${item.content}` : `${timePrefix}${item.content}`,
        raw_content: item.content,
        user_name: item.user_name,
        type: item.type,
        schedule_kind: item.schedule_kind,
        timesheet_project_id: item.timesheet_project_id,
        timesheet_project_name: item.timesheet_project_name,
        timesheet_project_source: item.timesheet_project_source
      }
    })
  } catch (error) {
    console.error('휴가 일정 조회 실패:', error)
    message.error(getScheduleErrorMessage(error, '전사 휴가 일정을 불러오지 못했습니다.'))
  }
}

function resetRefreshForm() {
  editingRefreshSchedule.value = null
  newRefreshSchedule.value = { content: '', dateValue: null, rangeValue: null, type: '#bae7ff' }
}

function openRefreshModal() {
  resetRefreshForm()
  isRefreshModalOpen.value = true
}

function closeRefreshModal() {
  isRefreshModalOpen.value = false
  resetRefreshForm()
}

function openRefreshEditModal(item) {
  if (!canManageSchedule(item)) return
  editingRefreshSchedule.value = item
  newRefreshSchedule.value = {
    content: item.raw_content || '',
    dateValue: [dayjs(item.start_date || item.date), dayjs(item.end_date || item.date)],
    rangeValue: null,
    type: item.type || '#bae7ff'
  }
  isRefreshDetailModalOpen.value = false
  isRefreshModalOpen.value = true
}

function getRefreshScheduleKind(type) {
  const map = {
    '#bae7ff': '\uC5F0\uCC28',
    '#13c2c2': '\uBC18\uCC28',
    '#eb2f96': '\uBC18\uBC18\uCC28',
    '#1890ff': '\uB300\uCCB4\uD734\uAC00',
    '#bfbfbf': '\uD558\uACC4\uD734\uAC00',
    '#ff7a45': '\uBCD1\uAC00',
    '#d9d9d9': '\uAE30\uD0C0',
  }
  return map[type] || '\uC5F0\uCC28'
}

async function handleRefreshSubmit() {
  if (!newRefreshSchedule.value.content) {
    message.warning('\uc77c\uc815\uba85\uc744 \uc785\ub825\ud574 \uc8fc\uc138\uc694.')
    return
  }
  if (!newRefreshSchedule.value.dateValue || newRefreshSchedule.value.dateValue.length < 2) {
    message.warning('\uae30\uac04\uc744 \uc120\ud0dd\ud574 \uc8fc\uc138\uc694.')
    return
  }
  try {
    const payload = {
      content: newRefreshSchedule.value.content,
      type: newRefreshSchedule.value.type,
      category: 'refresh',
      user_name: auth.user?.name || '\ubbf8\ud655\uc778',
      is_all_day: true,
      schedule_kind: getRefreshScheduleKind(newRefreshSchedule.value.type)
    }
    payload.date = newRefreshSchedule.value.dateValue[0].format('YYYY-MM-DD')
    payload.end_date = newRefreshSchedule.value.dateValue[1].format('YYYY-MM-DD')

    if (editingRefreshSchedule.value) {
      await api.put(`/schedules/${editingRefreshSchedule.value.id}`, payload)
      message.success('\uc804\uc0ac \ud734\uac00 \uc77c\uc815 \uc218\uc815\uc774 \uc644\ub8cc\ub418\uc5c8\uc2b5\ub2c8\ub2e4.')
    } else {
      await api.post('/schedules', payload)
      message.success('\uc804\uc0ac \ud734\uac00 \uc77c\uc815 \ub4f1\ub85d\uc774 \uc644\ub8cc\ub418\uc5c8\uc2b5\ub2c8\ub2e4.')
    }
    isRefreshModalOpen.value = false
    resetRefreshForm()
    await loadRefreshCalendarData()
  } catch (error) {
    console.error('\ud734\uac00 \uc77c\uc815 \uc800\uc7a5 \uc2e4\ud328:', error)
    message.error(error.response?.data?.detail || '\uc77c\uc815 \uc800\uc7a5 \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4.')
  }
}

function openRefreshDetailModal(currentDate) {
  selectedRefreshDate.value = currentDate.format('YYYY\ub144 MM\uc6d4 DD\uc77c')
  refreshDetailList.value = getSchedulesForDate(refreshSchedules.value, currentDate)
  isRefreshDetailModalOpen.value = true
}

function deleteRefreshSchedule(item) {
  if (!canManageSchedule(item)) return
  Modal.confirm({
    title: '\ud734\uac00 \uc77c\uc815\uc744 \uc0ad\uc81c\ud558\uc2dc\uaca0\uc2b5\ub2c8\uae4c?',
    content: '\uc0ad\uc81c\ud55c \uc77c\uc815\uc740 \ubcf5\uad6c\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.',
    okText: '\uc0ad\uc81c',
    okType: 'danger',
    cancelText: '\ucde8\uc18c',
    async onOk() {
      try {
        await api.delete(`/schedules/${item.id}`, { params: { category: 'refresh' } })
        message.success('\uc804\uc0ac \ud734\uac00 \uc77c\uc815\uc774 \uc0ad\uc81c\ub418\uc5c8\uc2b5\ub2c8\ub2e4.')
        isRefreshDetailModalOpen.value = false
        await loadRefreshCalendarData()
      } catch (error) {
        console.error('\ud734\uac00 \uc77c\uc815 \uc0ad\uc81c \uc2e4\ud328:', error)
        message.error(error.response?.data?.detail || '\uc77c\uc815 \uc0ad\uc81c \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4.')
      }
    }
  })
}

// ══════════════════════════════════════════════════
// 공통 가동 감시 및 생명주기 관련
// ══════════════════════════════════════════════════
watch(() => companyCalendarValue.value, (newVal, oldVal) => {
  if (!newVal) return
  const newYear = newVal.format('YYYY')
  const oldYear = oldVal ? oldVal.format('YYYY') : null
  if (newYear !== oldYear) fetchCompanyHolidayFromServer(newYear)
}, { immediate: true })

watch(() => refreshCalendarValue.value, (newVal, oldVal) => {
  if (!newVal) return
  const newYear = newVal.format('YYYY')
  const oldYear = oldVal ? oldVal.format('YYYY') : null
  if (newYear !== oldYear) fetchRefreshHolidayFromServer(newYear)
}, { immediate: true })

function sortCalendarEvents(list, dateStr) {
  return [...list].sort((a, b) => {
    const aStart = a.start_date || a.date || ''
    const bStart = b.start_date || b.date || ''
    const aContinues = a.start_date && a.start_date < dateStr ? 0 : 1
    const bContinues = b.start_date && b.start_date < dateStr ? 0 : 1
    if (aContinues !== bContinues) return aContinues - bContinues
    if (aStart !== bStart) return aStart.localeCompare(bStart)
    return String(a.id || '').localeCompare(String(b.id || ''))
  })
}

function formatTimeRange(startTime, endTime) {
  if (!startTime || !endTime) return ''
  const start = startTime.slice(11, 16)
  const end = endTime.slice(11, 16)
  return `${start} ~ ${end}`
}

function hexToRgba(hex, alpha) {
  if (!hex || !hex.startsWith('#')) return `rgba(82, 196, 26, ${alpha})`
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function getEventStyle(item, currentDate) {
  const baseColor = item.type || '#52c41a'
  if (!item.start_date || !item.end_date || item.start_date === item.end_date || !currentDate) {
    return {
      backgroundColor: hexToRgba(baseColor, 0.12),
      borderLeft: `3px solid ${baseColor}`,
      color: '#434343',
      padding: '2px 6px',
      borderRadius: '4px'
    }
  }

  const dateStr = currentDate.format('YYYY-MM-DD')
  const isStart = dateStr === item.start_date
  const isEnd = dateStr === item.end_date
  
  const dayOfWeek = currentDate.day() // 0 = Sunday, 6 = Saturday
  const isWeekStart = (dayOfWeek === 0)
  const isWeekEnd = (dayOfWeek === 6)
  
  const connectLeft = !isStart && !isWeekStart
  const connectRight = !isEnd && !isWeekEnd
  const bridgeSize = 20
  const extraWidth = (connectLeft ? bridgeSize : 0) + (connectRight ? bridgeSize : 0)
  
  return {
    backgroundColor: hexToRgba(baseColor, 0.35),
    color: '#1a2535',
    fontWeight: '600',
    boxShadow: 'inset 0 -2px 0 rgba(0, 0, 0, 0.05)',
    boxSizing: 'border-box',
    position: 'relative',
    zIndex: 1,
    width: extraWidth ? `calc(100% + ${extraWidth}px)` : '100%',
    marginLeft: connectLeft ? `-${bridgeSize}px` : '0px',
    marginRight: connectRight ? `-${bridgeSize}px` : '0px',
    paddingLeft: connectLeft ? `${bridgeSize}px` : '8px',
    paddingRight: connectRight ? `${bridgeSize}px` : '8px',
    borderLeft: connectLeft ? 'none' : `4px solid ${baseColor}`,
    borderTopLeftRadius: connectLeft ? '0px' : '4px',
    borderBottomLeftRadius: connectLeft ? '0px' : '4px',
    borderTopRightRadius: connectRight ? '0px' : '4px',
    borderBottomRightRadius: connectRight ? '0px' : '4px',
    paddingTop: '2px',
    paddingBottom: '2px'
  }
}

function shouldShowEventText(item, currentDate) {
  if (!item.start_date || !item.end_date || item.start_date === item.end_date) {
    return true
  }
  const dateStr = currentDate.format('YYYY-MM-DD')
  const isStart = dateStr === item.start_date
  const dayOfWeek = currentDate.day() // 0 = Sunday
  const isWeekStart = (dayOfWeek === 0)
  return isStart || isWeekStart
}

onMounted(() => {
  const currentYear = dayjs().format('YYYY')
  loadCompanyProjectSources()
  
  // 전사 일정 구동
  fetchCompanyHolidayFromServer(currentYear)
  loadCompanyCalendarData()
  
  // 휴가 일정 구동
  fetchRefreshHolidayFromServer(currentYear)
  loadRefreshCalendarData()
})
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 0; }
:deep(.main-tabs .ant-tabs-nav) { margin-bottom: 14px; }

:deep(.ant-picker-calendar-date),
:deep(.ant-picker-cell-inner),
:deep(.ant-picker-calendar-date-content) {
  overflow: visible !important;
}

.calendar-nav {
  display: flex; justify-content: space-between; align-items: center; 
  background: #fff; border-radius: 8px; padding: 12px 16px; 
  box-shadow: 0 1px 4px rgba(0,0,0,0.07); margin-bottom: 12px;
}
.calendar-period-label { font-size: 14px; font-weight: 700; color: #1a2535; min-width: 120px; text-align: center; }
.grid-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.calendar-event-list { list-style: none; padding: 0; margin: 0; }
.calendar-event-chip {
  margin-bottom: 3px;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
  line-height: 1.35;
  min-height: 18px;
  box-sizing: border-box;
  position: relative;
}
:deep(.ant-picker-calendar-date-content .calendar-event-list) { overflow: visible; }
.calendar-more-link {
  display: inline-flex;
  align-items: center;
  height: 18px;
  max-width: 100%;
  padding: 0 6px;
  border-radius: 4px;
  background: #f0f5ff;
  border: 1px solid #adc6ff;
  color: #1d4f91;
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  cursor: pointer;
}
.calendar-more-link:hover { background: #dbeafe; border-color: #69b1ff; }

:deep(.ant-picker-content th:first-child), :deep(.ant-picker-content th:last-child),
:deep(.ant-picker-calendar-thead th:first-child), :deep(.ant-picker-calendar-thead th:last-child) {
  color: #f5222d !important;
}
:deep(.is-red-day .ant-picker-calendar-date-value) { color: #f5222d !important; }
:deep(.is-out-view.is-red-day .ant-picker-calendar-date-value) { color: #ffa39e !important; }
:deep(.is-today.is-red-day .ant-picker-calendar-date-value) { color: #ffffff !important; }
</style>
