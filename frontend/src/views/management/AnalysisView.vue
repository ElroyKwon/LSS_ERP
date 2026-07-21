<template>
  <div class="page-wrap">
    <a-tabs class="analysis-tabs">
      <a-tab-pane v-for="tab in analysisTabs" :key="tab.key" :tab="tab.label">
    <a-card :bordered="false" class="table-card">
      <template #title>
        <div class="title-row">
          <span class="card-title">{{ tab.label }}</span>
          <div class="month-nav">
            <a-button size="small" @click="moveMonth(-1)">
              <template #icon><LeftOutlined /></template>
            </a-button>
            <a-date-picker
              v-model:value="selectedMonth"
              picker="month"
              value-format="YYYY-MM"
              format="YYYY년 MM월"
              :allow-clear="false"
              class="month-picker"
              @change="load"
            />
            <a-button size="small" @click="moveMonth(1)">
              <template #icon><RightOutlined /></template>
            </a-button>
          </div>
        </div>
      </template>
      <template #extra>
        <a-space>
          <a-tag color="blue">1주차 {{ tabAnalysis(tab)?.week1_start || '-' }}</a-tag>
          <a-tag color="purple">4주차 {{ tabAnalysis(tab)?.week4_start || '-' }}</a-tag>
          <a-tag v-if="tab.key === 'orders' && dirty" color="orange">변경 있음</a-tag>
          <a-button v-if="tab.key === 'orders'" type="primary" size="small" :loading="saving" :disabled="!dirty" @click="saveBusinessPlan">
            <template #icon><SaveOutlined /></template>
            저장
          </a-button>
        </a-space>
      </template>

      <div class="grid-help">
        영업관리 주차 데이터 중 수주확도 A~C 항목만 불러옵니다. 사업계획은 직접 입력하고, 실적/이동계획은 선택 월의 1주차와 4주차 영업관리 저장본을 기준으로 표시합니다.
      </div>

      <a-table
        :columns="tableColumns(tab)"
        :data-source="tableRows(tab)"
        :loading="loading"
        :pagination="{ pageSize: 20, showSizeChanger: true }"
        :scroll="{ x: tableScrollXValue(tab), y: 620 }"
        row-key="row_key"
        size="small"
        bordered
        class="analysis-table"
      
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="tab.key === 'orders' && column.groupKey === 'business_plan' && column.month">
            <a-input-number
              v-model:value="record.business_plan.months[column.month]"
              :min="0"
              :formatter="amountFormatter"
              :parser="amountParser"
              class="table-number-input"
              @focus="clearZero(record.business_plan.months, column.month)"
              @change="markDirty"
            />
          </template>

          <template v-else-if="column.groupKey === 'business_plan' && column.total">
            <span class="num-cell readonly-cell">{{ formatAmount(businessPlanTotal(record)) }}</span>
          </template>

          <template v-else-if="column.groupKey">
            <span class="num-cell readonly-cell">{{ formatAmount(groupValue(record, column)) }}</span>
          </template>

          <template v-else-if="column.key === 'probability'">
            <a-tag :color="probabilityColor(record.probability)">{{ record.probability || '-' }}</a-tag>
          </template>

          <template v-else-if="column.key === 'sales_status'">
            <a-tag color="blue">{{ record.sales_status || '-' }}</a-tag>
          </template>

          <template v-else>
            {{ record[column.key] || '-' }}
          </template>
        </template>
      </a-table>
    </a-card>

    <a-card :bordered="false" class="table-card">
      <template #title>
        <span class="card-title">{{ tab.divisionTitle }}</span>
      </template>
      <a-table
        :columns="summaryColumns"
        :data-source="businessDivisionSummaryRows"
        :loading="loading"
        :pagination="{ pageSize: 20, showSizeChanger: true }"
        :scroll="{ x: summaryTableScrollX }"
        row-key="business_division"
        size="small"
        bordered
        class="analysis-table"
      
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key !== 'business_division'">
            <span class="num-cell readonly-cell">{{ formatAmount(record[column.key]) }}</span>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-card :bordered="false" class="table-card">
      <template #title>
        <span class="card-title">{{ tab.groupTitle }}</span>
      </template>
      <a-table
        :columns="businessGroupSummaryColumns"
        :data-source="businessGroupSummaryRows"
        :loading="loading"
        :pagination="{ pageSize: 20, showSizeChanger: true }"
        :scroll="{ x: businessGroupSummaryTableScrollX }"
        row-key="business_category"
        size="small"
        bordered
        class="analysis-table"
      
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key !== 'business_category'">
            <span class="num-cell readonly-cell">{{ formatAmount(record[column.key]) }}</span>
          </template>
        </template>
      </a-table>
    </a-card>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { LeftOutlined, RightOutlined, SaveOutlined } from '@ant-design/icons-vue'
import { executionApi, managementApi, masterApi } from '@/api'
import { flattenDepartmentTree } from '@/utils/departments'

const now = new Date()
const selectedMonth = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)
const loading = ref(false)
const saving = ref(false)
const dirty = ref(false)
const analysis = ref(null)
const rows = ref([])
const revenueAnalysis = ref(null)
const revenueRows = ref([])
const departments = ref([])
const businessCategories = ref([])

const DEFAULT_BUSINESS_CATEGORIES = ['빌딩', 'DC', 'BAS', 'E&M', 'O&M', 'DR', 'FEMS리스', 'SE', '솔루션', 'CS', '스테콤', 'SCADA']
const EXCLUDED_SUMMARY_DIVISIONS = new Set(['사장실', 'CFO 부문', '공통'])
const analysisTabs = [
  {
    key: 'orders',
    label: '경영 분석(수주)',
    divisionTitle: '사업계획 수주 종합(사업부)',
    groupTitle: '사업계획 수주 종합(사업군)',
  },
  {
    key: 'revenue',
    label: '경영 분석(매출)',
    divisionTitle: '사업계획 매출 종합(사업부)',
    groupTitle: '사업계획 매출 종합(사업군)',
  },
]

const selectedYear = computed(() => Number(selectedMonth.value.slice(0, 4)))
const selectedMonthNo = computed(() => Number(selectedMonth.value.slice(5, 7)))
const nextYear = computed(() => selectedYear.value + 1)
const shortYear = computed(() => String(selectedYear.value).slice(2))
const shortNextYear = computed(() => String(nextYear.value).slice(2))
const monthLabels = Array.from({ length: 12 }, (_, index) => `${index + 1}월`)

const tableScrollX = computed(() => sumColumnWidths(columns.value))
const revenueTableScrollX = computed(() => sumColumnWidths(revenueColumns.value))
const summaryTableScrollX = computed(() => sumColumnWidths(summaryColumns.value))
const businessGroupSummaryTableScrollX = computed(() => sumColumnWidths(businessGroupSummaryColumns.value))

const columns = computed(() => [
  leaf('사업부', 'business_division', 130, 'center', true, 'left'),
  leaf('영업팀', 'sales_team', 130, 'center', true, 'left'),
  leaf('사업구분', 'business_category', 110, 'center', true, 'left'),
  leaf('영업번호', 'sales_no', 110, 'center', false, 'left'),
  leaf('프로젝트명', 'project_name', 220, 'center', true, 'left'),
  leaf('수주확도', 'probability', 90),
  leaf('영업상태', 'sales_status', 130),
  leaf('내수/해외', 'domestic_overseas', 100),
  leaf('특수관계', 'special_relation', 100),
  amountGroup(`${selectedYear.value}년도 사업계획`, 'business_plan', `${shortYear.value}년도 발주 합계`, true),
  amountGroup(`${selectedYear.value}년도 실적/이동계획(1주)`, 'current_week1', `${shortYear.value}년도 발주 합계`),
  amountGroup(`${selectedYear.value}년도 실적/이동계획(4주)`, 'current_week4', `${shortYear.value}년도 발주 합계`),
  amountGroup(`${nextYear.value}년도 실적/이동계획(1주)`, 'next_week1', `${shortNextYear.value}년도 발주 합계`),
  amountGroup(`${nextYear.value}년도 실적/이동계획(4주)`, 'next_week4', `${shortNextYear.value}년도 발주 합계`),
])

const revenueColumns = computed(() => [
  leaf('구분', 'source_type', 90, 'center', false, 'left'),
  leaf('사업부', 'business_division', 130, 'center', true, 'left'),
  leaf('팀', 'sales_team', 130, 'center', true, 'left'),
  leaf('사업구분', 'business_category', 110, 'center', true, 'left'),
  leaf('영업번호', 'sales_no', 110, 'center'),
  leaf('JOB NO', 'job_no', 120, 'center'),
  leaf('프로젝트명', 'project_name', 220, 'center', true),
  leaf('계약업체명', 'contract_company', 160, 'center', true),
  leaf('내수/해외', 'domestic_overseas', 100),
  leaf('특수관계', 'special_relation', 100),
  amountGroup(`${selectedYear.value}년도 사업계획`, 'business_plan', `${selectedYear.value}년도 매출 합계`, false),
  amountGroup(`${selectedYear.value}년 실적/이동계획(1주)`, 'current_week1', `${selectedYear.value}년도 매출 합계`),
  amountGroup(`${selectedYear.value}년 실적/이동계획(4주)`, 'current_week4', `${selectedYear.value}년도 매출 합계`),
  amountGroup(`${nextYear.value}년 실적/이동계획(1주)`, 'next_week1', `${nextYear.value}년도 매출 합계`),
  amountGroup(`${nextYear.value}년 실적/이동계획(4주)`, 'next_week4', `${nextYear.value}년도 매출 합계`),
])

const summaryColumns = computed(() => [
  leaf('사업부', 'business_division', 150, 'center', true, 'left'),
  group('기준월 실적', [
    leaf('실적', 'base_actual', 135, 'right'),
    leaf('이동', 'base_move', 135, 'right'),
    leaf('이동비', 'base_move_rate', 135, 'right'),
  ]),
  group('기준월 누계', [
    leaf('실적', 'monthly_actual', 135, 'right'),
    leaf('전년 사업부별 실적 누계', 'monthly_prev_actual', 170, 'right'),
    leaf('계획', 'monthly_plan', 135, 'right'),
    leaf('이동', 'monthly_move', 135, 'right'),
    leaf('전년비', 'monthly_prev_rate', 135, 'right'),
    leaf('계획비', 'monthly_plan_rate', 135, 'right'),
    leaf('이동비', 'monthly_move_rate', 135, 'right'),
  ]),
  group('연간 누계', [
    leaf('실적', 'year_actual', 135, 'right'),
    leaf('전년 사업부별 실적 누계', 'year_prev_plan', 170, 'right'),
    leaf('이동', 'year_move', 135, 'right'),
    leaf('전년비', 'year_prev_rate', 135, 'right'),
    leaf('계획비', 'year_plan_rate', 135, 'right'),
    leaf('이동비', 'year_move_rate', 135, 'right'),
  ]),
])

const businessGroupSummaryColumns = computed(() => [
  leaf('사업군', 'business_category', 150, 'center', true, 'left'),
  ...summaryColumns.value.slice(1),
])

const businessDivisionSummaryRows = computed(() => {
  const divisions = businessDivisionOptions.value
  const rowsByDivision = divisions.map(division => buildSummaryRow(
    rows.value.filter(row => row.business_division === division),
    { business_division: division },
  ))
  return [
    buildSummaryRow(
      rows.value.filter(row => divisions.includes(row.business_division)),
      { business_division: '합계(전사)' },
    ),
    ...rowsByDivision,
  ]
})

const businessGroupSummaryRows = computed(() => {
  const categories = businessCategoryOptions.value
  return [
    buildSummaryRow(rows.value, { business_category: '합계(전사)' }),
    ...categories.map(category => buildSummaryRow(
      rows.value.filter(row => row.business_category === category),
      { business_category: category },
    )),
  ]
})

const businessDivisionOptions = computed(() => {
  const topLevel = flattenDepartmentTree(departments.value)
    .filter(dept => !dept.parent_id)
    .filter(dept => ['office', 'business', 'division'].includes(dept.dept_type))
    .map(dept => dept.name)
    .filter(name => name && !EXCLUDED_SUMMARY_DIVISIONS.has(name))
  if (topLevel.length) return [...new Set(topLevel)]

  const rowDivisions = rows.value
    .map(row => row.business_division)
    .filter(name => name && !EXCLUDED_SUMMARY_DIVISIONS.has(name))
  return [...new Set(rowDivisions)]
})

const businessCategoryOptions = computed(() => {
  const categories = businessCategories.value.length ? businessCategories.value : DEFAULT_BUSINESS_CATEGORIES
  return [...new Set(categories.filter(Boolean))]
})

function leaf(title, key, width = 120, align = 'center', ellipsis = false, fixed = undefined) {
  return { title, key, dataIndex: key, width, align, ellipsis, fixed }
}

function group(title, children) {
  return { title, align: 'center', children }
}

function amountGroup(title, groupKey, totalTitle, editable = false) {
  return {
    title,
    align: 'center',
    children: [
      { title: totalTitle, key: `${groupKey}_total`, width: 145, align: 'right', groupKey, total: true },
      ...monthLabels.map((label, index) => ({
        title: label,
        key: `${groupKey}_${index + 1}`,
        width: 135,
        align: 'right',
        groupKey,
        month: String(index + 1),
        editable,
      })),
    ],
  }
}

function tableColumns(tab) {
  return tab.key === 'revenue' ? revenueColumns.value : columns.value
}

function tableRows(tab) {
  return tab.key === 'revenue' ? revenueRows.value : rows.value
}

function tableScrollXValue(tab) {
  return tab.key === 'revenue' ? revenueTableScrollX.value : tableScrollX.value
}

function tabAnalysis(tab) {
  return tab.key === 'revenue' ? revenueAnalysis.value : analysis.value
}

function monthValue(row, groupKey, month) {
  return toNumber(row[groupKey]?.months?.[String(month)])
}

function monthSum(row, groupKey, toMonth = 12) {
  let sum = 0
  for (let month = 1; month <= toMonth; month += 1) {
    sum += monthValue(row, groupKey, month)
  }
  return sum
}

function rowsMonthSum(sourceRows, groupKey, month) {
  return sourceRows.reduce((sum, row) => sum + monthValue(row, groupKey, month), 0)
}

function rowsCumulativeSum(sourceRows, groupKey, toMonth = 12) {
  return sourceRows.reduce((sum, row) => sum + monthSum(row, groupKey, toMonth), 0)
}

function buildSummaryRow(sourceRows, identity) {
  const baseMonth = selectedMonthNo.value
  const baseActual = rowsMonthSum(sourceRows, 'current_week1', baseMonth)
  const baseMove = rowsMonthSum(sourceRows, 'current_week4', baseMonth)
  const monthlyActual = rowsCumulativeSum(sourceRows, 'current_week1', baseMonth)
  const monthlyPrevActual = 0
  const monthlyPlan = rowsCumulativeSum(sourceRows, 'business_plan', baseMonth)
  const monthlyMove = rowsCumulativeSum(sourceRows, 'current_week4', baseMonth)
  const yearActual = rowsCumulativeSum(sourceRows, 'current_week1', 12)
  const yearPrevPlan = 0
  const yearPlan = rowsCumulativeSum(sourceRows, 'business_plan', 12)
  const yearMove = rowsCumulativeSum(sourceRows, 'current_week4', 12)

  return {
    ...identity,
    base_actual: baseActual,
    base_move: baseMove,
    base_move_rate: baseActual - baseMove,
    monthly_actual: monthlyActual,
    monthly_prev_actual: monthlyPrevActual,
    monthly_plan: monthlyPlan,
    monthly_move: monthlyMove,
    monthly_prev_rate: monthlyActual - monthlyPrevActual,
    monthly_plan_rate: monthlyActual - monthlyPlan,
    monthly_move_rate: monthlyActual - monthlyMove,
    year_actual: yearActual,
    year_prev_plan: yearPrevPlan,
    year_move: yearMove,
    year_prev_rate: yearActual - yearPrevPlan,
    year_plan_rate: yearActual - yearPlan,
    year_move_rate: yearActual - yearMove,
  }
}

function sumColumnWidths(list) {
  return list.reduce((sum, column) => sum + (column.children ? sumColumnWidths(column.children) : (column.width || 120)), 0)
}

function moveMonth(delta) {
  const [year, month] = selectedMonth.value.split('-').map(Number)
  const date = new Date(year, month - 1 + delta, 1)
  selectedMonth.value = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
  load()
}

function toNumber(value) {
  const parsed = Number(String(value ?? 0).replace(/,/g, ''))
  return Number.isFinite(parsed) ? parsed : 0
}

function amountFormatter(value) {
  if (value === null || value === undefined || value === '') return ''
  return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

function amountParser(value) {
  return String(value ?? '').replace(/,/g, '')
}

function formatAmount(value) {
  const amount = Math.round(toNumber(value))
  return amount ? amount.toLocaleString() : '-'
}

function clearZero(target, key) {
  if (toNumber(target[key]) === 0) target[key] = undefined
}

function probabilityColor(value) {
  if (value === 'A') return 'green'
  if (value === 'B') return 'blue'
  if (value === 'C') return 'orange'
  return 'default'
}

function businessPlanTotal(record) {
  return monthLabels.reduce((sum, _label, index) => sum + toNumber(record.business_plan?.months?.[String(index + 1)]), 0)
}

function groupValue(record, column) {
  const group = record[column.groupKey] || {}
  if (column.total) return group.total || 0
  return group.months?.[column.month] || 0
}

function normalizeRow(source = {}) {
  const businessMonths = {}
  for (let month = 1; month <= 12; month += 1) {
    businessMonths[String(month)] = toNumber(source.business_plan?.months?.[String(month)])
  }
  return {
    ...source,
    business_plan: {
      total: toNumber(source.business_plan?.total),
      months: businessMonths,
    },
  }
}

function serializeBusinessPlanRow(row) {
  const months = {}
  for (let month = 1; month <= 12; month += 1) {
    months[String(month)] = toNumber(row.business_plan?.months?.[String(month)])
  }
  return {
    row_key: row.row_key,
    business_division: row.business_division,
    sales_team: row.sales_team,
    business_category: row.business_category,
    sales_no: row.sales_no,
    project_name: row.project_name,
    probability: row.probability,
    sales_status: row.sales_status,
    domestic_overseas: row.domestic_overseas,
    special_relation: row.special_relation,
    business_plan_total: Object.values(months).reduce((sum, value) => sum + toNumber(value), 0),
    business_plan_months: months,
  }
}

function markDirty() {
  dirty.value = true
}

function apiErrorMessage(error, fallback) {
  return error?.response?.data?.detail || error?.message || fallback
}

async function load() {
  loading.value = true
  try {
    const [salesResult, revenueResult] = await Promise.allSettled([
      managementApi.getSalesPlanAnalysis(selectedYear.value, selectedMonthNo.value),
      managementApi.getRevenuePlanAnalysis(selectedYear.value, selectedMonthNo.value),
    ])

    if (salesResult.status === 'fulfilled') {
      analysis.value = salesResult.value.data
      rows.value = (salesResult.value.data?.rows || []).map(normalizeRow)
    } else {
      analysis.value = null
      rows.value = []
      message.error(apiErrorMessage(salesResult.reason, '경영분석(수주) 데이터를 불러오지 못했습니다.'))
    }

    if (revenueResult.status === 'fulfilled') {
      revenueAnalysis.value = revenueResult.value.data
      revenueRows.value = (revenueResult.value.data?.rows || []).map(normalizeRow)
    } else {
      revenueAnalysis.value = null
      revenueRows.value = []
      message.error(apiErrorMessage(revenueResult.reason, '경영분석(매출) 데이터를 불러오지 못했습니다.'))
    }

    const [deptResult, categoryResult] = await Promise.allSettled([
      masterApi.getDepartments({ org_year: selectedYear.value, include_inactive: false, tree: true }),
      executionApi.getProjectBusinessCategories(),
    ])

    if (deptResult.status === 'fulfilled') {
      departments.value = deptResult.value.data || []
    } else {
      departments.value = []
      message.warning(apiErrorMessage(deptResult.reason, '부서 정보를 불러오지 못해 경영분석 데이터 기준으로 요약합니다.'))
    }

    if (categoryResult.status === 'fulfilled') {
      businessCategories.value = Array.isArray(categoryResult.value.data) ? categoryResult.value.data : []
    } else {
      businessCategories.value = []
      message.warning(apiErrorMessage(categoryResult.reason, '사업구분 정보를 불러오지 못해 기본 항목으로 요약합니다.'))
    }

    dirty.value = false
  } finally {
    loading.value = false
  }
}

async function saveBusinessPlan() {
  saving.value = true
  try {
    await managementApi.saveSalesBusinessPlan(selectedYear.value, rows.value.map(serializeBusinessPlanRow))
    dirty.value = false
    message.success('사업계획이 저장되었습니다.')
    await load()
  } catch (error) {
    message.error(error.response?.data?.detail || '저장 중 오류가 발생했습니다.')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.table-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.title-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 12px;
  width: 100%;
}
.card-title { justify-self: start; font-size: 15px; font-weight: 600; color: #1a2535; }
.month-nav { justify-self: center; display: inline-flex; align-items: center; gap: 8px; }
.month-picker { width: 145px; }
.grid-help { margin-bottom: 10px; color: #8c8c8c; font-size: 12px; }
.table-number-input { width: 100%; }
.num-cell {
  display: block;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.readonly-cell {
  min-height: 30px;
  padding: 5px 8px;
  border-radius: 4px;
  background: #fafafa;
  color: #1a2535;
  font-weight: 600;
}
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
:deep(.ant-table-tbody > tr > td) { padding: 6px 8px; }
:deep(.analysis-table .ant-input-number-input) { text-align: right; }
</style>
