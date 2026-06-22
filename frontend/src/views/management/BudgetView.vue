<template>
  <div class="page-wrap">
    <a-row :gutter="16">
      <a-col :flex="1" v-for="s in statsCards" :key="s.key">
        <a-card :bordered="false" class="stat-card" :class="s.cls">
          <div class="stat-inner">
            <div>
              <div class="stat-label">{{ s.label }}</div>
              <div class="stat-value" :style="`color:${s.color}`">{{ s.value }}<span class="stat-unit">{{ s.unit }}</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-card :bordered="false" class="table-card">
      <template #title>
        <a-space size="small">
          <a-select v-model:value="year" style="width: 110px" @change="load">
            <a-select-option v-for="y in years" :key="y" :value="y">{{ y }}년</a-select-option>
          </a-select>
          <span class="card-title">부서별 예산 현황</span>
        </a-space>
      </template>
      <template #extra>
        <a-space>
          <a-select
            v-model:value="selectedDepartments"
            mode="multiple"
            class="department-select"
            placeholder="부서 선택"
            :max-tag-count="2"
            :options="departmentOptions"
            option-label-prop="shortLabel"
          >
            <template #option="{ value, label }">
              <div class="department-option" @mousedown.prevent @click.stop="toggleDepartment(value)">
                <a-checkbox :checked="selectedDepartments.includes(value)" />
                <span>{{ label }}</span>
              </div>
            </template>
          </a-select>
          <a-button type="primary" :loading="saving" @click="saveAll">저장</a-button>
        </a-space>
      </template>
      <a-table
        :columns="columns"
        :data-source="tableRows"
        :loading="loading"
        :pagination="false"
        size="middle"
        row-key="key"
        :scroll="{ x: 1720 }"
        :row-class-name="rowClassName"
        :custom-row="customRow"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'department'">
            <b>{{ record.department }}</b>
          </template>
          <template v-else-if="column.key === 'major'">
            {{ record.major }}
          </template>
          <template v-else-if="column.key === 'item'">
            <b v-if="record.isSubtotal">{{ record.item }}</b>
            <span v-else>{{ record.item }}</span>
          </template>
          <template v-else-if="MONTH_KEYS.includes(column.key)">
            <span v-if="record.isSubtotal || record.isSummary" class="num-bold">{{ fmtMoney(record[column.key]) }}</span>
            <a-input-number
              v-else
              v-model:value="record.months[column.key]"
              class="month-input"
              :min="0"
              :formatter="fmtInput"
              :parser="parseInput"
              @focus="event => clearZeroMonth(record, column.key, event)"
              @blur="restoreEmptyMonth(record, column.key)"
            />
          </template>
          <template v-else-if="column.key === 'total'">
            <span class="num-bold">{{ fmtMoney(record.total) }}</span>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { managementApi, masterApi } from '@/api'
import { flattenDepartmentTree } from '@/utils/departments'

const REQ_MARKER = '\n---예산월별요구사항---\n'
const BUDGET_ITEMS = [
  { major: '접대비', item: '법인카드', category: '접대비-법인카드', legacyCategory: '법인카드', editable: true },
  { major: '접대비', item: '계산서', category: '접대비-계산서', legacyCategory: '계산서', editable: true },
  { major: '접대비', item: '경조사비', category: '접대비-경조사비', legacyCategory: '경조사비', editable: true },
  { major: '접대비', item: '기타', category: '접대비-기타', legacyCategory: '기타', editable: true },
  { major: '접대비', item: '소계', category: '접대비-소계', editable: false, isSubtotal: true },
  { major: '식대', item: '식대', category: '식대', editable: true },
]
const MONTH_INPUTS = Array.from({ length: 12 }, (_, i) => ({ key: `m${i + 1}`, label: `${i + 1}월` }))
const MONTH_KEYS = MONTH_INPUTS.map(m => m.key)

const now = new Date()
const years = Array.from({ length: 5 }, (_, i) => now.getFullYear() - 1 + i)
const year = ref(now.getFullYear())
const loading = ref(false)
const saving = ref(false)
const budgets = ref([])
const departments = ref([])
const selectedDepartments = ref([])

const emptyMonths = () => Object.fromEntries(MONTH_KEYS.map(key => [key, 0]))
const fmtMoney = value => Number(value || 0).toLocaleString()
const fmtInput = value => {
  if (value === null || value === undefined || value === '') return ''
  if (Number(value) === 0) return ''
  return Number(value).toLocaleString()
}
const parseInput = value => String(value || '').replace(/,/g, '')

function clearZeroMonth(record, key, event) {
  if (Number(record.months[key]) !== 0) return
  record.months[key] = null
  const input = event?.target
  if (input) {
    input.value = ''
    requestAnimationFrame(() => input.select?.())
  }
}

function restoreEmptyMonth(record, key) {
  if (record.months[key] === null || record.months[key] === undefined || record.months[key] === '') {
    record.months[key] = 0
  }
}

function toggleDepartment(value) {
  const selected = new Set(selectedDepartments.value)
  if (selected.has(value)) selected.delete(value)
  else selected.add(value)
  selectedDepartments.value = [...selected]
}

const departmentOptions = computed(() =>
  flattenDepartmentTree(departments.value)
    .filter(dept => ['team', 'part', 'common', 'office', 'business', 'division'].includes(dept.dept_type))
    .map(dept => ({ value: dept.name, label: dept.path, shortLabel: dept.name }))
)

const budgetMap = computed(() => {
  const map = new Map()
  budgets.value.forEach(row => {
    map.set(`${row.department}::${row.category}`, row)
  })
  return map
})

const tableRows = computed(() => {
  const rows = []
  selectedDepartments.value.forEach(department => {
    const editableRows = BUDGET_ITEMS.filter(item => item.editable).map((item, index) => {
      const saved = findSavedBudget(department, item)
      const months = saved ? { ...saved.months } : emptyMonths()
      return {
        key: `${department}-${item.category}`,
        id: saved?.id,
        department,
        major: item.major,
        item: item.item,
        category: item.category,
        months,
        total: sumMonths(months),
        deptRowSpan: index === 0 ? BUDGET_ITEMS.length : 0,
        majorRowSpan: index === 0 ? 5 : index === 4 ? 1 : 0,
        isSubtotal: false,
      }
    })

    const subtotalMonths = emptyMonths()
    editableRows.slice(0, 4).forEach(row => {
      MONTH_KEYS.forEach(key => { subtotalMonths[key] += Number(row.months[key]) || 0 })
    })

    rows.push(...editableRows.slice(0, 4))
    rows.push({
      key: `${department}-subtotal`,
      department,
      major: '접대비',
      item: '소계',
      category: '접대비-소계',
      months: subtotalMonths,
      ...subtotalMonths,
      total: sumMonths(subtotalMonths),
      deptRowSpan: 0,
      majorRowSpan: 0,
      isSubtotal: true,
    })
    rows.push({
      ...editableRows[4],
      deptRowSpan: 0,
      majorRowSpan: 1,
    })
  })
  const bodyRows = rows.map(row => {
    if (row.isSubtotal) return row
    const total = sumMonths(row.months)
    return { ...row, total }
  })
  return [...bodyRows, ...summaryRows(bodyRows)]
})

const statsCards = computed(() => {
  const rows = tableRows.value
  const entertainment = rows.filter(row => row.isSubtotal).reduce((sum, row) => sum + row.total, 0)
  const meal = rows.filter(row => row.category === '식대').reduce((sum, row) => sum + row.total, 0)
  const total = entertainment + meal
  return [
    { key: 'entertainment', label: '접대비', value: fmtMoney(entertainment), unit: '원', color: '#1677ff', cls: 'stat-blue' },
    { key: 'meal', label: '식대', value: fmtMoney(meal), unit: '원', color: '#fa8c16', cls: 'stat-orange' },
    { key: 'total', label: '전체 합계', value: fmtMoney(total), unit: '원', color: '#1a2535', cls: '' },
    { key: 'dept', label: '선택 부서', value: selectedDepartments.value.length, unit: '개', color: '#722ed1', cls: 'stat-purple' },
  ]
})

const columns = [
  { title: '부서', key: 'department', width: 180, align: 'center', fixed: 'left', customCell: row => ({ rowSpan: row.deptRowSpan }) },
  { title: '구분', key: 'major', width: 100, align: 'center', fixed: 'left', customCell: row => ({ rowSpan: row.majorRowSpan }) },
  { title: '항목', key: 'item', width: 120, align: 'center', fixed: 'left' },
  ...MONTH_INPUTS.map(month => ({ title: month.label, key: month.key, width: 105, align: 'right' })),
  { title: '합계', key: 'total', width: 130, align: 'right' },
]

function splitNotes(notes) {
  const raw = notes || ''
  const idx = raw.indexOf(REQ_MARKER)
  if (idx < 0) return { memo: raw, req: {} }
  try { return { memo: raw.slice(0, idx), req: JSON.parse(raw.slice(idx + REQ_MARKER.length)) || {} } }
  catch { return { memo: raw, req: {} } }
}

function spreadQuarter(q) {
  const value = Number(q) || 0
  const base = Math.floor(value / 3)
  const rest = value - base * 3
  return [base + rest, base, base]
}

function normalizeBudget(row) {
  const { memo, req } = splitNotes(row.notes)
  const months = emptyMonths()
  if (req.months) {
    MONTH_KEYS.forEach(key => { months[key] = Number(req.months[key]) || 0 })
  } else {
    const values = [...spreadQuarter(row.q1), ...spreadQuarter(row.q2), ...spreadQuarter(row.q3), ...spreadQuarter(row.q4)]
    MONTH_KEYS.forEach((key, index) => { months[key] = values[index] || 0 })
  }
  return {
    ...row,
    months,
    notes: memo,
  }
}

function sumMonths(months) {
  return MONTH_KEYS.reduce((sum, key) => sum + (Number(months[key]) || 0), 0)
}

function summaryRows(rows) {
  const entertainmentMonths = emptyMonths()
  const mealMonths = emptyMonths()
  rows.forEach(row => {
    const target = row.isSubtotal ? entertainmentMonths : row.category === '식대' ? mealMonths : null
    if (!target) return
    MONTH_KEYS.forEach(key => { target[key] += Number(row.months?.[key] || row[key]) || 0 })
  })
  return [
    {
      key: 'summary-entertainment',
      department: '합계(접대비)',
      major: '',
      item: '',
      months: entertainmentMonths,
      ...entertainmentMonths,
      total: sumMonths(entertainmentMonths),
      deptRowSpan: 1,
      majorRowSpan: 1,
      isSummary: true,
    },
    {
      key: 'summary-meal',
      department: '합계(식대)',
      major: '',
      item: '',
      months: mealMonths,
      ...mealMonths,
      total: sumMonths(mealMonths),
      deptRowSpan: 1,
      majorRowSpan: 1,
      isSummary: true,
    },
  ]
}

function findSavedBudget(department, item) {
  return budgetMap.value.get(`${department}::${item.category}`) ||
    (item.legacyCategory ? budgetMap.value.get(`${department}::${item.legacyCategory}`) : null)
}

function buildNotes(row) {
  return `${row.notes || ''}${REQ_MARKER}${JSON.stringify({ major_category: row.major, months: row.months })}`
}

function toPayload(row) {
  return {
    budget_year: year.value,
    department: row.department,
    category: row.category,
    q1: MONTH_KEYS.slice(0, 3).reduce((sum, key) => sum + (Number(row.months[key]) || 0), 0),
    q2: MONTH_KEYS.slice(3, 6).reduce((sum, key) => sum + (Number(row.months[key]) || 0), 0),
    q3: MONTH_KEYS.slice(6, 9).reduce((sum, key) => sum + (Number(row.months[key]) || 0), 0),
    q4: MONTH_KEYS.slice(9, 12).reduce((sum, key) => sum + (Number(row.months[key]) || 0), 0),
    status: '작성중',
    notes: buildNotes(row),
  }
}

function rowClassName(row) {
  if (row.isSummary) return 'summary-row'
  return row.isSubtotal ? 'subtotal-row' : ''
}

function customRow(record) {
  return record.isSummary ? { class: 'summary-fixed-row' } : {}
}

async function load() {
  loading.value = true
  try {
    const [budgetRes, deptRes] = await Promise.all([
      managementApi.getDeptBudgets(year.value),
      masterApi.getDepartments({ org_year: year.value, include_inactive: false, tree: true }),
    ])
    budgets.value = budgetRes.data.map(normalizeBudget)
    departments.value = deptRes.data || []

    const valuedDepartments = [...new Set(
      budgets.value
        .filter(row => sumMonths(row.months) > 0)
        .map(row => row.department)
    )]
    const validDepartmentNames = new Set(departmentOptions.value.map(option => option.value))
    selectedDepartments.value = valuedDepartments.filter(name => validDepartmentNames.has(name))
  } finally {
    loading.value = false
  }
}

async function saveAll() {
  const rows = tableRows.value.filter(row => !row.isSubtotal && !row.isSummary)
  if (!rows.length) {
    message.warning('저장할 부서를 선택하세요.')
    return
  }
  try {
    saving.value = true
    await Promise.all(rows.map(row => managementApi.upsertDeptBudget(toPayload(row))))
    message.success('부서별 예산이 저장되었습니다.')
    await load()
  } catch (e) {
    message.error(e.response?.data?.detail || '저장 중 오류가 발생했습니다.')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.department-select { width: 320px; }
.department-option {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  cursor: pointer;
}
.stat-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue { border-left-color: #1677ff; }
.stat-orange { border-left-color: #fa8c16; }
.stat-purple { border-left-color: #722ed1; }
.stat-inner { display: flex; align-items: center; gap: 14px; }
.stat-label { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value { font-size: 22px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit { font-size: 11px; font-weight: 400; margin-left: 2px; color: #8c8c8c; }
.table-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size: 15px; font-weight: 600; color: #1a2535; }
.month-input { width: 96px; }
.num-bold { font-weight: 700; }
:deep(.subtotal-row td) { background: #fafafa; font-weight: 600; }
:deep(.summary-row td) {
  background: #f0f5ff;
  border-top: 2px solid #d6e4ff;
  font-weight: 700;
}
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
:deep(.ant-table-cell) { white-space: nowrap; }
</style>
