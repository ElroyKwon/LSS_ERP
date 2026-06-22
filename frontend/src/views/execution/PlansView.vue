<template>
  <div class="page-wrap">
    <a-card :bordered="false" class="selector-card">
      <a-space size="middle" wrap>
        <span class="sel-label">프로젝트</span>
        <a-select
          v-model:value="selectedProjectId"
          show-search
          allow-clear
          placeholder="프로젝트 선택"
          style="width: 360px"
          :options="projectOptions"
          option-filter-prop="label"
          @change="loadPlans"
        />
        <span class="sel-label">기준연도</span>
        <a-select v-model:value="selectedYear" style="width: 110px" @change="loadPlans">
          <a-select-option v-for="y in years" :key="y" :value="y">{{ y }}년</a-select-option>
        </a-select>
        <a-tag color="blue">단위: 원 / VAT 별도</a-tag>
      </a-space>

      <div v-if="selectedProject" class="proj-info">
        <a-tag :color="statusColor[selectedProject.status] || 'default'">{{ selectedProject.status }}</a-tag>
        <b>{{ selectedProject.project_name }}</b>
        <span>{{ selectedProject.client_name || '-' }}</span>
        <span>계약금액 <b>{{ money(selectedProject.contract_amount) }}</b></span>
        <span v-if="selectedProject.contract_start || selectedProject.contract_end">
          계약기간 {{ selectedProject.contract_start || '-' }} ~ {{ selectedProject.contract_end || '-' }}
        </span>
      </div>
    </a-card>

    <a-row :gutter="16">
      <a-col :flex="1" v-for="s in summaryCards" :key="s.key">
        <a-card :bordered="false" class="stat-card" :class="s.cls">
          <div class="stat-inner">
            <div class="stat-icon" :class="s.iconCls">
              <component :is="s.icon" />
            </div>
            <div>
              <div class="stat-label">{{ s.label }}</div>
              <div class="stat-value" :style="`color:${s.color}`">
                {{ s.value }}<span class="stat-unit">{{ s.unit }}</span>
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-card :bordered="false" class="table-card">
      <template #title>
        <span class="card-title">매출 투입 계획</span>
      </template>
      <template #extra>
        <a-space>
          <a-tag v-if="dirtyCount > 0" color="orange">{{ dirtyCount }}개월 변경</a-tag>
          <a-button size="small" @click="resetPlans" :disabled="saving || dirtyCount === 0">되돌리기</a-button>
          <a-button type="primary" size="small" :loading="saving" :disabled="!selectedProjectId || dirtyCount === 0" @click="savePlans">
            <template #icon><SaveOutlined /></template>
            저장
          </a-button>
        </a-space>
      </template>

      <div class="grid-help">
        엑셀 양식의 A~G 고정 열을 화면에서도 왼쪽에 고정했습니다. 월별 계획 값은 흰색 입력칸에서 수정하고,
        누계·수주잔·원가율·합계는 자동 계산됩니다.
      </div>
      <a-alert
        v-if="!selectedProjectId"
        type="info"
        show-icon
        class="select-alert"
        message="프로젝트를 선택하면 월별 계획 입력과 저장이 활성화됩니다."
      />

      <section v-for="section in tableSections" :key="section.key" class="plan-section">
        <div class="section-title">
          <span>{{ section.title }}</span>
          <a-button
            v-if="section.key === 'material'"
            size="small"
            class="section-add-btn"
            @click="addMaterialVendorRow"
          >
            거래처 추가
          </a-button>
        </div>
        <a-table
          :columns="getPlanColumns(section.key)"
          :data-source="section.rows"
          :loading="planLoading"
          :pagination="false"
          row-key="key"
          size="small"
          :scroll="{ x: tableScrollX }"
          :row-class-name="rowClassName"
          bordered
        >
          <template #headerCell="{ column }">
            <template v-if="column.changeGroup">
              <div class="header-change-title">
                <span>{{ column.title }}</span>
                <a-button
                  v-if="column.changeGroupIndex === 0"
                  size="small"
                  class="header-change-add"
                  title="변경 열 추가"
                  @click="addChangeColumn(column.sectionKey)"
                >
                  추가
                </a-button>
              </div>
            </template>
            <template v-else-if="column.key === 'contract'">
              <div v-if="column.showContractDate" class="header-input-wrap">
                <a-date-picker
                  v-model:value="contractDate"
                  size="small"
                  value-format="YYYY-MM-DD"
                  placeholder="계약일"
                  class="header-date"
                />
              </div>
              <span v-else>{{ column.title }}</span>
            </template>
            <template v-else-if="column.changeIndex !== undefined">
              <div class="header-change-cell">
                <a-input
                  v-model:value="changeColumnGroups[column.sectionKey][column.changeIndex].label"
                  size="small"
                  :placeholder="column.placeholder || 'N차(20xx,xx,xx)'"
                  class="header-change-input"
                />
              </div>
            </template>
            <template v-else>
              {{ column.title }}
            </template>
          </template>

          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'label'">
              <a-input
                v-if="record.rowType === 'vendor'"
                :value="getMaterialVendorRow(record.vendorId)?.vendorName"
                size="small"
                placeholder="거래처명"
                class="vendor-name-input"
                @change="(event) => setMaterialVendorName(record.vendorId, event.target.value)"
              />
              <span v-else :class="['label-cell', { strong: record.strong }]">{{ record.label }}</span>
            </template>

            <template v-else-if="column.key === 'item'">
              <a-select
                v-if="record.rowType === 'vendor'"
                :value="getMaterialVendorRow(record.vendorId)?.costType"
                size="small"
                class="vendor-type-select"
                @change="(value) => setMaterialVendorCostType(record.vendorId, value)"
              >
                <a-select-option value="subcontract_plan">외주</a-select-option>
                <a-select-option value="material_plan">자재</a-select-option>
              </a-select>
              <span v-else>{{ record.item }}</span>
            </template>

            <template v-else-if="column.key === 'contract'">
              <span class="num-cell">{{ record.contract ? money(record.contract) : '' }}</span>
            </template>

            <template v-else-if="column.key === 'type'">
              <a-select
                v-if="record.rowType === 'vendor'"
                :value="getMaterialVendorRow(record.vendorId)?.costType"
                size="small"
                class="vendor-type-select"
                @change="(value) => setMaterialVendorCostType(record.vendorId, value)"
              >
                <a-select-option value="subcontract_plan">외주</a-select-option>
                <a-select-option value="material_plan">자재</a-select-option>
              </a-select>
              <a-tag v-else-if="record.type" :color="typeColor(record.type)">{{ record.type }}</a-tag>
            </template>

            <template v-else-if="column.key === 'prev'">
              <span class="num-cell">{{ formatCell(record, column.key) }}</span>
            </template>

            <template v-else-if="isMonthColumn(column)">
              <a-input-number
                v-if="record.rowType === 'vendor'"
                :value="getMaterialVendorMonthValue(record.vendorId, column.year, column.month)"
                :min="0"
                size="small"
                class="month-input"
                :formatter="formatInput"
                :parser="parseInput"
                @change="(value) => setMaterialVendorMonthValue(record.vendorId, column.year, column.month, value)"
              />
              <a-input-number
                v-else-if="record.sourceKey"
                :value="getEditableValue(record.sourceKey, column.year, column.month)"
                :min="0"
                size="small"
                class="month-input"
                :formatter="formatInput"
                :parser="parseInput"
                @change="(value) => setEditableValue(record.sourceKey, column.year, column.month, value)"
              />
              <span v-else class="num-cell" :class="{ percent: record.format === 'percent' }">
                {{ formatCell(record, column.key) }}
              </span>
            </template>

            <template v-else-if="['total', 'remain', 'rate'].includes(column.key)">
              <span class="num-cell" :class="{ percent: column.key === 'rate' || record.format === 'percent', warn: column.key === 'remain' && getCellValue(record, column.key) < 0 }">
                {{ formatCell(record, column.key) }}
              </span>
            </template>
          </template>
        </a-table>
      </section>
    </a-card>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  SaveOutlined,
  RiseOutlined,
  FallOutlined,
  CalculatorOutlined,
  PercentageOutlined,
} from '@ant-design/icons-vue'
import { executionApi } from '@/api'

const now = new Date()
const years = Array.from({ length: 5 }, (_, i) => now.getFullYear() - 1 + i)
const planFields = ['revenue_plan', 'material_plan', 'subcontract_plan', 'labor_plan', 'expense_plan']
const planMetaVersion = 4
const planSectionKeys = ['revenue', 'material', 'labor']

const projects = ref([])
const selectedProjectId = ref(null)
const selectedYear = ref(now.getFullYear())
const planLoading = ref(false)
const saving = ref(false)
const planData = ref(createEmptyPlanDataForYears([selectedYear.value - 1, selectedYear.value]))
const prevCumulative = ref(createEmptyCumulative())
const originalSnapshot = ref('')
const dirtyPlanKeys = ref(new Set())
const contractDate = ref(null)
const changeColumnGroups = ref(defaultChangeColumnGroups())
const materialVendorRows = ref([])
const planMetaLoading = ref(false)

const statusColor = { 미진행: 'orange', 진행중: 'blue', 완료: 'green' }

const cumulativeYear = computed(() => selectedYear.value - 2)
const previousPlanYear = computed(() => selectedYear.value - 1)
const currentPlanYear = computed(() => selectedYear.value)
const planYears = computed(() => [previousPlanYear.value, currentPlanYear.value])
const monthColumns = computed(() =>
  planYears.value.flatMap(year =>
    Array.from({ length: 12 }, (_, i) => ({
      key: monthKey(year, i + 1),
      year,
      month: i + 1,
    }))
  )
)
const tableScrollX = computed(() => 980 + (maxChangeColumnCount.value * 150) + 130 + (monthColumns.value.length * 110) + 360)
const planMetaStorageKey = computed(() =>
  selectedProjectId.value ? `execution-plan-meta:${selectedProjectId.value}:${selectedYear.value}` : null
)

const projectOptions = computed(() =>
  projects.value.map(p => ({
    value: p.id,
    label: `[${p.project_no || '-'}] ${p.project_name}`,
  }))
)

const selectedProject = computed(() =>
  projects.value.find(p => p.id === selectedProjectId.value) || null
)

const dirtyCount = computed(() => dirtyPlanKeys.value.size)
const maxChangeColumnCount = computed(() =>
  Math.max(...planSectionKeys.map(key => changeColumnGroups.value[key]?.length || 1))
)

const totals = computed(() => {
  const result = createEmptyCumulative()
  Object.values(planData.value[currentPlanYear.value] || {}).forEach(row => {
    planFields.forEach(field => { result[field] += Number(row[field] || 0) })
  })
  return result
})

const costTotal = computed(() =>
  totals.value.material_plan + totals.value.subcontract_plan + totals.value.labor_plan + totals.value.expense_plan
)

const summaryCards = computed(() => {
  const revenue = totals.value.revenue_plan
  const margin = revenue - costTotal.value
  const marginRate = revenue > 0 ? (margin / revenue * 100) : 0
  return [
    { key: 'revenue', label: '연간 매출 계획', value: compactMoney(revenue), unit: '원', color: '#1677ff', cls: 'stat-blue', iconCls: 'icon-blue', icon: RiseOutlined },
    { key: 'cost', label: '연간 투입 계획', value: compactMoney(costTotal.value), unit: '원', color: '#fa8c16', cls: 'stat-orange', iconCls: 'icon-orange', icon: FallOutlined },
    { key: 'margin', label: '계획 이익', value: compactMoney(margin), unit: '원', color: '#52c41a', cls: 'stat-green', iconCls: 'icon-green', icon: CalculatorOutlined },
    { key: 'rate', label: '계획 이익률', value: marginRate.toFixed(1), unit: '%', color: '#722ed1', cls: 'stat-purple', iconCls: 'icon-purple', icon: PercentageOutlined },
  ]
})

function getPlanColumns(sectionKey) {
  const changeColumns = changeColumnGroups.value[sectionKey] || defaultChangeColumns()
  const detailSection = sectionKey === 'material' || sectionKey === 'labor'
  return [
  { title: detailSection ? '업체명' : '내역', key: 'label', dataIndex: 'label', width: detailSection ? 160 : 130, align: 'center', fixed: 'left' },
  ...(!detailSection ? [{ title: '항목', key: 'item', dataIndex: 'item', width: 90, align: 'center', fixed: 'left' }] : []),
  {
    title: '계약액',
    fixed: 'left',
    children: [
      {
        title: detailSection ? '' : '계약일',
        key: 'contract',
        dataIndex: 'contract',
        width: detailSection ? 128 : 150,
        align: 'right',
        fixed: 'left',
        sectionKey,
        showContractDate: !detailSection,
      },
    ],
  },
  ...changeColumns.map((change, index) => ({
    title: getChangeGroupTitle(sectionKey, index),
    fixed: 'left',
    sectionKey,
    changeGroup: true,
    changeGroupIndex: index,
    children: [
      {
        title: change.label,
        key: `change${index + 1}`,
        dataIndex: `change${index + 1}`,
        width: 150,
        align: 'center',
        fixed: 'left',
        sectionKey,
        changeIndex: index,
        placeholder: getChangePlaceholder(sectionKey, index),
      },
    ],
  })),
  { title: '구분', key: 'type', dataIndex: 'type', width: 110, align: 'center', fixed: 'left' },
  {
    title: `${cumulativeYear.value}년`,
    children: [
      { title: '12월까지 누계', key: 'prev', dataIndex: 'prev', width: 130, align: 'right' },
    ],
  },
  {
    title: `${previousPlanYear.value}년`,
    children: Array.from({ length: 12 }, (_, i) => ({
      title: `${i + 1}월`,
      key: monthKey(previousPlanYear.value, i + 1),
      dataIndex: monthKey(previousPlanYear.value, i + 1),
      year: previousPlanYear.value,
      month: i + 1,
      width: 110,
      align: 'right',
    })),
  },
  {
    title: `${currentPlanYear.value}년`,
    children: Array.from({ length: 12 }, (_, i) => ({
      title: `${i + 1}월`,
      key: monthKey(currentPlanYear.value, i + 1),
      dataIndex: monthKey(currentPlanYear.value, i + 1),
      year: currentPlanYear.value,
      month: i + 1,
      width: 110,
      align: 'right',
    })),
  },
  {
    title: '집계',
    children: [
      { title: '합계', key: 'total', dataIndex: 'total', width: 130, align: 'right' },
      { title: '미 실행', key: 'remain', dataIndex: 'remain', width: 130, align: 'right' },
      { title: '진행율', key: 'rate', dataIndex: 'rate', width: 100, align: 'center' },
    ],
  },
  ]
}

function getChangeGroupTitle(sectionKey, index) {
  if (sectionKey === 'material' && index >= 2) return '정산'
  return '변경'
}

function getChangePlaceholder(sectionKey, index) {
  if ((sectionKey === 'material' || sectionKey === 'labor') && index === 0) return '준공예정'
  return 'N차(20xx,xx,xx)'
}

const revenuePlanRows = computed(() => {
  const contract = Number(selectedProject.value?.contract_amount || 0)
  return [
    calcRow('invoice', '수주업체명', '', contract, '매출계산서 발행', timelineValue('revenue_plan'), prevCumulative.value.revenue_plan),
    metricRow('revenue', '', '', contract, '매출', 'revenue_plan', { strong: true }),
    calcRow('revenue-cumulative', '', '', contract, '누계', timelineCumulative('revenue_plan'), prevCumulative.value.revenue_plan, { strong: true }),
    calcRow('order-balance', '수주잔', '', contract, '계산서', timelineBalance('revenue_plan', contract), contract - prevCumulative.value.revenue_plan),
    calcRow('progress-rate', '', '', contract, '진행율', timelineRate('revenue_plan', contract), rate(prevCumulative.value.revenue_plan, contract), { format: 'percent' }),
    calcRow('subcontract-overview', '예정원가', '외주비', null, '외주', timelineValue('subcontract_plan'), prevCumulative.value.subcontract_plan),
    calcRow('material-overview', '', '자재비', null, '자재', timelineValue('material_plan'), prevCumulative.value.material_plan),
    calcRow('labor-overview', '', '인건비', null, '인건비', timelineValue('labor_plan'), prevCumulative.value.labor_plan),
    calcRow('expense-overview', '', '경비', null, '직접경비', timelineValue('expense_plan'), prevCumulative.value.expense_plan),
    calcRow('cost-total', '매출원가 합계', '', null, '합계', timelineCostTotal(), prevCostTotal(), { strong: true }),
    calcRow('cost-cumulative', '매출원가 누계', '', null, '누계', timelineCostCumulative(), prevCostTotal(), { strong: true }),
    calcRow('cost-rate', '원가율', '', contract, '비율', timelineCostRate(contract), rate(prevCostTotal(), contract), { format: 'percent' }),
  ]
})

const materialPlanRows = computed(() => [
    calcRow('material-sub-total', '합계', '', null, '합계', timelineMaterialSubTotal(), prevCumulative.value.material_plan + prevCumulative.value.subcontract_plan, { strong: true }),
    metricRow('subcontract-source', '외주', '', null, '외주', 'subcontract_plan'),
    metricRow('material-source', '자재', '', null, '자재', 'material_plan'),
    ...materialVendorRows.value.map(row => materialVendorPlanRow(row)),
])

const laborPlanRows = computed(() => [
    calcRow('labor-expense-total', '합계', '', null, '개별비', timelineLaborExpenseTotal(), prevCumulative.value.labor_plan + prevCumulative.value.expense_plan, { strong: true }),
    metricRow('labor-source', '인건비', '', null, '인건비', 'labor_plan'),
    metricRow('expense-source', '직접경비', '', null, '직접경비', 'expense_plan'),
])

const tableSections = computed(() => [
  { key: 'revenue', title: '매출 계획 / 예정원가', rows: revenuePlanRows.value },
  { key: 'material', title: '자재비 + 외주비', rows: materialPlanRows.value },
  { key: 'labor', title: '인건비 + 경비', rows: laborPlanRows.value },
])

function monthKey(year, month) {
  return `y${year}m${month}`
}

function createEmptyYearData() {
  return Object.fromEntries(Array.from({ length: 12 }, (_, i) => [
    i + 1,
    {
      revenue_plan: 0,
      material_plan: 0,
      subcontract_plan: 0,
      labor_plan: 0,
      expense_plan: 0,
      notes: '',
    },
  ]))
}

function createEmptyPlanDataForYears(yearList = [selectedYear.value - 1, selectedYear.value]) {
  return Object.fromEntries(yearList.map(year => [year, createEmptyYearData()]))
}

function createEmptyCumulative() {
  return {
    revenue_plan: 0,
    material_plan: 0,
    subcontract_plan: 0,
    labor_plan: 0,
    expense_plan: 0,
  }
}

function metricRow(key, label, item, contract, type, sourceKey, options = {}) {
  const prev = Number(prevCumulative.value[sourceKey] || 0)
  const total = prev + timelineValue(sourceKey).reduce((sum, value) => sum + value, 0)
  const row = { key, label, item, contract, type, sourceKey, rowType: 'metric', prev, total, ...options }
  if (contract) {
    row.remain = contract - total
    row.rate = rate(total, contract)
  }
  return row
}

function calcRow(key, label, item, contract, type, months, prev, options = {}) {
  const row = { key, label, item, contract, type, prev, rowType: 'calc', ...options }
  monthColumns.value.forEach((column, index) => { row[column.key] = months[index] || 0 })
  row.total = (prev || 0) + monthColumns.value.reduce((sum, column) => sum + Number(row[column.key] || 0), 0)
  if (contract) {
    row.remain = contract - row.total
    row.rate = rate(row.total, contract)
  }
  return row
}

function materialVendorPlanRow(vendor) {
  const row = {
    key: `material-vendor-${vendor.id}`,
    label: vendor.vendorName || '',
    item: '거래처',
    type: vendor.costType === 'material_plan' ? '자재' : '외주',
    prev: null,
    rowType: 'vendor',
    vendorId: vendor.id,
    vendorCostType: vendor.costType,
  }
  monthColumns.value.forEach(column => {
    row[column.key] = getMaterialVendorMonthValue(vendor.id, column.year, column.month)
  })
  row.total = monthColumns.value.reduce((sum, column) => sum + Number(row[column.key] || 0), 0)
  return row
}

function yearValue(field, year) {
  return Array.from({ length: 12 }, (_, i) => Number(planData.value[year]?.[i + 1]?.[field] || 0))
}

function timelineValue(field) {
  return planYears.value.flatMap(year => yearValue(field, year))
}

function timelineCumulative(field) {
  let sum = Number(prevCumulative.value[field] || 0)
  return timelineValue(field).map(v => {
    sum += v
    return sum
  })
}

function timelineBalance(field, contract) {
  return timelineCumulative(field).map(v => Number(contract || 0) - v)
}

function timelineRate(field, contract) {
  return timelineCumulative(field).map(v => rate(v, contract))
}

function timelineCostTotal() {
  return monthColumns.value.map(({ year, month }) => {
    const row = planData.value[year]?.[month] || {}
    return Number(row.material_plan || 0) + Number(row.subcontract_plan || 0) + Number(row.labor_plan || 0) + Number(row.expense_plan || 0)
  })
}

function timelineCostCumulative() {
  let sum = prevCostTotal()
  return timelineCostTotal().map(v => {
    sum += v
    return sum
  })
}

function timelineCostRate(contract) {
  return timelineCostCumulative().map(v => rate(v, contract))
}

function timelineMaterialSubTotal() {
  return monthColumns.value.map(({ year, month }) => {
    const row = planData.value[year]?.[month] || {}
    return Number(row.material_plan || 0) + Number(row.subcontract_plan || 0)
  })
}

function timelineLaborExpenseTotal() {
  return monthColumns.value.map(({ year, month }) => {
    const row = planData.value[year]?.[month] || {}
    return Number(row.labor_plan || 0) + Number(row.expense_plan || 0)
  })
}

function prevCostTotal() {
  return prevCumulative.value.material_plan + prevCumulative.value.subcontract_plan + prevCumulative.value.labor_plan + prevCumulative.value.expense_plan
}

function rate(value, base) {
  return Number(base || 0) > 0 ? Number(value || 0) / Number(base) * 100 : 0
}

function getEditableValue(field, year, month) {
  return Number(planData.value[year]?.[month]?.[field] || 0)
}

function setEditableValue(field, year, month, value) {
  ensureYearData(year)
  planData.value[year][month][field] = Number(value || 0)
  dirtyPlanKeys.value = findDirtyPlanKeys()
}

function getCellValue(record, key) {
  return Number(record[key] || 0)
}

function formatCell(record, key) {
  const value = getCellValue(record, key)
  if (record.rowType === 'section') return ''
  if (record.format === 'percent' || key === 'rate') return value ? `${value.toFixed(1)}%` : '-'
  return value ? money(value) : '-'
}

function isMonthColumn(column) {
  return Boolean(column.year && column.month)
}

function addChangeColumn(sectionKey) {
  if (!changeColumnGroups.value[sectionKey]) {
    changeColumnGroups.value[sectionKey] = defaultChangeColumns()
  }
  changeColumnGroups.value[sectionKey].push({ label: '' })
}

function addMaterialVendorRow() {
  materialVendorRows.value.push({
    id: `vendor-${Date.now()}-${materialVendorRows.value.length + 1}`,
    vendorName: '',
    costType: 'subcontract_plan',
    values: {},
  })
}

function getMaterialVendorRow(id) {
  return materialVendorRows.value.find(row => row.id === id)
}

function setMaterialVendorName(id, value) {
  const row = getMaterialVendorRow(id)
  if (row) row.vendorName = value
}

function setMaterialVendorCostType(id, value) {
  const row = getMaterialVendorRow(id)
  if (row) row.costType = value
}

function getMaterialVendorMonthValue(id, year, month) {
  const row = getMaterialVendorRow(id)
  return Number(row?.values?.[year]?.[month] || 0)
}

function setMaterialVendorMonthValue(id, year, month, value) {
  const row = getMaterialVendorRow(id)
  if (!row) return
  if (!row.values) row.values = {}
  if (!row.values[year]) row.values[year] = {}
  row.values[year][month] = Number(value || 0)
}

function resetPlanMeta() {
  contractDate.value = null
  changeColumnGroups.value = defaultChangeColumnGroups()
  materialVendorRows.value = []
}

function loadLegacyPlanMeta() {
  if (!planMetaStorageKey.value) {
    return null
  }
  try {
    const raw = localStorage.getItem(planMetaStorageKey.value)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function applyPlanMeta(meta = {}) {
  contractDate.value = meta.contractDate || null
  changeColumnGroups.value = meta.version === planMetaVersion
    ? normalizeChangeColumnGroups(meta.changeColumnGroups)
    : defaultChangeColumnGroups()
  materialVendorRows.value = meta.version === planMetaVersion
    ? normalizeMaterialVendorRows(meta.materialVendorRows)
    : []
}

async function loadPlanMeta() {
  if (!selectedProjectId.value) {
    resetPlanMeta()
    return
  }
  planMetaLoading.value = true
  try {
    const res = await executionApi.getProjectPlanMeta(selectedProjectId.value, selectedYear.value)
    let meta = res.data || {}
    const legacy = loadLegacyPlanMeta()
    if (!meta.exists && legacy) {
      meta = legacy
      applyPlanMeta(meta)
      await savePlanMeta(true)
      localStorage.removeItem(planMetaStorageKey.value)
      return
    }
    applyPlanMeta(meta)
  } catch (e) {
    resetPlanMeta()
    message.error(e.response?.data?.detail || '매출 투입 계획 설정 조회 중 오류가 발생했습니다.')
  } finally {
    planMetaLoading.value = false
  }
}

async function savePlanMeta(force = false) {
  if (!selectedProjectId.value || (!force && planMetaLoading.value)) return
  await executionApi.saveProjectPlanMeta({
    project_id: selectedProjectId.value,
    plan_year: selectedYear.value,
    version: planMetaVersion,
    contractDate: contractDate.value,
    changeColumnGroups: changeColumnGroups.value,
    materialVendorRows: materialVendorRows.value,
  })
}

function defaultChangeColumns() {
  return [
    { label: '' },
  ]
}

function defaultChangeColumnGroups() {
  return Object.fromEntries(planSectionKeys.map(key => [key, defaultChangeColumns()]))
}

function normalizeChangeColumnGroups(groups) {
  const defaults = defaultChangeColumnGroups()
  if (!groups || typeof groups !== 'object') return defaults
  planSectionKeys.forEach(key => {
    if (Array.isArray(groups[key]) && groups[key].length > 0) {
      defaults[key] = groups[key]
    }
  })
  return defaults
}

function normalizeMaterialVendorRows(rows) {
  if (!Array.isArray(rows)) return []
  return rows.map((row, index) => ({
    id: row.id || `vendor-restored-${index + 1}`,
    vendorName: row.vendorName || '',
    costType: ['material_plan', 'subcontract_plan'].includes(row.costType) ? row.costType : 'subcontract_plan',
    values: row.values || {},
  }))
}

function ensureYearData(year) {
  if (!planData.value[year]) planData.value[year] = createEmptyYearData()
}

function formatInput(value) {
  return value ? `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : ''
}

function parseInput(value) {
  return value ? Number(`${value}`.replace(/,/g, '')) : 0
}

function money(value) {
  return Number(value || 0).toLocaleString()
}

function compactMoney(value) {
  const n = Number(value || 0)
  if (Math.abs(n) >= 100000000) return `${(n / 100000000).toFixed(1)}억`
  if (Math.abs(n) >= 10000) return `${Math.round(n / 10000).toLocaleString()}만`
  return n.toLocaleString()
}

function typeColor(type) {
  if (['매출', '매출계산서 발행'].includes(type)) return 'blue'
  if (['외주', '자재', '직접경비', '개별비'].includes(type)) return 'orange'
  if (['인건비'].includes(type)) return 'purple'
  if (['합계', '누계'].includes(type)) return 'green'
  return 'default'
}

function rowClassName(record) {
  if (record.rowType === 'section') return 'section-row'
  if (record.rowType === 'vendor') return 'vendor-row'
  if (record.strong) return 'strong-row'
  if (record.sourceKey) return 'input-row'
  return ''
}

function snapshot(data = planData.value) {
  return JSON.stringify(data)
}

function findDirtyPlanKeys() {
  if (!originalSnapshot.value) return new Set()
  const original = JSON.parse(originalSnapshot.value)
  const dirty = new Set()
  Object.keys(planData.value).forEach(year => {
    Object.keys(planData.value[year] || {}).forEach(month => {
      const before = original[year]?.[month] || {}
      const after = planData.value[year]?.[month] || {}
      if (planFields.some(field => Number(before[field] || 0) !== Number(after[field] || 0))) {
        dirty.add(`${year}-${month}`)
      }
    })
  })
  return dirty
}

function rowsToYearData(rows) {
  const data = createEmptyYearData()
  rows.forEach(row => {
    const month = Number(row.plan_month)
    if (!data[month]) return
    planFields.forEach(field => { data[month][field] = Number(row[field] || 0) })
    data[month].notes = row.notes || ''
  })
  return data
}

function rowsToCumulative(rows) {
  const data = createEmptyCumulative()
  rows.forEach(row => {
    planFields.forEach(field => { data[field] += Number(row[field] || 0) })
  })
  return data
}

async function loadProjects() {
  const res = await executionApi.getProjects()
  projects.value = res.data
}

async function loadPlans() {
  dirtyPlanKeys.value = new Set()
  await loadPlanMeta()
  if (!selectedProjectId.value) {
    planData.value = createEmptyPlanDataForYears()
    prevCumulative.value = createEmptyCumulative()
    originalSnapshot.value = snapshot()
    return
  }

  planLoading.value = true
  try {
    const [base, previous, current] = await Promise.all([
      executionApi.getProjectPlans(selectedProjectId.value, cumulativeYear.value),
      executionApi.getProjectPlans(selectedProjectId.value, previousPlanYear.value),
      executionApi.getProjectPlans(selectedProjectId.value, currentPlanYear.value),
    ])
    planData.value = {
      [previousPlanYear.value]: rowsToYearData(previous.data),
      [currentPlanYear.value]: rowsToYearData(current.data),
    }
    prevCumulative.value = rowsToCumulative(base.data)
    originalSnapshot.value = snapshot()
  } finally {
    planLoading.value = false
  }
}

function resetPlans() {
  if (!originalSnapshot.value) return
  planData.value = JSON.parse(originalSnapshot.value)
  dirtyPlanKeys.value = new Set()
}

async function savePlans() {
  if (!selectedProjectId.value || dirtyCount.value === 0) return
  saving.value = true
  try {
    await savePlanMeta()
    const planKeys = Array.from(dirtyPlanKeys.value).sort()
    await Promise.all(planKeys.map(key => {
      const [yearText, monthText] = key.split('-')
      const year = Number(yearText)
      const month = Number(monthText)
      return executionApi.upsertProjectPlan({
      project_id: selectedProjectId.value,
      plan_year: year,
      plan_month: month,
      revenue_plan: planData.value[year][month].revenue_plan || 0,
      material_plan: planData.value[year][month].material_plan || 0,
      subcontract_plan: planData.value[year][month].subcontract_plan || 0,
      labor_plan: planData.value[year][month].labor_plan || 0,
      expense_plan: planData.value[year][month].expense_plan || 0,
      notes: planData.value[year][month].notes || '',
    })
    }))
    originalSnapshot.value = snapshot()
    dirtyPlanKeys.value = new Set()
    message.success('매출/투입 계획이 저장되었습니다.')
  } catch (e) {
    message.error(e.response?.data?.detail || '저장 중 오류가 발생했습니다.')
  } finally {
    saving.value = false
  }
}

watch([contractDate, changeColumnGroups, materialVendorRows], () => {
  savePlanMeta().catch(() => {})
}, { deep: true })

onMounted(async () => {
  await loadProjects()
  await loadPlanMeta()
})
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.selector-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.sel-label { font-size: 13px; font-weight: 600; color: #595959; }
.proj-info { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-top: 12px; font-size: 13px; color: #595959; }

.stat-card   { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue   { border-left-color: #1677ff; }
.stat-orange { border-left-color: #fa8c16; }
.stat-green  { border-left-color: #52c41a; }
.stat-purple { border-left-color: #722ed1; }
.stat-inner  { display: flex; align-items: center; gap: 14px; }
.stat-icon   { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.icon-blue   { background: #e6f4ff; color: #1677ff; }
.icon-green  { background: #f6ffed; color: #52c41a; }
.icon-orange { background: #fff7e6; color: #fa8c16; }
.icon-purple { background: #f9f0ff; color: #722ed1; }
.stat-label  { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value  { font-size: 24px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit   { font-size: 13px; font-weight: 400; margin-left: 3px; color: #8c8c8c; }

.table-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size: 15px; font-weight: 600; color: #1a2535; }
.grid-help { margin-bottom: 10px; color: #8c8c8c; font-size: 12px; }
.select-alert { margin-bottom: 12px; }
.plan-section { margin-top: 16px; }
.plan-section:first-of-type { margin-top: 0; }
.section-title { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; font-size: 13px; font-weight: 700; color: #1a2535; }
.section-add-btn {
  border-color: #d9d9d9;
  background: #fff;
  color: #1a2535;
  font-size: 12px;
  font-weight: 600;
}
.section-add-btn:hover,
.section-add-btn:focus {
  border-color: #1677ff;
  color: #1677ff;
}
.header-input-wrap { display: flex; flex-direction: column; gap: 4px; align-items: stretch; }
.header-input-label { font-size: 11px; font-weight: 600; line-height: 1.1; }
.header-date { width: 132px; }
.header-change-title { display: flex; align-items: center; justify-content: center; gap: 8px; }
.header-change-cell { display: flex; align-items: center; justify-content: center; }
.header-change-input { width: 132px; text-align: center; }
:deep(.header-change-input input::placeholder) { color: #bfbfbf; }
.header-change-add {
  height: 24px;
  padding: 0 9px;
  border: 1px solid #91caff;
  border-radius: 4px;
  background: #e6f4ff;
  color: #0958d9;
  font-size: 12px;
  font-weight: 600;
  line-height: 22px;
  box-shadow: 0 1px 2px rgba(22, 119, 255, 0.12);
}
.header-change-add:hover,
.header-change-add:focus {
  border-color: #1677ff;
  background: #bae0ff;
  color: #003eb3;
}
.label-cell.strong { font-weight: 700; color: #1a2535; }
.num-cell { display: block; text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.num-cell.percent { text-align: center; }
.num-cell.warn { color: #f5222d; font-weight: 600; }
.month-input { width: 96px; }
.vendor-name-input { width: 118px; }
.vendor-type-select { width: 82px; }

:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
:deep(.ant-table-cell) { white-space: nowrap; }
:deep(.section-row td) { background: #eef4ff !important; color: #1a2535; font-weight: 700; }
:deep(.strong-row td) { background: #fafafa; font-weight: 600; }
:deep(.input-row td) { background: #fff; }
:deep(.vendor-row td) { background: #fcfcfc; }
:deep(.input-row .ant-input-number) { border-color: #d9e6ff; }
:deep(.ant-table-cell-fix-left),
:deep(.ant-table-cell-fix-left-last) {
  position: sticky !important;
  z-index: 3;
  background: #fff !important;
  overflow: hidden;
}
:deep(.ant-table-thead .ant-table-cell-fix-left),
:deep(.ant-table-thead .ant-table-cell-fix-left-last) {
  z-index: 5;
  background: #fafafa !important;
}
:deep(.section-row .ant-table-cell-fix-left),
:deep(.section-row .ant-table-cell-fix-left-last) {
  background: #eef4ff !important;
}
:deep(.strong-row .ant-table-cell-fix-left),
:deep(.strong-row .ant-table-cell-fix-left-last) {
  background: #fafafa !important;
}
:deep(.vendor-row .ant-table-cell-fix-left),
:deep(.vendor-row .ant-table-cell-fix-left-last) {
  background: #fcfcfc !important;
}
:deep(.ant-table-cell-fix-left-last::after) {
  box-shadow: inset 8px 0 8px -8px rgba(0,0,0,0.18);
}
</style>
