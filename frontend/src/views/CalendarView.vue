<template>
  <div class="page-wrap">
    <a-tabs v-model:activeKey="activeTab" class="main-tabs">
      
      <a-tab-pane key="company-calendar" tab="전사 월간 일정">
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
                  <ul class="events" style="list-style: none; padding: 0; margin: 0;">
                    <li v-for="item in getCompanyListData(current)" :key="item.id" style="margin-bottom: 2px; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                      <a-badge :color="item.type" :text="item.content" />
                    </li>
                  </ul>
                </div>
              </div>
            </template>
          </a-calendar>
        </a-card>	

        <a-modal v-model:open="isCompanyDetailModalOpen" :title="`${selectedCompanyDate} 일정 상세`" :footer="null">
          <div style="margin-top: 16px;">
            <a-list item-layout="horizontal" :data-source="companyDetailList">
              <template #renderItem="{ item }">
                <a-list-item style="padding: 12px 4px;">
                  <a-badge :color="item.type" :text="item.content" style="font-size: 14px;" />
                </a-list-item>
              </template>
              <template #empty>
                <a-empty description="등록된 일정이 없습니다." />
              </template>
            </a-list>
          </div>
        </a-modal>

        <a-modal v-model:open="isCompanyModalOpen" title="전사 월간 일정 등록" @ok="handleCompanySubmit" @cancel="closeCompanyModal" ok-text="등록" cancel-text="취소">
          <a-form layout="vertical" style="margin-top: 16px;">
            <a-form-item label="일정명" required>
              <a-input v-model:value="newCompanySchedule.content" placeholder="예: 전사 정기 미팅, 현장 작업" />
            </a-form-item>
            <a-form-item label="날짜" required>
              <a-date-picker v-model:value="newCompanySchedule.dateValue" style="width: 100%" placeholder="날짜 선택" />
            </a-form-item>
            <a-form-item label="일정 유형">
              <a-select v-model:value="newCompanySchedule.type">
                <a-select-option value="#52c41a">외근 (초록)</a-select-option>
                <a-select-option value="#722ed1">국내 출장 (보라)</a-select-option>
                <a-select-option value="#fa8c16">국외 출장 (빨강)</a-select-option>
              </a-select>
            </a-form-item>
          </a-form>
        </a-modal>
      </a-tab-pane>

      <a-tab-pane key="refresh-calendar" tab="전사 휴가 일정">
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
                   style="cursor: pointer;" 
                   @click="openRefreshDetailModal(current)">
                <div class="ant-picker-calendar-date-value">
                  {{ current.date() }}
                </div>
                <div class="ant-picker-calendar-date-content">
                  <ul class="events" style="list-style: none; padding: 0; margin: 0;">
                    <li v-for="item in getRefreshListData(current)" :key="item.id" style="margin-bottom: 2px; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                      <a-badge :color="item.type" :text="item.content" />
                    </li>
                  </ul>
                </div>
              </div>
            </template>
          </a-calendar>
        </a-card>	

        <a-modal v-model:open="isRefreshDetailModalOpen" :title="`${selectedRefreshDate} 휴가 상세`" :footer="null">
          <div style="margin-top: 16px;">
            <a-list item-layout="horizontal" :data-source="refreshDetailList">
              <template #renderItem="{ item }">
                <a-list-item style="padding: 12px 4px;">
                  <a-badge :color="item.type" :text="item.content" style="font-size: 14px;" />
                </a-list-item>
              </template>
              <template #empty>
                <a-empty description="등록된 휴가 일정이 없습니다." />
              </template>
            </a-list>
          </div>
        </a-modal>

        <a-modal v-model:open="isRefreshModalOpen" title="전사 휴가 일정 등록" @ok="handleRefreshSubmit" @cancel="closeRefreshModal" ok-text="등록" cancel-text="취소">
          <a-form layout="vertical" style="margin-top: 16px;">
            <a-form-item label="일정명" required>
              <a-input v-model:value="newRefreshSchedule.content" placeholder="예: 여름휴가, OOO 매니저 연차" />
            </a-form-item>
            <a-form-item label="날짜" required>
              <a-date-picker v-model:value="newRefreshSchedule.dateValue" style="width: 100%" placeholder="날짜 선택" />
            </a-form-item>
            <a-form-item label="일정 유형">
              <a-select v-model:value="newRefreshSchedule.type">
                <a-select-option value="#bae7ff">연차 (연파랑)</a-select-option>
                <a-select-option value="#1890ff">시간연차 (파랑)</a-select-option>
                <a-select-option value="#bfbfbf">기타 (회색)</a-select-option>
              </a-select>
            </a-form-item>
          </a-form>
        </a-modal>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'
import dayjs from 'dayjs'
import { message } from 'ant-design-vue'
import { LeftOutlined, RightOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const activeTab = ref('company-calendar')

// ══════════════════════════════════════════════════
// 탭 1: 전사 월간 일정 데이터 및 로직
// ══════════════════════════════════════════════════
const companyCalendarValue = ref(dayjs()) 
const companySchedules     = ref([])
const companyHoliday       = ref([]) 
const companyHolidayCache  = ref({})

const isCompanyModalOpen   = ref(false)
const newCompanySchedule   = ref({ content: '', dateValue: null, type: '#52c41a' }) // 기본값 컬러코드로 세팅

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
    const response = await axios.get('/api/holiday', { params: { year } })
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
  return companySchedules.value.filter(item => item.date === dateStr)
}

async function loadCompanyCalendarData() {
  try {
    const response = await axios.get('/api/schedules', { params: { category: 'company' } }) 
    const events = response.data || []
    companySchedules.value = events.map(item => ({
      id: item.id,
      date: item.date,
      content: item.user_name ? `[${item.user_name}] ${item.content} ` : item.content, 
      type: item.type
    }))
  } catch (error) {
    console.error('전사 일정 조회 실패:', error)
    message.error('전사 월간 일정을 불러오지 못했습니다.')
  }
}

function openCompanyModal() {
  newCompanySchedule.value = { content: '', dateValue: null, type: '#52c41a' }
  isCompanyModalOpen.value = true
}

function closeCompanyModal() {
  isCompanyModalOpen.value = false
}

async function handleCompanySubmit() {
  if (!newCompanySchedule.value.content) {
    message.warning('일정명을 입력해 주세요.')
    return
  }
  if (!newCompanySchedule.value.dateValue) {
    message.warning('날짜를 선택해 주세요.')
    return
  }
  try {
    const formattedDate = newCompanySchedule.value.dateValue.format('YYYY-MM-DD')
    await axios.post('/api/schedules', {
      content: newCompanySchedule.value.content,
      date: formattedDate,
      type: newCompanySchedule.value.type,
      category: 'company',
      user_name: auth.user?.name || '미확인'
    })
    message.success('전사 일정 등록이 완료되었습니다.')
    isCompanyModalOpen.value = false
    loadCompanyCalendarData()
  } catch (error) {
    console.error('전사 일정 등록 실패:', error)
    message.error(error.response?.data?.detail || '일정 등록 중 오류가 발생했습니다.')
  }
}

function openCompanyDetailModal(currentDate) {
  const dateStr = currentDate.format('YYYY-MM-DD')
  selectedCompanyDate.value = currentDate.format('YYYY년 MM월 DD일')
  companyDetailList.value = companySchedules.value.filter(item => item.date === dateStr)
  isCompanyDetailModalOpen.value = true
}

// ══════════════════════════════════════════════════
// 탭 2: 전사 휴가 일정 데이터 및 로직
// ══════════════════════════════════════════════════
const refreshCalendarValue = ref(dayjs()) 
const refreshSchedules     = ref([])
const refreshHoliday       = ref([]) 
const refreshHolidayCache  = ref({})

const isRefreshModalOpen   = ref(false)
const newRefreshSchedule   = ref({ content: '', dateValue: null, type: '#bae7ff' }) // 기본값 컬러코드로 세팅

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
    const response = await axios.get('/api/holiday', { params: { year } })
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
  return refreshSchedules.value.filter(item => item.date === dateStr)
}

async function loadRefreshCalendarData() {
  try {
    const response = await axios.get('/api/schedules', { params: { category: 'refresh' } }) 
    const events = response.data || []
    refreshSchedules.value = events.map(item => ({
      id: item.id,
      date: item.date,
      content: item.user_name ? `[${item.user_name}] ${item.content} ` : item.content, 
      type: item.type
    }))
  } catch (error) {
    console.error('휴가 일정 조회 실패:', error)
    message.error('전사 휴가 일정을 불러오지 못했습니다.')
  }
}

function openRefreshModal() {
  newRefreshSchedule.value = { content: '', dateValue: null, type: '#bae7ff' }
  isRefreshModalOpen.value = true
}

function closeRefreshModal() {
  isRefreshModalOpen.value = false
}

async function handleRefreshSubmit() {
  if (!newRefreshSchedule.value.content) {
    message.warning('일정명을 입력해 주세요.')
    return
  }
  if (!newRefreshSchedule.value.dateValue) {
    message.warning('날짜를 선택해 주세요.')
    return
  }
  try {
    const formattedDate = newRefreshSchedule.value.dateValue.format('YYYY-MM-DD')
    await axios.post('/api/schedules', {
      content: newRefreshSchedule.value.content,
      date: formattedDate,
      type: newRefreshSchedule.value.type,
      category: 'refresh',
      user_name: auth.user?.name || '미확인'
    })
    message.success('전사 휴가 일정 등록이 완료되었습니다.')
    isRefreshModalOpen.value = false
    loadRefreshCalendarData()
  } catch (error) {
    console.error('휴가 일정 등록 실패:', error)
    message.error(error.response?.data?.detail || '일정 등록 중 오류가 발생했습니다.')
  }
}

function openRefreshDetailModal(currentDate) {
  const dateStr = currentDate.format('YYYY-MM-DD')
  selectedRefreshDate.value = currentDate.format('YYYY년 MM월 DD일')
  refreshDetailList.value = refreshSchedules.value.filter(item => item.date === dateStr)
  isRefreshDetailModalOpen.value = true
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

onMounted(() => {
  const currentYear = dayjs().format('YYYY')
  
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

.calendar-nav {
  display: flex; justify-content: space-between; align-items: center; 
  background: #fff; border-radius: 8px; padding: 12px 16px; 
  box-shadow: 0 1px 4px rgba(0,0,0,0.07); margin-bottom: 12px;
}
.calendar-period-label { font-size: 14px; font-weight: 700; color: #1a2535; min-width: 120px; text-align: center; }
.grid-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }

:deep(.ant-picker-content th:first-child), :deep(.ant-picker-content th:last-child),
:deep(.ant-picker-calendar-thead th:first-child), :deep(.ant-picker-calendar-thead th:last-child) {
  color: #f5222d !important;
}
:deep(.is-red-day .ant-picker-calendar-date-value) { color: #f5222d !important; }
:deep(.is-out-view.is-red-day .ant-picker-calendar-date-value) { color: #ffa39e !important; }
:deep(.is-today.is-red-day .ant-picker-calendar-date-value) { color: #ffffff !important; }
</style>