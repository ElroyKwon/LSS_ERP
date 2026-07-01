<template>
  <div class="page-wrap">
    <a-card :bordered="false" class="table-card">
      <template #title>
        <span class="card-title">{{ currentYear }}년 영업 진행 Project List</span>
      </template>
      <template #extra>
        <a-space wrap>
          <div class="week-nav">
            <a-button @click="moveWeek(-1)">
              <template #icon><LeftOutlined /></template>
            </a-button>
            <span class="week-period">{{ weekRangeLabel }}</span>
            <a-tag v-if="sourceWeek && sourceWeek !== weekStart" color="orange">
              {{ sourceWeek }} 자료 복사
            </a-tag>
            <a-tag v-else color="blue">작성중</a-tag>
            <a-button @click="moveWeek(1)">
              <template #icon><RightOutlined /></template>
            </a-button>
            <a-button @click="goThisWeek">이번 주</a-button>
          </div>
          <a-button @click="addRow">
            <template #icon><PlusOutlined /></template>
            행 추가
          </a-button>
          <input ref="excelInput" type="file" accept=".xlsx,.xlsm,.xls" style="display:none" @change="handleExcelFile" />
          <a-button :loading="importing" @click="excelInput?.click()">
            <template #icon><UploadOutlined /></template>엑셀 업로드
          </a-button>
          <a-button @click="downloadTemplate">
            <template #icon><DownloadOutlined /></template>양식 다운로드
          </a-button>
          <a-button type="primary" :loading="saving" @click="saveRows">저장</a-button>
        </a-space>
      </template>

      <a-alert
        v-if="dirty"
        type="warning"
        show-icon
        message="저장되지 않은 변경사항이 있습니다."
        class="dirty-alert"
      />

      <a-table
        :columns="columns"
        :data-source="rows"
        :loading="loading"
        :pagination="{ pageSize: 20, showSizeChanger: true }"
        :scroll="{ x: tableScrollX }"
        row-key="id"
        size="small"
        bordered
        class="sales-management-table"
      
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'project_name'">
            <a-input
              v-model:value="record.project_name"
              class="table-text-input"
              @change="handleTextChange(record)"
            />
          </template>

          <template v-else-if="column.key === 'probability'">
            <a-select
              v-model:value="record.probability"
              :options="probabilityOptions"
              class="table-select"
              @change="markDirty"
            />
          </template>

          <template v-else-if="column.key === 'sales_status'">
            <a-select
              v-model:value="record.sales_status"
              :options="salesStatusOptions"
              class="table-select"
              @change="handleSalesStatusChange(record)"
            />
          </template>

          <template v-else-if="column.key === 'entry_round' || column.key === 'sales_no' || column.key === 'project_no'">
            <span class="readonly-text-cell">{{ record[column.key] || '-' }}</span>
          </template>

          <template v-else-if="dateKeys.has(column.key)">
            <a-date-picker
              v-model:value="record[column.key]"
              value-format="YYYY-MM-DD"
              class="table-date-input"
              @change="markDirty"
            />
          </template>

          <template v-else-if="calculatedKeys.has(column.key)">
            <span class="num-cell readonly-cell">
              {{ column.key === 'profit_rate' ? formatPercent(calculatedValue(record, column.key)) : formatAmount(calculatedValue(record, column.key)) }}
            </span>
          </template>

          <template v-else-if="amountKeys.has(column.key)">
            <a-input-number
              v-model:value="record[column.key]"
              :min="0"
              :formatter="amountFormatter"
              :parser="amountParser"
              class="table-number-input"
              @focus="clearZero(record, column.key)"
              @change="markDirty"
            />
          </template>

          <template v-else-if="percentKeys.has(column.key)">
            <a-input-number
              v-model:value="record[column.key]"
              :min="0"
              :max="100"
              :precision="2"
              class="table-number-input"
              @focus="clearZero(record, column.key)"
              @change="markDirty"
            />
          </template>

          <template v-else-if="textKeys.has(column.key)">
            <a-input
              v-model:value="record[column.key]"
              class="table-text-input"
              @change="handleTextChange(record)"
            />
          </template>

          <template v-else-if="column.key === 'action'">
            <a-popconfirm
              title="해당 행을 삭제하시겠습니까?"
              ok-text="삭제"
              ok-type="danger"
              cancel-text="취소"
              @confirm="removeRow(record.id)"
            >
              <a-button danger size="small">삭제</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { DownloadOutlined, LeftOutlined, PlusOutlined, RightOutlined, UploadOutlined } from '@ant-design/icons-vue'
import { executionApi, salesApi } from '@/api'

const now = new Date()
const currentYear = now.getFullYear()
const nextYear = currentYear + 1
const carryoverYear = currentYear + 2
const monthLabels = Array.from({ length: 12 }, (_, index) => `${index + 1}월`)

const probabilityOptions = ['A', 'B', 'C', 'D', 'E'].map(value => ({ value, label: value }))
const salesStatusOptions = ['수주확정', '사업발굴', '수주기회개발', '입찰', '견적', '협상', '계약진행', '수주실패']
  .map(value => ({ value, label: value }))
const textKeys = new Set([
  'client_name',
  'business_division',
  'sales_team',
  'business_category',
  'manager',
  'revenue_type',
  'domestic_overseas',
  'special_relation',
])
const dateKeys = new Set(['contract_expected_date', 'completion_expected_date'])
const percentKeys = new Set(['material_ratio'])

const amountKeys = new Set([
  'expected_order_amount',
  ...monthLabels.map(month => `order_current_${month}`),
  ...monthLabels.map(month => `order_next_${month}`),
  ...monthLabels.map(month => `revenue_current_${month}`),
  ...monthLabels.map(month => `revenue_next_${month}`),
])
const calculatedKeys = new Set([
  'material_cost',
  'order_current_total',
  'order_next_total',
  'revenue_current_total',
  'order_current_backlog',
  'revenue_next_total',
  'order_next_backlog',
  'carryover_revenue',
  'gross_profit',
  'profit_rate',
])

const loading = ref(false)
const saving = ref(false)
const importing = ref(false)
const dirty = ref(false)
const rows = ref([])
const projects = ref([])
const sourceWeek = ref(null)
const weekStart = ref(formatDate(startOfWeek(new Date())))
const excelInput = ref()

const tableScrollX = computed(() => sumColumnWidths(columns.value))
const weekEnd = computed(() => {
  const date = new Date(weekStart.value)
  date.setDate(date.getDate() + 6)
  return date
})
const weekRangeLabel = computed(() => `${formatWeekDate(new Date(weekStart.value))} ~ ${formatWeekDate(weekEnd.value)}`)

const columns = computed(() => [
  leaf('작성차수', 'entry_round', 100, 'center', false, 'left'),
  leaf('영업번호', 'sales_no', 110, 'center', false, 'left'),
  leaf('프로젝트명', 'project_name', 220, 'center', true),
  leaf('발주처', 'client_name', 180),
  leaf('수주확도', 'probability', 90),
  leaf('영업상태', 'sales_status', 130),
  leaf('프로젝트번호', 'project_no', 130),
  leaf('사업부', 'business_division', 140),
  leaf('영업팀', 'sales_team', 150),
  leaf('사업구분', 'business_category', 110),
  leaf('담당자', 'manager', 110),
  leaf('구분(매출유형)', 'revenue_type', 130),
  leaf('계약예정일', 'contract_expected_date', 125),
  leaf('준공예정일', 'completion_expected_date', 125),
  leaf('내수/해외', 'domestic_overseas', 100),
  leaf('특수관계', 'special_relation', 100),
  leaf('재료비', 'material_cost', 135, 'right'),
  leaf('재료비율(%)', 'material_ratio', 135, 'right'),
  leaf('발주예상금액', 'expected_order_amount', 145, 'right'),
  group(`${currentYear}년 발주`, [
    leaf(`${currentYear}년도 발주합계`, 'order_current_total', 150, 'right'),
    ...monthLabels.map(month => leaf(month, `order_current_${month}`, 135, 'right')),
  ]),
  group(`${nextYear}년 발주`, [
    leaf(`${nextYear}년도 발주합계`, 'order_next_total', 150, 'right'),
    ...monthLabels.map(month => leaf(month, `order_next_${month}`, 135, 'right')),
  ]),
  group('매출 계획', [
    leaf(`${currentYear}년도 매출합계`, 'revenue_current_total', 150, 'right'),
    ...monthLabels.map(month => leaf(`${month}매출`, `revenue_current_${month}`, 135, 'right')),
    leaf(`${currentYear}년 수주잔`, 'order_current_backlog', 145, 'right'),
    leaf(`${nextYear}년도 매출합계`, 'revenue_next_total', 150, 'right'),
    ...monthLabels.map(month => leaf(`${month}매출`, `revenue_next_${month}`, 135, 'right')),
    leaf(`${nextYear}년 수주잔`, 'order_next_backlog', 145, 'right'),
  ]),
  leaf(`${carryoverYear}년 이월 매출`, 'carryover_revenue', 155, 'right'),
  leaf('매출이익', 'gross_profit', 140, 'right'),
  leaf('매출이익률(%)', 'profit_rate', 135, 'right'),
  leaf('관리', 'action', 85, 'center', false, 'right'),
])

function leaf(title, key, width = 120, align = 'center', ellipsis = false, fixed = undefined) {
  return { title, key, dataIndex: key, width, align, ellipsis, fixed }
}

function group(title, children) {
  return { title, align: 'center', children }
}

function sumColumnWidths(list) {
  return list.reduce((sum, column) => sum + (column.children ? sumColumnWidths(column.children) : (column.width || 120)), 0)
}

function formatDate(date) {
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

function formatWeekDate(date) {
  return `${date.getFullYear()}.${date.getMonth() + 1}.${date.getDate()}`
}

function formatEntryRound(value) {
  const date = new Date(value)
  const firstDay = new Date(date.getFullYear(), date.getMonth(), 1)
  const mondayOffset = (firstDay.getDay() + 6) % 7
  const weekNo = Math.floor((date.getDate() + mondayOffset - 1) / 7) + 1
  return `${String(date.getFullYear()).slice(2)}-${String(date.getMonth() + 1).padStart(2, '0')}-${weekNo}`
}

function startOfWeek(date) {
  const value = new Date(date)
  const day = value.getDay()
  const diff = day === 0 ? -6 : 1 - day
  value.setHours(0, 0, 0, 0)
  value.setDate(value.getDate() + diff)
  return value
}

function moveWeek(delta) {
  const date = new Date(weekStart.value)
  date.setDate(date.getDate() + delta * 7)
  weekStart.value = formatDate(startOfWeek(date))
  loadRows()
}

function goThisWeek() {
  weekStart.value = formatDate(startOfWeek(new Date()))
  loadRows()
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
  const number = Math.round(toNumber(value))
  return number ? number.toLocaleString() : '-'
}

function formatPercent(value) {
  const number = toNumber(value)
  return number ? `${number.toFixed(1)}%` : '-'
}

function clearZero(record, key) {
  if (toNumber(record[key]) === 0) record[key] = undefined
}

function sumMonths(row, prefix) {
  return monthLabels.reduce((sum, month) => sum + toNumber(row[`${prefix}_${month}`]), 0)
}

function calculatedValue(row, key) {
  const expectedOrderAmount = toNumber(row.expected_order_amount)
  const materialCost = expectedOrderAmount * toNumber(row.material_ratio) / 100
  const orderCurrentTotal = sumMonths(row, 'order_current')
  const orderNextTotal = sumMonths(row, 'order_next')
  const revenueCurrentTotal = sumMonths(row, 'revenue_current')
  const revenueNextTotal = sumMonths(row, 'revenue_next')
  const orderCurrentBacklog = orderCurrentTotal - revenueCurrentTotal
  const orderNextBacklog = orderCurrentBacklog + orderNextTotal - revenueNextTotal
  const grossProfit = expectedOrderAmount - materialCost

  switch (key) {
    case 'material_cost': return materialCost
    case 'order_current_total': return orderCurrentTotal
    case 'order_next_total': return orderNextTotal
    case 'revenue_current_total': return revenueCurrentTotal
    case 'order_current_backlog': return orderCurrentBacklog
    case 'revenue_next_total': return revenueNextTotal
    case 'order_next_backlog': return orderNextBacklog
    case 'carryover_revenue': return orderNextBacklog
    case 'gross_profit': return grossProfit
    case 'profit_rate': return expectedOrderAmount ? grossProfit / expectedOrderAmount * 100 : 0
    default: return 0
  }
}

function normalizedText(value) {
  return String(value || '').trim().toLowerCase()
}

function findMatchedProject(row) {
  const projectName = normalizedText(row.project_name)
  const clientName = normalizedText(row.client_name)
  if (!projectName) return null
  return projects.value.find(project => {
    const sameProject = normalizedText(project.project_name) === projectName
    const sameClient = !clientName || normalizedText(project.client_name) === clientName
    return sameProject && sameClient
  }) || null
}

function syncProjectNo(row) {
  if (row.sales_status !== '수주확정') return
  const matched = findMatchedProject(row)
  if (matched?.project_no) row.project_no = matched.project_no
  if (matched?.domestic_overseas && !row.domestic_overseas) row.domestic_overseas = matched.domestic_overseas
  if (matched?.special_relation && !row.special_relation) row.special_relation = matched.special_relation
}

function handleSalesStatusChange(record) {
  syncProjectNo(record)
  markDirty()
}

function handleTextChange(record) {
  syncProjectNo(record)
  markDirty()
}

function normalizeRow(source = {}) {
  const row = {
    id: source.id || `manual-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    entry_round: source.entry_round || formatEntryRound(weekStart.value),
    sales_no: source.sales_no || '',
    project_name: source.project_name || '',
    client_name: source.client_name || '',
    probability: source.probability || 'C',
    sales_status: source.sales_status || '사업발굴',
    project_no: source.project_no || '',
    business_division: source.business_division || '',
    sales_team: source.sales_team || '',
    business_category: source.business_category || '',
    manager: source.manager || '',
    revenue_type: source.revenue_type || '',
    contract_expected_date: source.contract_expected_date || null,
    completion_expected_date: source.completion_expected_date || null,
    domestic_overseas: source.domestic_overseas || '',
    special_relation: source.special_relation || '',
    material_ratio: toNumber(source.material_ratio),
    expected_order_amount: toNumber(source.expected_order_amount),
    ...source,
  }

  amountKeys.forEach(key => { row[key] = toNumber(row[key]) })
  percentKeys.forEach(key => { row[key] = toNumber(row[key]) })
  calculatedKeys.forEach(key => { row[key] = calculatedValue(row, key) })
  syncProjectNo(row)
  return row
}

function addRow() {
  rows.value = [...rows.value, normalizeRow()]
  markDirty()
}

function removeRow(id) {
  rows.value = rows.value.filter(row => row.id !== id)
  markDirty()
}

function markDirty() {
  dirty.value = true
}

function saveBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.URL.revokeObjectURL(url)
}

async function downloadTemplate() {
  const res = await salesApi.downloadSalesManagementTemplate()
  saveBlob(res.data, '영업관리_양식.xlsx')
}

async function handleExcelFile(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await salesApi.importSalesManagementExcel(weekStart.value, formData)
    const { imported = 0, updated = 0, skipped = 0, rows: importedRows = [] } = res.data || {}
    rows.value = importedRows.map(normalizeRow)
    sourceWeek.value = weekStart.value
    dirty.value = false
    message.success(`엑셀 업로드 완료: 신규 ${imported}건, 수정 ${updated}건, 제외 ${skipped}건`)
  } catch (e) {
    message.error(e.response?.data?.detail || '엑셀 업로드 중 오류가 발생했습니다.')
  } finally {
    importing.value = false
  }
}

function serializeRow(row) {
  const payload = { ...row }
  calculatedKeys.forEach(key => { payload[key] = calculatedValue(row, key) })
  return payload
}

async function loadRows() {
  loading.value = true
  try {
    await loadProjects()
    const current = await salesApi.getSalesManagementRows(weekStart.value)
    if ((current.data || []).length) {
      rows.value = current.data.map(normalizeRow)
      sourceWeek.value = weekStart.value
      dirty.value = false
      return
    }

    const latest = await salesApi.getLatestSalesManagementRowsBefore(weekStart.value)
    if ((latest.data?.rows || []).length) {
      rows.value = latest.data.rows.map(row => normalizeRow({
        ...row,
        db_id: undefined,
        week_start: weekStart.value,
        entry_round: undefined,
        id: `copy-${row.id}`,
      }))
      sourceWeek.value = latest.data.week_start
      dirty.value = true
      message.info(`${sourceWeek.value} 자료를 불러왔습니다. 저장하면 현재 주차로 등록됩니다.`)
      return
    }

    rows.value = []
    sourceWeek.value = null
    dirty.value = false
  } catch (error) {
    message.error(error.response?.data?.detail || '영업관리 데이터를 불러오지 못했습니다.')
  } finally {
    loading.value = false
  }
}

async function loadProjects() {
  const res = await executionApi.getProjects()
  projects.value = res.data || []
}

async function saveRows() {
  saving.value = true
  try {
    const payload = rows.value.map(serializeRow)
    const res = await salesApi.saveSalesManagementRows(weekStart.value, payload)
    rows.value = (res.data || []).map(normalizeRow)
    sourceWeek.value = weekStart.value
    dirty.value = false
    message.success('저장했습니다.')
  } catch (error) {
    message.error(error.response?.data?.detail || '저장 중 오류가 발생했습니다.')
  } finally {
    saving.value = false
  }
}

onMounted(loadRows)
</script>

<style scoped>
.page-wrap {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.table-card {
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.07);
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2535;
}

.dirty-alert {
  margin-bottom: 12px;
}

.week-nav {
  display: inline-flex;
  align-items: center;
  gap: 14px;
}

.week-period {
  min-width: 170px;
  text-align: center;
  color: #0f172a;
  font-weight: 700;
  white-space: nowrap;
}

.table-text-input,
.table-number-input,
.table-date-input,
.table-select {
  width: 100%;
}

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

.readonly-text-cell {
  display: block;
  min-height: 30px;
  padding: 5px 8px;
  border-radius: 4px;
  background: #fafafa;
  color: #1a2535;
  font-weight: 600;
  text-align: center;
}

:deep(.ant-table-thead > tr > th) {
  text-align: center !important;
  background: #fafafa;
}

:deep(.ant-table-tbody > tr > td) {
  padding: 6px 8px;
}

:deep(.sales-management-table .ant-input-number-input) {
  text-align: right;
}
</style>
