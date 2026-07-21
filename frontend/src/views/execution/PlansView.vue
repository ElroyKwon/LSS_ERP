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
        <div class="plan-title-row">
          <span class="card-title">매출 투입 계획</span>
          <div class="week-nav">
            <a-button size="small" @click="movePlanWeek(-1)">
              <template #icon><LeftOutlined /></template>
            </a-button>
            <span class="week-period">{{ weekRangeLabel }}</span>
            <a-tag v-if="sourceWeek && sourceWeek !== weekStart" color="orange">
              {{ sourceWeek }} 자료 복사
            </a-tag>
            <a-tag v-else color="blue">작성중</a-tag>
            <a-button size="small" @click="movePlanWeek(1)">
              <template #icon><RightOutlined /></template>
            </a-button>
            <a-button size="small" @click="goThisWeek">이번 주</a-button>
          </div>
        </div>
      </template>
      <template #extra>
        <a-space>
          <a-tag v-if="dirtyCount > 0" color="orange">{{ dirtyCount }}건 변경</a-tag>
          <a-button size="small" @click="resetPlans" :disabled="saving || dirtyCount === 0">되돌리기</a-button>
          <a-button type="primary" size="small" :loading="saving" :disabled="!selectedProjectId || dirtyCount === 0" @click="savePlans">
            <template #icon><SaveOutlined /></template>
            저장
          </a-button>
        </a-space>
      </template>

      <div class="grid-help">
        엑셀 양식의 고정 열을 화면에서도 왼쪽에 고정했습니다. 월별 계획 값은 흰색 입력칸에서 수정하고,
        누계, 수주잔, 원가율, 합계는 자동 계산됩니다.
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
          <span v-if="section.key === 'revenue'" class="section-period">{{ projectPeriodText }}</span>
          <template v-else>
            <a-button
              v-if="section.key === 'material'"
              size="small"
              class="section-add-btn"
              @click="addMaterialVendorRow"
            >
              거래처 추가
            </a-button>
            <a-button
              v-if="section.key === 'labor'"
              size="small"
              class="section-add-btn"
              @click="addLaborDetailRow"
            >
              행 추가
            </a-button>
          </template>
        </div>
        <a-table
          :columns="getPlanColumns(section.key)"
          :data-source="section.rows"
          :loading="planLoading"
          :pagination="{ defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'] }"
          row-key="key"
          size="small"
          :scroll="{ x: tableScrollX }"
          :row-class-name="rowClassName"
          bordered
        
        :sticky="{ offsetHeader: 56 }">
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
              <span>{{ column.title }}</span>
            </template>
            <template v-else-if="column.key === 'order_amount'">
              <div v-if="column.showOrderDate" class="header-input-wrap">
                <a-date-picker
                  v-model:value="orderDate"
                  size="small"
                  value-format="YYYY-MM-DD"
                  placeholder="수주일"
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
                v-if="record.key === 'order-company-name'"
                v-model:value="orderCompanyName"
                size="small"
                placeholder="수주업체명"
                class="vendor-name-input"
                @change="savePlanMeta().catch(() => {})"
              />
              <a-input
                v-else-if="record.rowType === 'vendor'"
                :value="getMaterialVendorRow(record.vendorId)?.vendorName"
                size="small"
                placeholder="거래처명"
                class="vendor-name-input"
                @change="(event) => setMaterialVendorName(record.vendorId, event.target.value)"
              />
              <a-input
                v-else-if="record.rowType === 'labor-detail'"
                :value="getLaborDetailRow(record.detailId)?.label"
                size="small"
                placeholder="내용"
                class="vendor-name-input"
                @change="(event) => setLaborDetailLabel(record.detailId, event.target.value)"
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
              <a-input-number
                v-if="isEditableDetailContractCell(record)"
                :value="getDetailContractAmount(record)"
                :min="0"
                size="small"
                placeholder="계약액"
                class="month-input"
                :formatter="formatInput"
                :parser="parseInput"
                @change="(value) => setDetailContractAmount(record, value)"
              />
              <span v-else class="num-cell">{{ contractCellText(record) }}</span>
            </template>

            <template v-else-if="column.key === 'order_amount'">
              <a-input-number
                v-if="record.key === 'invoice'"
                v-model:value="orderAmount"
                :min="0"
                size="small"
                placeholder="수주금액"
                class="month-input"
                :formatter="formatInput"
                :parser="parseInput"
                @change="savePlanMeta().catch(() => {})"
              />
              <a-input-number
                v-else-if="record.key === 'labor-overview'"
                v-model:value="orderLaborCost"
                :min="0"
                size="small"
                placeholder="인건비"
                class="month-input"
                :formatter="formatInput"
                :parser="parseInput"
                @change="savePlanMeta().catch(() => {})"
              />
              <a-input-number
                v-else-if="record.key === 'expense-overview'"
                v-model:value="orderExpenseCost"
                :min="0"
                size="small"
                placeholder="경비"
                class="month-input"
                :formatter="formatInput"
                :parser="parseInput"
                @change="savePlanMeta().catch(() => {})"
              />
              <span v-else class="num-cell">{{ orderColumnCellText(record) }}</span>
            </template>

            <template v-else-if="column.changeIndex !== undefined">
              <a-input-number
                v-if="record.key === 'invoice'"
                v-model:value="changeColumnGroups[column.sectionKey][column.changeIndex].amount"
                :min="0"
                size="small"
                placeholder="계약액"
                class="month-input"
                :formatter="formatInput"
                :parser="parseInput"
                @change="savePlanMeta().catch(() => {})"
              />
              <a-input-number
                v-else-if="record.key === 'labor-overview'"
                v-model:value="changeColumnGroups[column.sectionKey][column.changeIndex].laborCost"
                :min="0"
                size="small"
                placeholder="인건비"
                class="month-input"
                :formatter="formatInput"
                :parser="parseInput"
                @change="savePlanMeta().catch(() => {})"
              />
              <a-input-number
                v-else-if="record.key === 'expense-overview'"
                v-model:value="changeColumnGroups[column.sectionKey][column.changeIndex].expenseCost"
                :min="0"
                size="small"
                placeholder="경비"
                class="month-input"
                :formatter="formatInput"
                :parser="parseInput"
                @change="savePlanMeta().catch(() => {})"
              />
              <span v-else class="num-cell">{{ changeColumnCellText(record, column.changeIndex) }}</span>
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
              <a-select
                v-else-if="record.rowType === 'labor-detail'"
                :value="getLaborDetailRow(record.detailId)?.costType"
                size="small"
                class="vendor-type-select"
                @change="(value) => setLaborDetailCostType(record.detailId, value)"
              >
                <a-select-option value="labor_plan">인건비</a-select-option>
                <a-select-option value="expense_plan">직접경비</a-select-option>
              </a-select>
              <a-tag v-else-if="record.type" :color="typeColor(record.type)">{{ record.type }}</a-tag>
            </template>

            <template v-else-if="isMonthColumn(column)">
              <a-input-number
                v-if="record.rowType === 'vendor' && isEditableMaterialVendorMonth(record, column)"
                :value="getMaterialVendorMonthValue(record.vendorId, column.year, column.month)"
                :min="0"
                size="small"
                class="month-input"
                :formatter="formatInput"
                :parser="parseInput"
                @change="(value) => setMaterialVendorMonthValue(record.vendorId, column.year, column.month, value)"
              />
              <span v-else-if="record.rowType === 'vendor'" class="num-cell">
                {{ formatCell(record, column.key) }}
              </span>
              <a-input-number
                v-else-if="record.rowType === 'labor-detail'"
                :value="getLaborDetailMonthValue(record.detailId, column.year, column.month)"
                :min="0"
                size="small"
                class="month-input"
                :formatter="formatInput"
                :parser="parseInput"
                @change="(value) => setLaborDetailMonthValue(record.detailId, column.year, column.month, value)"
              />
              <a-input-number
                v-else-if="isEditableMonthCell(record, column)"
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
  LeftOutlined,
  RightOutlined,
  RiseOutlined,
  FallOutlined,
  CalculatorOutlined,
  PercentageOutlined,
} from '@ant-design/icons-vue'
import { executionApi } from '@/api'

const now = new Date()
const years = Array.from({ length: 5 }, (_, i) => now.getFullYear() - 1 + i)
const planFields = ['invoice_plan', 'revenue_plan', 'material_plan', 'subcontract_plan', 'labor_plan', 'expense_plan']
const planMetaVersion = 4
const planSectionKeys = ['revenue', 'material', 'labor']

const projects = ref([])
const projectPurchasePlanRows = ref([])
const projectSalesPlanRows = ref([])
const salesBills = ref([])
const apBills = ref([])
const selectedProjectId = ref(null)
const selectedYear = ref(now.getFullYear())
const weekStart = ref(formatDate(startOfWeek(now)))
const sourceWeek = ref(null)
const planLoading = ref(false)
const saving = ref(false)
const planData = ref(createEmptyPlanDataForYears([selectedYear.value - 1, selectedYear.value]))
const prevCumulative = ref(createEmptyCumulative())
const originalSnapshot = ref('')
const dirtyPlanKeys = ref(new Set())
const metaDirty = ref(false)
const orderDate = ref(null)
const orderAmount = ref(0)
const orderCompanyName = ref('')
const orderLaborCost = ref(0)
const orderExpenseCost = ref(0)
const changeColumnGroups = ref(defaultChangeColumnGroups())
const materialVendorRows = ref([])
const laborDetailRows = ref([])
const planMetaLoading = ref(false)
const purchaseContractLoading = ref(false)
const suppressMetaWatch = ref(false)

const statusColor = { 미진행: 'orange', 진행중: 'blue', 완료: 'green' }

const currentPlanYear = computed(() => selectedYear.value)
const weekEnd = computed(() => addDays(weekStart.value, 6))
const weekRangeLabel = computed(() => `${formatWeekDate(new Date(weekStart.value))} ~ ${formatWeekDate(weekEnd.value)}`)
const monthColumns = computed(() => projectPeriodMonths.value.map(({ year, month }) => ({
  key: monthKey(year, month),
  year,
  month,
})))
const planYears = computed(() => [...new Set(monthColumns.value.map(column => column.year))])
const yearMonthColumnGroups = computed(() => planYears.value.map(year => ({
  year,
  months: monthColumns.value.filter(column => column.year === year),
})))
const tableScrollX = computed(() => 980 + (maxChangeColumnCount.value * 150) + (monthColumns.value.length * 110) + 360)
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

const selectedProjectPurchasePlan = computed(() => {
  const project = selectedProject.value
  if (!project) return null
  return projectPurchasePlanRows.value.find(row => row.project_id && row.project_id === project.id)
    || projectPurchasePlanRows.value.find(row => row.job_no && row.job_no === project.project_no)
    || null
})

function selectedProjectSalesPlan(year) {
  const project = selectedProject.value
  if (!project) return null
  return projectSalesPlanRows.value.find(row =>
    Number(row.plan_year || year) === Number(year)
    && row.project_id
    && Number(row.project_id) === Number(project.id)
  ) || projectSalesPlanRows.value.find(row =>
    Number(row.plan_year || year) === Number(year)
    && row.job_no
    && row.job_no === project.project_no
  ) || null
}

function projectSalesPlanMonthAmount(year, month) {
  const row = selectedProjectSalesPlan(year)
  return Number(row?.[`revenue_progress_${month}월`] || 0)
}

function approvedInvoiceAmount(year, month) {
  return salesBills.value.reduce((sum, bill) => {
    if (bill.status !== '승인') return sum
    const dateText = bill.invoice_date || bill.bill_date
    if (!dateText) return sum
    const date = new Date(dateText)
    if (Number.isNaN(date.getTime())) return sum
    if (date.getFullYear() !== Number(year) || date.getMonth() + 1 !== Number(month)) return sum
    return sum + Number(bill.bill_amount || 0)
  }, 0)
}

const projectPeriodText = computed(() => {
  const start = formatProjectPeriodDate(selectedProject.value?.contract_start)
  const end = formatProjectPeriodDate(selectedProject.value?.contract_end)
  return `프로젝트기간 : ${start} ~ ${end}`
})

const projectPeriodMonths = computed(() => {
  const start = parseProjectDate(selectedProject.value?.contract_start || selectedProject.value?.construct_start)
  const end = parseProjectDate(selectedProject.value?.contract_end || selectedProject.value?.construct_end)
  if (!start || !end || end < start) {
    return Array.from({ length: 12 }, (_, index) => ({ year: selectedYear.value, month: index + 1 }))
  }

  const months = []
  const cursor = new Date(start.getFullYear(), start.getMonth(), 1)
  const last = new Date(end.getFullYear(), end.getMonth(), 1)
  while (cursor <= last) {
    months.push({ year: cursor.getFullYear(), month: cursor.getMonth() + 1 })
    cursor.setMonth(cursor.getMonth() + 1)
  }
  return months
})

const dirtyCount = computed(() => dirtyPlanKeys.value.size + (metaDirty.value ? 1 : 0))
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
      title: '최종 계약액',
      fixed: 'left',
      children: [
        {
          title: detailSection ? '' : '최종 계약일',
          key: 'contract',
          dataIndex: 'contract',
          width: detailSection ? 128 : 150,
          align: 'right',
          fixed: 'left',
          sectionKey,
        },
      ],
    },
    ...(!detailSection ? [{
      title: '수주',
      fixed: 'left',
      children: [
        {
          title: '',
          key: 'order_amount',
          dataIndex: 'order_amount',
          width: 150,
          align: 'center',
          fixed: 'left',
          showOrderDate: true,
        },
      ],
    }] : []),
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
    ...yearMonthColumnGroups.value.map(group => ({
      title: `${group.year}년`,
      children: group.months.map(column => ({
        title: `${column.month}월`,
        key: column.key,
        dataIndex: column.key,
        year: column.year,
        month: column.month,
        width: 135,
        align: 'right',
      })),
    })),
    {
      title: '집계',
      children: [
        { title: '합계', key: 'total', dataIndex: 'total', width: 135, align: 'right' },
        { title: '미실행', key: 'remain', dataIndex: 'remain', width: 135, align: 'right' },
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
  const contract = Number(finalContract.value.amount || 0)
  return [
    invoiceRow(contract),
    calcRow('order-company-name', '', '', null, '', [], 0),
    calcRow('revenue', '', '', contract, '매출', timelineRevenue(), prevCumulative.value.revenue_plan, { strong: true }),
    calcRow('revenue-cumulative', '', '', contract, '누계', timelineRevenueCumulative(), prevCumulative.value.revenue_plan, { strong: true }),
    calcRow('order-balance', '수주잔', '', contract, '계산서', timelineInvoiceBalance(contract), contract - Number(prevCumulative.value.invoice_plan || 0)),
    calcRow('progress-rate', '', '', contract, '진행율', timelineProgressBalance(contract), contract - Number(prevCumulative.value.revenue_plan || 0)),
    calcRow('subcontract-overview', '예정원가', '외주비', finalExpectedSubcontractCost.value, '', timelineValue('subcontract_plan'), prevCumulative.value.subcontract_plan),
    calcRow('material-overview', '', '자재비', finalExpectedMaterialCost.value, '', timelineValue('material_plan'), prevCumulative.value.material_plan),
    calcRow('labor-overview', '', '인건비', finalExpectedLaborCost.value, '', timelineValue('labor_plan'), prevCumulative.value.labor_plan),
    calcRow('expense-overview', '', '경비', finalExpectedExpenseCost.value, '', timelineValue('expense_plan'), prevCumulative.value.expense_plan),
    calcRow('cost-total', '매출원가 합계', '', finalContractCostTotal.value, '', timelineCostTotal(), prevCostTotal(), { strong: true }),
    calcRow('cost-cumulative', '매출원가 누계', '', null, '', timelineCostCumulative(), prevCostTotal(), { strong: true }),
    calcRow('cost-rate', '원가율', '', null, '', timelineCostRate(), rate(prevCostTotal(), finalContractCostTotal.value), { format: 'percent' }),
  ]
})

const materialPlanRows = computed(() => [
  calcRow(
    'material-sub-total',
    '합계',
    '',
    materialVendorContractTotal(),
    '합계',
    timelineMaterialSubTotal(),
    prevCumulative.value.material_plan + prevCumulative.value.subcontract_plan,
    { strong: true }
  ),
  calcRow(
    'subcontract-source',
    '외주',
    '',
    materialVendorContractTotal('subcontract_plan'),
    '외주',
    timelineMaterialVendorTotal('subcontract_plan'),
    prevCumulative.value.subcontract_plan
  ),
  calcRow(
    'material-source',
    '자재',
    '',
    materialVendorContractTotal('material_plan'),
    '자재',
    timelineMaterialVendorTotal('material_plan'),
    prevCumulative.value.material_plan
  ),
  ...materialVendorRows.value.map(row => materialVendorPlanRow(row)),
])

const laborPlanRows = computed(() => [
  calcRow(
    'labor-expense-total',
    '합계',
    '',
    laborDetailContractTotal(),
    '개별비',
    timelineLaborExpenseTotal(),
    prevCumulative.value.labor_plan + prevCumulative.value.expense_plan,
    { strong: true }
  ),
  calcRow(
    'labor-source',
    '인건비',
    '',
    laborDetailContractTotal('labor_plan'),
    '인건비',
    timelineLaborDetailTotal('labor_plan'),
    prevCumulative.value.labor_plan,
    { forceReadOnly: true }
  ),
  calcRow(
    'expense-source',
    '직접경비',
    '',
    laborDetailContractTotal('expense_plan'),
    '직접경비',
    timelineLaborDetailTotal('expense_plan'),
    prevCumulative.value.expense_plan,
    { forceReadOnly: true }
  ),
  ...laborDetailRows.value.map(row => laborDetailPlanRow(row)),
])

const tableSections = computed(() => [
  { key: 'revenue', title: '매출 계획 / 예정원가', rows: revenuePlanRows.value },
  { key: 'material', title: '자재비 + 외주비', rows: materialPlanRows.value },
  { key: 'labor', title: '인건비 + 경비', rows: laborPlanRows.value },
])

function monthKey(year, month) {
  return `y${year}m${month}`
}

function parseProjectDate(value) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function formatProjectPeriodDate(value) {
  if (!value) return '        '
  return String(value).replaceAll('-', '.')
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

function startOfWeek(date) {
  const value = new Date(date)
  const day = value.getDay()
  const diff = day === 0 ? -6 : 1 - day
  value.setHours(0, 0, 0, 0)
  value.setDate(value.getDate() + diff)
  return value
}

function addDays(dateText, days) {
  const date = new Date(dateText)
  date.setDate(date.getDate() + days)
  return date
}

function movePlanWeek(delta) {
  weekStart.value = formatDate(startOfWeek(addDays(weekStart.value, delta * 7)))
  loadPlans()
}

function goThisWeek() {
  weekStart.value = formatDate(startOfWeek(new Date()))
  loadPlans()
}

function createEmptyYearData() {
  return Object.fromEntries(Array.from({ length: 12 }, (_, i) => [
    i + 1,
    {
      invoice_plan: 0,
      revenue_plan: 0,
      material_plan: 0,
      subcontract_plan: 0,
      labor_plan: 0,
      expense_plan: 0,
      notes: '',
    },
  ]))
}

function createEmptyPlanDataForYears(yearList = (planYears.value.length ? planYears.value : [selectedYear.value])) {
  return Object.fromEntries(yearList.map(year => [year, createEmptyYearData()]))
}

function createEmptyCumulative() {
  return {
    invoice_plan: 0,
    revenue_plan: 0,
    material_plan: 0,
    subcontract_plan: 0,
    labor_plan: 0,
    expense_plan: 0,
  }
}

function metricRow(key, label, item, contract, type, sourceKey, options = {}) {
  const total = timelineValue(sourceKey).reduce((sum, value) => sum + value, 0)
  const row = { key, label, item, contract, type, sourceKey, rowType: 'metric', total, ...options }
  if (contract) {
    row.remain = contract - total
    row.rate = rate(total, contract)
  }
  return row
}

function calcRow(key, label, item, contract, type, months, prev, options = {}) {
  const row = { key, label, item, contract, type, rowType: 'calc', ...options }
  monthColumns.value.forEach((column, index) => { row[column.key] = months[index] || 0 })
  row.total = monthColumns.value.reduce((sum, column) => sum + Number(row[column.key] || 0), 0)
  if (contract) {
    row.remain = contract - row.total
    row.rate = rate(row.total, contract)
  }
  return row
}

function invoiceRow(contract) {
  const row = calcRow(
    'invoice',
    '수주업체명',
    '',
    contract,
    '매출계산서 발행',
    timelineInvoice(),
    Number(prevCumulative.value.invoice_plan || 0)
  )
  row.sourceKey = 'invoice_plan'
  row.lockedMonthKeys = new Set(
    monthColumns.value
      .filter(column => approvedInvoiceAmount(column.year, column.month) > 0)
      .map(column => column.key)
  )
  return row
}
function materialVendorPlanRow(vendor) {
  const row = {
    key: `material-vendor-${vendor.id}`,
    label: vendor.vendorName || '',
    item: '거래처',
    contract: Number(vendor.contractAmount || 0),
    type: vendor.costType === 'material_plan' ? '자재' : '외주',
    rowType: 'vendor',
    vendorId: vendor.id,
    vendorCostType: vendor.costType,
    source: vendor.source || null,
  }
  monthColumns.value.forEach(column => {
    row[column.key] = getMaterialVendorMonthValue(vendor.id, column.year, column.month)
  })
  row.total = monthColumns.value.reduce((sum, column) => sum + Number(row[column.key] || 0), 0)
  row.remain = Number(row.contract || 0) - row.total
  row.rate = rate(row.total, row.contract)
  return row
}

function laborDetailPlanRow(detail) {
  const row = {
    key: `labor-detail-${detail.id}`,
    label: detail.label || '',
    item: '상세',
    contract: Number(detail.contractAmount || 0),
    type: detail.costType === 'expense_plan' ? '직접경비' : '인건비',
    rowType: 'labor-detail',
    detailId: detail.id,
  }
  monthColumns.value.forEach(column => {
    row[column.key] = getLaborDetailMonthValue(detail.id, column.year, column.month)
  })
  row.total = monthColumns.value.reduce((sum, column) => sum + Number(row[column.key] || 0), 0)
  row.remain = Number(row.contract || 0) - row.total
  row.rate = rate(row.total, row.contract)
  return row
}

function yearValue(field, year) {
  if (field === 'material_plan' || field === 'subcontract_plan') {
    return Array.from({ length: 12 }, (_, i) => materialVendorMonthTotal(field, year, i + 1))
  }
  if (field === 'labor_plan' || field === 'expense_plan') {
    return Array.from({ length: 12 }, (_, i) => laborDetailMonthTotal(field, year, i + 1))
  }
  return Array.from({ length: 12 }, (_, i) => Number(planData.value[year]?.[i + 1]?.[field] || 0))
}

function timelineValue(field) {
  return planYears.value.flatMap(year => yearValue(field, year))
}

function timelineInvoice() {
  return monthColumns.value.map(({ year, month }) => {
    const approvedAmount = approvedInvoiceAmount(year, month)
    return approvedAmount > 0 ? approvedAmount : Number(planData.value[year]?.[month]?.invoice_plan || 0)
  })
}

function timelineRevenue() {
  let previousRevenueCumulative = Number(prevCumulative.value.revenue_plan || 0)
  return monthColumns.value.map(({ year, month }) => {
    const salesPlanAmount = projectSalesPlanMonthAmount(year, month)
    if (salesPlanAmount > 0) {
      previousRevenueCumulative += salesPlanAmount
      return salesPlanAmount
    }
    const currentRevenueCumulative = Number(finalContract.value.amount || 0) * rate(monthCostCumulative(year, month), finalContractCostTotal.value) / 100
    const amount = Math.max(currentRevenueCumulative - previousRevenueCumulative, 0)
    previousRevenueCumulative += amount
    return amount
  })
}

function timelineRevenueCumulative() {
  let sum = Number(prevCumulative.value.revenue_plan || 0)
  return timelineRevenue().map(value => {
    sum += Number(value || 0)
    return sum
  })
}

function timelineInvoiceBalance(contract) {
  let balance = Number(contract || 0) - Number(prevCumulative.value.invoice_plan || 0)
  return timelineInvoice().map(value => {
    balance -= Number(value || 0)
    return balance
  })
}

function timelineProgressBalance(contract) {
  let previousInvoiceBalance = Number(contract || 0) - Number(prevCumulative.value.invoice_plan || 0)
  return timelineRevenue().map((value, index) => {
    const balance = previousInvoiceBalance - Number(value || 0)
    previousInvoiceBalance = timelineInvoiceBalance(contract)[index] || 0
    return balance
  })
}

function timelineCumulative(field) {
  let sum = 0
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
  let sum = 0
  return timelineCostTotal().map(v => {
    sum += v
    return sum
  })
}

function timelineCostRate() {
  return timelineCostCumulative().map(v => rate(v, finalContractCostTotal.value))
}

function monthCostCumulative(targetYear, targetMonth) {
  let sum = Number(prevCostTotal() || 0)
  for (const { year, month } of monthColumns.value) {
    const row = planData.value[year]?.[month] || {}
    sum += Number(row.material_plan || 0)
      + Number(row.subcontract_plan || 0)
      + Number(row.labor_plan || 0)
      + Number(row.expense_plan || 0)
    if (year === targetYear && month === targetMonth) return sum
  }
  return sum
}

function timelineMaterialSubTotal() {
  return monthColumns.value.map(({ year, month }) =>
    materialVendorMonthTotal('material_plan', year, month) + materialVendorMonthTotal('subcontract_plan', year, month)
  )
}

function timelineMaterialVendorTotal(costType) {
  return monthColumns.value.map(({ year, month }) => materialVendorMonthTotal(costType, year, month))
}

function materialVendorMonthTotal(costType, year, month) {
  return materialVendorRows.value
    .filter(row => !costType || row.costType === costType)
    .reduce((sum, row) => sum + getMaterialVendorMonthValue(row.id, year, month), 0)
}

function materialVendorContractTotal(costType = null) {
  return materialVendorRows.value
    .filter(row => !costType || row.costType === costType)
    .reduce((sum, row) => sum + Number(row.contractAmount || 0), 0)
}

function timelineLaborExpenseTotal() {
  return monthColumns.value.map(({ year, month }) =>
    laborDetailMonthTotal('labor_plan', year, month) + laborDetailMonthTotal('expense_plan', year, month)
  )
}

function timelineLaborDetailTotal(costType) {
  return monthColumns.value.map(({ year, month }) => laborDetailMonthTotal(costType, year, month))
}

function laborDetailMonthTotal(costType, year, month) {
  return laborDetailRows.value
    .filter(row => !costType || row.costType === costType)
    .reduce((sum, row) => sum + getLaborDetailMonthValue(row.id, year, month), 0)
}

function laborDetailContractTotal(costType = null) {
  return laborDetailRows.value
    .filter(row => !costType || row.costType === costType)
    .reduce((sum, row) => sum + Number(row.contractAmount || 0), 0)
}

function prevCostTotal() {
  return prevCumulative.value.material_plan + prevCumulative.value.subcontract_plan + prevCumulative.value.labor_plan + prevCumulative.value.expense_plan
}

function rate(value, base) {
  return Number(base || 0) > 0 ? Number(value || 0) / Number(base) * 100 : 0
}

const projectOrderAmount = computed(() => Number(selectedProject.value?.contract_amount || 0))
const projectOrderDate = computed(() => selectedProject.value?.contract_start || '')
const effectiveOrderAmount = computed(() => Number(orderAmount.value || projectOrderAmount.value || 0))
const effectiveOrderDate = computed(() => orderDate.value || projectOrderDate.value || '')

const finalContract = computed(() => {
  const changes = changeColumnGroups.value.revenue || []
  for (let index = changes.length - 1; index >= 0; index -= 1) {
    const change = changes[index] || {}
    if (change.amount || change.label) {
      return {
        amount: Number(change.amount || effectiveOrderAmount.value || 0),
        date: change.label || effectiveOrderDate.value || '',
      }
    }
  }
  return {
    amount: effectiveOrderAmount.value,
    date: effectiveOrderDate.value,
  }
})

function contractCellText(record) {
  if (record.key === 'invoice') {
    return finalContract.value.amount ? money(finalContract.value.amount) : ''
  }
  if (record.key === 'order-company-name') {
    return finalContract.value.date || ''
  }
  if (record.key === 'order-balance') {
    return moneyOrBlank(finalContractOrderBalance.value)
  }
  if (record.key === 'progress-rate') {
    return percentOrBlank(finalContractProgressRate.value)
  }
  if (record.key === 'cost-total') {
    return moneyOrBlank(finalContractCostTotal.value)
  }
  if (record.key === 'cost-cumulative') {
    return moneyOrBlank(finalContractCostCumulative.value)
  }
  if (record.key === 'cost-rate') {
    return percentOrBlank(finalContractCostRate.value)
  }
  if (Number(record.contract || 0)) {
    return moneyOrBlank(record.contract)
  }
  return ''
}

function isEditableDetailContractCell(record) {
  if (record.rowType === 'vendor') return !record.source
  return record.rowType === 'labor-detail'
}

function getDetailContractAmount(record) {
  if (record.rowType === 'vendor') {
    return getMaterialVendorRow(record.vendorId)?.contractAmount
  }
  if (record.rowType === 'labor-detail') {
    return getLaborDetailRow(record.detailId)?.contractAmount
  }
  return 0
}

function setDetailContractAmount(record, value) {
  if (record.rowType === 'vendor') {
    setMaterialVendorContractAmount(record.vendorId, value)
    return
  }
  if (record.rowType === 'labor-detail') {
    setLaborDetailContractAmount(record.detailId, value)
  }
}

const finalContractCostBase = computed(() => {
  const latestChangeIndex = latestRevenueChangeIndex()
  return latestChangeIndex >= 0 ? changeCostTotal(latestChangeIndex) : orderCostTotal.value
})

const finalContractOrderBalance = computed(() =>
  Number(finalContract.value.amount || 0) - Number(prevCumulative.value.revenue_plan || 0)
)

const finalContractProgressRate = computed(() =>
  rate(prevCumulative.value.revenue_plan, finalContract.value.amount)
)

const finalContractCostTotal = computed(() => finalContractCostBase.value)
const finalContractCostCumulative = computed(() => finalContractCostBase.value + prevCostTotal())
const finalContractCostRate = computed(() =>
  rate(finalContractCostTotal.value, finalContract.value.amount)
)

const orderMaterialCost = computed(() => projectPurchasePlanAmount('ordered_material_cost'))
const orderSubcontractCost = computed(() => projectPurchasePlanAmount('ordered_subcontract_cost'))
const orderCostTotal = computed(() =>
  orderMaterialCost.value + orderSubcontractCost.value + Number(orderLaborCost.value || 0) + Number(orderExpenseCost.value || 0)
)
const orderCostRate = computed(() =>
  rate(orderCostTotal.value, effectiveOrderAmount.value)
)

function changeContractAmount(changeIndex) {
  const change = changeColumnGroup('revenue', changeIndex)
  return Number(change.amount || 0)
}

function changeColumnGroup(sectionKey, changeIndex) {
  return changeColumnGroups.value[sectionKey]?.[changeIndex] || {}
}

function changeLaborCost(changeIndex) {
  return Number(changeColumnGroup('revenue', changeIndex).laborCost || 0)
}

function changeExpenseCost(changeIndex) {
  return Number(changeColumnGroup('revenue', changeIndex).expenseCost || 0)
}

function changeCostTotal(changeIndex) {
  return orderMaterialCost.value + orderSubcontractCost.value + changeLaborCost(changeIndex) + changeExpenseCost(changeIndex)
}

const finalExpectedMaterialCost = computed(() => orderMaterialCost.value)
const finalExpectedSubcontractCost = computed(() => orderSubcontractCost.value)
const finalExpectedLaborCost = computed(() => {
  const latestChangeIndex = latestRevenueChangeIndex()
  return latestChangeIndex >= 0 ? changeLaborCost(latestChangeIndex) : Number(orderLaborCost.value || 0)
})
const finalExpectedExpenseCost = computed(() => {
  const latestChangeIndex = latestRevenueChangeIndex()
  return latestChangeIndex >= 0 ? changeExpenseCost(latestChangeIndex) : Number(orderExpenseCost.value || 0)
})

function changeCostRate(changeIndex) {
  return rate(changeCostTotal(changeIndex), changeContractAmount(changeIndex))
}

function latestRevenueChangeIndex() {
  const changes = changeColumnGroups.value.revenue || []
  for (let index = changes.length - 1; index >= 0; index -= 1) {
    const change = changes[index] || {}
    if (change.label || Number(change.amount || 0) || Number(change.laborCost || 0) || Number(change.expenseCost || 0)) {
      return index
    }
  }
  return -1
}

function projectPurchasePlanAmount(key) {
  return Number(selectedProjectPurchasePlan.value?.[key] || 0)
}

function orderColumnCellText(record) {
  if (record.key === 'subcontract-overview') {
    return moneyOrBlank(orderSubcontractCost.value)
  }
  if (record.key === 'material-overview') {
    return moneyOrBlank(orderMaterialCost.value)
  }
  if (record.key === 'cost-total') {
    return moneyOrBlank(orderCostTotal.value)
  }
  if (record.key === 'cost-rate') {
    return percentOrBlank(orderCostRate.value)
  }
  return ''
}

function changeColumnCellText(record, changeIndex) {
  if (record.key === 'subcontract-overview') {
    return moneyOrBlank(orderSubcontractCost.value)
  }
  if (record.key === 'material-overview') {
    return moneyOrBlank(orderMaterialCost.value)
  }
  if (record.key === 'labor-overview') {
    return moneyOrBlank(changeLaborCost(changeIndex))
  }
  if (record.key === 'expense-overview') {
    return moneyOrBlank(changeExpenseCost(changeIndex))
  }
  if (record.key === 'cost-total') {
    return moneyOrBlank(changeCostTotal(changeIndex))
  }
  if (record.key === 'cost-rate') {
    return percentOrBlank(changeCostRate(changeIndex))
  }
  return ''
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

function isLaborSummaryReadOnly(record) {
  return Boolean(record.forceReadOnly && record.sourceKey)
}

function isEditableMonthCell(record, column) {
  if (!record.sourceKey) return false
  if (isLaborSummaryReadOnly(record)) return false
  if (record.key === 'invoice') {
    return !record.lockedMonthKeys?.has(column.key)
  }
  return ['material_plan', 'subcontract_plan', 'labor_plan', 'expense_plan'].includes(record.sourceKey)
}

function addChangeColumn(sectionKey) {
  if (!changeColumnGroups.value[sectionKey]) {
    changeColumnGroups.value[sectionKey] = defaultChangeColumns()
  }
  changeColumnGroups.value[sectionKey].push({ label: '', amount: 0, laborCost: 0, expenseCost: 0 })
}

function addMaterialVendorRow() {
  materialVendorRows.value.push({
    id: `vendor-${Date.now()}-${materialVendorRows.value.length + 1}`,
    vendorName: '',
    costType: 'subcontract_plan',
    contractAmount: 0,
    values: {},
  })
}

function purchaseContractVendorId(contractId) {
  return `purchase-contract-${contractId}`
}

function purchaseContractCostType(contractType) {
  return contractType === '자재' ? 'material_plan' : 'subcontract_plan'
}

function mergePurchaseContractVendors(contracts = []) {
  if (!Array.isArray(contracts) || contracts.length === 0) return false
  let changed = false
  const existingById = new Map(materialVendorRows.value.map(row => [row.id, row]))
  const existingByNameAndType = new Map(
    materialVendorRows.value
      .filter(row => row.vendorName)
      .map(row => [`${row.vendorName}::${row.costType}`, row])
  )
  contracts
    .filter(row => row?.id && row?.vendor_name && ['자재', '외주'].includes(row.contract_type))
    .forEach(row => {
      const id = purchaseContractVendorId(row.id)
      const costType = purchaseContractCostType(row.contract_type)
      const existing = existingById.get(id) || existingByNameAndType.get(`${row.vendor_name}::${costType}`)
      if (existing) {
        if (
          existing.id !== id
          || existing.vendorName !== row.vendor_name
          || existing.costType !== costType
          || Number(existing.contractAmount || 0) !== Number(row.contract_amount || 0)
          || existing.source !== 'purchase_contract'
          || existing.purchaseContractId !== row.id
          || Number(existing.vendorId || 0) !== Number(row.vendor_id || 0)
        ) {
          existing.id = id
          existing.vendorName = row.vendor_name
          existing.costType = costType
          existing.contractAmount = Number(row.contract_amount || 0)
          existing.source = 'purchase_contract'
          existing.purchaseContractId = row.id
          existing.vendorId = row.vendor_id || null
          changed = true
        }
        return
      }
      materialVendorRows.value.push({
        id,
        vendorName: row.vendor_name,
        costType,
        contractAmount: Number(row.contract_amount || 0),
        values: {},
        source: 'purchase_contract',
        purchaseContractId: row.id,
        vendorId: row.vendor_id || null,
      })
      changed = true
    })
  return changed
}

async function syncApprovedPurchaseContractVendors() {
  if (!selectedProjectId.value) return
  purchaseContractLoading.value = true
  try {
    const res = await executionApi.getPurchaseContracts({
      project_id: selectedProjectId.value,
      status: '승인',
    })
    const changed = mergePurchaseContractVendors(res.data)
    if (changed) {
      syncAllMaterialVendorAggregates(false)
      await savePlanMeta(true)
    }
  } finally {
    purchaseContractLoading.value = false
  }
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
  if (!row) return
  const oldType = row.costType
  row.costType = value
  syncMaterialVendorAggregate(oldType)
  syncMaterialVendorAggregate(row.costType)
}

function setMaterialVendorContractAmount(id, value) {
  const row = getMaterialVendorRow(id)
  if (row) row.contractAmount = Number(value || 0)
}

function getMaterialVendorMonthValue(id, year, month) {
  const row = getMaterialVendorRow(id)
  if (!row) return 0
  const approvedAmount = approvedAPBillAmount(row, year, month)
  return approvedAmount > 0 ? approvedAmount : Number(row.values?.[year]?.[month] || 0)
}

function setMaterialVendorMonthValue(id, year, month, value) {
  const row = getMaterialVendorRow(id)
  if (!row) return
  if (!row.values) row.values = {}
  if (!row.values[year]) row.values[year] = {}
  row.values[year][month] = Number(value || 0)
  syncMaterialVendorAggregate(row.costType, year, month)
}

function isEditableMaterialVendorMonth(record, column) {
  const row = getMaterialVendorRow(record.vendorId)
  return row ? approvedAPBillAmount(row, column.year, column.month) <= 0 : false
}

function approvedAPBillAmount(vendor, year, month) {
  return apBills.value.reduce((sum, bill) => {
    if (bill.status !== '승인') return sum
    if (!isSameVendor(bill, vendor)) return sum
    const dateText = bill.bill_date || bill.invoice_date
    if (!dateText) return sum
    const date = new Date(dateText)
    if (Number.isNaN(date.getTime())) return sum
    if (date.getFullYear() !== Number(year) || date.getMonth() + 1 !== Number(month)) return sum
    return sum + Number(bill.bill_amount || 0)
  }, 0)
}

function isSameVendor(bill, vendor) {
  if (bill.vendor_id && vendor.vendorId && Number(bill.vendor_id) === Number(vendor.vendorId)) return true
  return String(bill.vendor_name || '').trim() === String(vendor.vendorName || '').trim()
}

function syncMaterialVendorAggregate(costType, targetYear = null, targetMonth = null, markDirty = true) {
  if (!['material_plan', 'subcontract_plan'].includes(costType)) return
  const targets = targetYear && targetMonth
    ? [{ year: targetYear, month: targetMonth }]
    : monthColumns.value.map(({ year, month }) => ({ year, month }))
  targets.forEach(({ year, month }) => {
    ensureYearData(year)
    planData.value[year][month][costType] = materialVendorMonthTotal(costType, year, month)
  })
  if (markDirty) dirtyPlanKeys.value = findDirtyPlanKeys()
}

function syncAllMaterialVendorAggregates(markDirty = true) {
  syncMaterialVendorAggregate('material_plan', null, null, markDirty)
  syncMaterialVendorAggregate('subcontract_plan', null, null, markDirty)
}

function addLaborDetailRow() {
  laborDetailRows.value.push({
    id: `labor-detail-${Date.now()}-${laborDetailRows.value.length + 1}`,
    label: '',
    costType: 'labor_plan',
    contractAmount: 0,
    values: {},
  })
}

function getLaborDetailRow(id) {
  return laborDetailRows.value.find(row => row.id === id)
}

function setLaborDetailLabel(id, value) {
  const row = getLaborDetailRow(id)
  if (row) row.label = value
}

function setLaborDetailCostType(id, value) {
  const row = getLaborDetailRow(id)
  if (!row) return
  const oldType = row.costType
  row.costType = ['labor_plan', 'expense_plan'].includes(value) ? value : 'labor_plan'
  syncLaborDetailAggregate(oldType)
  syncLaborDetailAggregate(row.costType)
}

function setLaborDetailContractAmount(id, value) {
  const row = getLaborDetailRow(id)
  if (row) row.contractAmount = Number(value || 0)
}

function getLaborDetailMonthValue(id, year, month) {
  const row = getLaborDetailRow(id)
  return Number(row?.values?.[year]?.[month] || 0)
}

function setLaborDetailMonthValue(id, year, month, value) {
  const row = getLaborDetailRow(id)
  if (!row) return
  if (!row.values) row.values = {}
  if (!row.values[year]) row.values[year] = {}
  row.values[year][month] = Number(value || 0)
  syncLaborDetailAggregate(row.costType, year, month)
}

function syncLaborDetailAggregate(costType, targetYear = null, targetMonth = null, markDirty = true) {
  if (!['labor_plan', 'expense_plan'].includes(costType)) return
  const targets = targetYear && targetMonth
    ? [{ year: targetYear, month: targetMonth }]
    : monthColumns.value.map(({ year, month }) => ({ year, month }))
  targets.forEach(({ year, month }) => {
    ensureYearData(year)
    planData.value[year][month][costType] = laborDetailMonthTotal(costType, year, month)
  })
  if (markDirty) dirtyPlanKeys.value = findDirtyPlanKeys()
}

function syncAllLaborDetailAggregates(markDirty = true) {
  syncLaborDetailAggregate('labor_plan', null, null, markDirty)
  syncLaborDetailAggregate('expense_plan', null, null, markDirty)
}

function resetPlanMeta() {
  orderDate.value = null
  orderAmount.value = projectOrderAmount.value
  orderCompanyName.value = selectedProject.value?.client_name || ''
  orderLaborCost.value = 0
  orderExpenseCost.value = 0
  changeColumnGroups.value = defaultChangeColumnGroups()
  materialVendorRows.value = []
  laborDetailRows.value = []
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
  suppressMetaWatch.value = true
  try {
    orderDate.value = meta.orderDate || null
    orderAmount.value = Number(meta.orderAmount || projectOrderAmount.value || 0)
    orderCompanyName.value = meta.orderCompanyName || selectedProject.value?.client_name || ''
    orderLaborCost.value = Number(meta.orderLaborCost || 0)
    orderExpenseCost.value = Number(meta.orderExpenseCost || 0)
    changeColumnGroups.value = meta.version === planMetaVersion
      ? normalizeChangeColumnGroups(meta.changeColumnGroups)
      : defaultChangeColumnGroups()
    materialVendorRows.value = meta.version === planMetaVersion
      ? normalizeMaterialVendorRows(meta.materialVendorRows)
      : []
    laborDetailRows.value = normalizeLaborDetailRows(meta.laborDetailRows)
    syncAllMaterialVendorAggregates(false)
    syncAllLaborDetailAggregates(false)
  } finally {
    suppressMetaWatch.value = false
  }
}

function applyWeeklySnapshot(snapshot = {}, copied = false) {
  const loadedPlanData = snapshot.planData && typeof snapshot.planData === 'object'
    ? snapshot.planData
    : createEmptyPlanDataForYears()
  planData.value = normalizePlanData(loadedPlanData)
  applyPlanMeta(snapshot.meta || {})
  originalSnapshot.value = snapshotPlanData()
  dirtyPlanKeys.value = new Set()
  metaDirty.value = copied
  sourceWeek.value = copied ? snapshot.week_start : weekStart.value
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
      await syncApprovedPurchaseContractVendors()
      await savePlanMeta(true)
      localStorage.removeItem(planMetaStorageKey.value)
      return
    }
    applyPlanMeta(meta)
    await syncApprovedPurchaseContractVendors()
  } catch (e) {
    message.error(e.response?.data?.detail || '매출 투입 계획 설정 조회 중 오류가 발생했습니다.')
  } finally {
    planMetaLoading.value = false
  }
}

async function savePlanMeta(force = false) {
  if (!selectedProjectId.value || (!force && planMetaLoading.value)) return
  await executionApi.saveProjectPlanMeta(planMetaPayload())
}

function planMetaPayload() {
  return {
    project_id: selectedProjectId.value,
    plan_year: selectedYear.value,
    version: planMetaVersion,
    orderDate: orderDate.value,
    orderAmount: orderAmount.value,
    orderCompanyName: orderCompanyName.value,
    orderLaborCost: orderLaborCost.value,
    orderExpenseCost: orderExpenseCost.value,
    changeColumnGroups: changeColumnGroups.value,
    materialVendorRows: materialVendorRows.value,
    laborDetailRows: laborDetailRows.value,
  }
}

function weeklySnapshotPayload() {
  return {
    project_id: selectedProjectId.value,
    plan_year: selectedYear.value,
    week_start: weekStart.value,
    planData: planData.value,
    meta: planMetaPayload(),
  }
}

function defaultChangeColumns() {
  return [
    { label: '', amount: 0, laborCost: 0, expenseCost: 0 },
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
      defaults[key] = groups[key].map(group => ({
        label: group.label || '',
        amount: Number(group.amount || 0),
        laborCost: Number(group.laborCost || 0),
        expenseCost: Number(group.expenseCost || 0),
      }))
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
    contractAmount: Number(row.contractAmount || 0),
    values: row.values || {},
    source: row.source || null,
    purchaseContractId: row.purchaseContractId || null,
    vendorId: row.vendorId || null,
  }))
}

function normalizeLaborDetailRows(rows) {
  if (!Array.isArray(rows)) return []
  return rows.map((row, index) => ({
    id: row.id || `labor-detail-restored-${index + 1}`,
    label: row.label || '',
    costType: ['labor_plan', 'expense_plan'].includes(row.costType) ? row.costType : 'labor_plan',
    contractAmount: Number(row.contractAmount || 0),
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

function moneyOrBlank(value) {
  const amount = Number(value || 0)
  return amount ? money(amount) : ''
}

function percentOrBlank(value) {
  const percent = Number(value || 0)
  return percent ? `${percent.toFixed(1)}%` : ''
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

function snapshotPlanData() {
  return snapshot(planData.value)
}

function normalizePlanData(data) {
  const normalized = createEmptyPlanDataForYears()
  Object.keys(data || {}).forEach(year => {
    if (!normalized[year]) normalized[year] = createEmptyYearData()
    Object.keys(data[year] || {}).forEach(month => {
      if (!normalized[year][month]) normalized[year][month] = { ...createEmptyYearData()[1] }
      planFields.forEach(field => {
        normalized[year][month][field] = Number(data[year][month]?.[field] || 0)
      })
      normalized[year][month].notes = data[year][month]?.notes || ''
    })
  })
  return normalized
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

async function loadProjectPurchasePlanRows() {
  const res = await executionApi.getProjectPurchasePlans(selectedYear.value)
  projectPurchasePlanRows.value = res.data || []
}

async function loadProjectSalesPlanRows() {
  const yearsToLoad = planYears.value.length ? planYears.value : [selectedYear.value]
  const responses = await Promise.all(yearsToLoad.map(year => executionApi.getProjectSalesPlans(year)))
  projectSalesPlanRows.value = responses.flatMap(res => res.data || [])
}

async function loadSalesBills() {
  if (!selectedProjectId.value) {
    salesBills.value = []
    return
  }
  const res = await executionApi.getSalesBills({ project_id: selectedProjectId.value })
  salesBills.value = res.data || []
}

async function loadAPBills() {
  if (!selectedProjectId.value) {
    apBills.value = []
    return
  }
  const res = await executionApi.getAPBills({ project_id: selectedProjectId.value })
  apBills.value = res.data || []
}

async function loadPlans() {
  dirtyPlanKeys.value = new Set()
  metaDirty.value = false
  sourceWeek.value = null
  await loadProjectPurchasePlanRows()
  await loadProjectSalesPlanRows()
  await loadSalesBills()
  await loadAPBills()
  if (!selectedProjectId.value) {
    planData.value = createEmptyPlanDataForYears()
    prevCumulative.value = createEmptyCumulative()
    originalSnapshot.value = snapshotPlanData()
    return
  }

  planLoading.value = true
  try {
    const currentWeekly = await executionApi.getProjectPlanWeekly(selectedProjectId.value, selectedYear.value, weekStart.value)
    if (currentWeekly.data?.exists) {
      applyWeeklySnapshot(currentWeekly.data)
      prevCumulative.value = createEmptyCumulative()
      return
    }

    const latestWeekly = await executionApi.getLatestProjectPlanWeeklyBefore(selectedProjectId.value, selectedYear.value, weekStart.value)
    if (latestWeekly.data?.exists) {
      applyWeeklySnapshot(latestWeekly.data, true)
      prevCumulative.value = createEmptyCumulative()
      message.info(`${latestWeekly.data.week_start} 자료를 불러왔습니다. 저장하면 현재 주차로 등록됩니다.`)
      return
    }

    await loadPlanMeta()
    const yearsToLoad = planYears.value.length ? planYears.value : [selectedYear.value]
    const responses = await Promise.all(
      yearsToLoad.map(year => executionApi.getProjectPlans(selectedProjectId.value, year))
    )
    planData.value = Object.fromEntries(
      yearsToLoad.map((year, index) => [year, rowsToYearData(responses[index].data)])
    )
    prevCumulative.value = createEmptyCumulative()
    syncAllMaterialVendorAggregates(false)
    syncAllLaborDetailAggregates(false)
    originalSnapshot.value = snapshotPlanData()
    dirtyPlanKeys.value = new Set()
    metaDirty.value = false
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
    syncAllMaterialVendorAggregates(false)
    syncAllLaborDetailAggregates(false)
    await savePlanMeta()
    await executionApi.saveProjectPlanWeekly(weeklySnapshotPayload())
    const planKeys = Array.from(new Set([
      ...dirtyPlanKeys.value,
      ...monthColumns.value.map(column => `${column.year}-${column.month}`),
    ])).sort()
    await Promise.all(planKeys.map(key => {
      const [yearText, monthText] = key.split('-')
      const year = Number(yearText)
      const month = Number(monthText)
      return executionApi.upsertProjectPlan({
        project_id: selectedProjectId.value,
        plan_year: year,
        plan_month: month,
        invoice_plan: planData.value[year][month].invoice_plan || 0,
        revenue_plan: planData.value[year][month].revenue_plan || 0,
        material_plan: planData.value[year][month].material_plan || 0,
        subcontract_plan: planData.value[year][month].subcontract_plan || 0,
        labor_plan: planData.value[year][month].labor_plan || 0,
        expense_plan: planData.value[year][month].expense_plan || 0,
        notes: planData.value[year][month].notes || '',
      })
    }))
    originalSnapshot.value = snapshotPlanData()
    dirtyPlanKeys.value = new Set()
    metaDirty.value = false
    sourceWeek.value = weekStart.value
    message.success('매출/투입 계획이 저장되었습니다.')
  } catch (e) {
    message.error(e.response?.data?.detail || '저장 중 오류가 발생했습니다.')
  } finally {
    saving.value = false
  }
}

watch([orderDate, orderAmount, orderCompanyName, orderLaborCost, orderExpenseCost, changeColumnGroups, materialVendorRows, laborDetailRows], () => {
  if (!suppressMetaWatch.value && !planLoading.value) metaDirty.value = true
}, { deep: true })

onMounted(async () => {
  await loadProjects()
  await loadProjectPurchasePlanRows()
  await loadProjectSalesPlanRows()
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
.plan-title-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 12px;
  width: 100%;
}
.plan-title-row .card-title { justify-self: start; }
.week-nav {
  justify-self: center;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.week-period {
  min-width: 170px;
  text-align: center;
  font-size: 13px;
  font-weight: 700;
  color: #1a2535;
}
.grid-help { margin-bottom: 10px; color: #8c8c8c; font-size: 12px; }
.select-alert { margin-bottom: 12px; }
.plan-section { margin-top: 16px; }
.plan-section:first-of-type { margin-top: 0; }
.section-title { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; font-size: 13px; font-weight: 700; color: #1a2535; }
.section-period { margin-left: auto; color: #595959; font-weight: 600; white-space: pre; }
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
