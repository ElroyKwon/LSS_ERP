<template>
  <div class="page-wrap">
    <a-row :gutter="16">
      <a-col :flex="1" v-for="card in statCards" :key="card.key">
        <a-card :bordered="false" class="stat-card" :class="card.cls">
          <div class="stat-inner">
            <div>
              <div class="stat-label">{{ card.label }}</div>
              <div class="stat-value" :style="`color:${card.color}`">
                {{ card.value }}<span class="stat-unit">{{ card.unit }}</span>
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-card :bordered="false" class="table-card">
      <template #title><span class="card-title">채무관리</span></template>
      <template #extra>
        <a-space>
          <a-radio-group v-model:value="filterRange" button-style="solid" size="small">
            <a-radio-button value="all">전체</a-radio-button>
            <a-radio-button value="overdue">연체</a-radio-button>
            <a-radio-button value="d30">30일 이내</a-radio-button>
            <a-radio-button value="unpaid">미지급</a-radio-button>
          </a-radio-group>
          <a-button :loading="loading" @click="load">
            <template #icon><ReloadOutlined /></template>새로고침
          </a-button>
          <a-button type="primary" :loading="adding" @click="addRow">
            <template #icon><PlusOutlined /></template>행 추가
          </a-button>
        </a-space>
      </template>

      <a-table
        :columns="columns"
        :data-source="displayItems"
        :loading="loading"
        :pagination="clientPagination"
        row-key="id"
        size="middle"
        :scroll="{ x: 3300 }"
        :row-class-name="record => record.overdue ? 'row-overdue' : ''"
      
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="TEXT_FIELDS.includes(column.key)">
            <a-input
              v-model:value="record[column.key]"
              class="cell-control"
              @blur="saveInline(record)"
              @pressEnter="saveInline(record)"
            />
          </template>

          <template v-else-if="DATE_FIELDS.includes(column.key)">
            <a-date-picker
              v-model:value="record[column.key]"
              class="cell-control"
              value-format="YYYY-MM-DD"
              @change="saveInline(record)"
            />
          </template>

          <template v-else-if="AMOUNT_INPUT_FIELDS.includes(column.key)">
            <a-input-number
              v-model:value="record[column.key]"
              class="cell-control"
              :min="0"
              :formatter="formatInputAmount"
              :parser="parseAmount"
              @focus="clearZero(record, column.key)"
              @blur="saveInline(record)"
              @pressEnter="saveInline(record)"
            />
          </template>

          <template v-else-if="column.key === 'purchase_type'">
            <a-select v-model:value="record.purchase_type" class="cell-control" allow-clear @change="saveInline(record)">
              <a-select-option v-for="type in PURCHASE_TYPES" :key="type" :value="type">{{ type }}</a-select-option>
            </a-select>
          </template>

          <template v-else-if="column.key === 'subcontract_type'">
            <a-select v-model:value="record.subcontract_type" class="cell-control" allow-clear @change="saveInline(record)">
              <a-select-option v-for="type in SUBCONTRACT_TYPES" :key="type" :value="type">{{ type }}</a-select-option>
            </a-select>
          </template>

          <template v-else-if="column.key === 'payment_type'">
            <a-select v-model:value="record.payment_type" class="cell-control" allow-clear @change="saveInline(record)">
              <a-select-option v-for="type in PAYMENT_TYPES" :key="type" :value="type">{{ type }}</a-select-option>
            </a-select>
          </template>

          <template v-else-if="AMOUNT_DISPLAY_FIELDS.includes(column.key)">
            <span class="num-cell">{{ formatAmount(record[column.key]) }}</span>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { managementApi } from '@/api'
import { createClientPagination } from '@/utils/pagination'

const clientPagination = createClientPagination()
const PURCHASE_TYPES = ['자재', '외주', '안전', '기타']
const SUBCONTRACT_TYPES = ['하도급', '비하도급']
const PAYMENT_TYPES = ['현금', '어음', '현금+어음', '기타']

const TEXT_FIELDS = [
  'job_no',
  'contract_name',
  'vendor_name',
  'payment_terms',
  'collection_terms',
  'related_revenue_no',
  'related_revenue_collection_method',
]
const DATE_FIELDS = [
  'debt_date',
  'related_revenue_collection_date',
  'payment_due_date',
  'actual_payment_date',
  'note_maturity_date',
]
const AMOUNT_INPUT_FIELDS = [
  'debt_amount',
  'contract_amount_ex_vat',
  'contract_amount',
  'cash_paid_amount',
  'note_issued_amount',
]
const AMOUNT_DISPLAY_FIELDS = [
  ...AMOUNT_INPUT_FIELDS,
  'payment_amount',
  'payable_balance',
]

const loading = ref(false)
const adding = ref(false)
const filterRange = ref('all')
const items = ref([])

const emptyForm = {
  job_no: '',
  contract_name: '',
  vendor_name: '',
  debt_date: null,
  debt_amount: null,
  contract_amount_ex_vat: null,
  contract_amount: null,
  purchase_type: null,
  subcontract_type: null,
  payment_terms: '',
  collection_terms: '',
  related_revenue_no: '',
  related_revenue: null,
  related_revenue_collection_date: null,
  related_revenue_collection_method: '',
  payment_due_date: null,
  actual_payment_date: null,
  payment_type: null,
  cash_paid_amount: null,
  note_issued_amount: null,
  note_maturity_date: null,
  payment_amount: 0,
  payable_balance: 0,
}

const columns = [
  { title: 'JOB NO', key: 'job_no', dataIndex: 'job_no', width: 130, align: 'center', fixed: 'left' },
  { title: '계약명', key: 'contract_name', dataIndex: 'contract_name', width: 200, align: 'center', ellipsis: true },
  { title: '구매업체', key: 'vendor_name', dataIndex: 'vendor_name', width: 170, align: 'center', ellipsis: true },
  { title: '채무발생일', key: 'debt_date', dataIndex: 'debt_date', width: 145, align: 'center' },
  { title: '채무금액', key: 'debt_amount', dataIndex: 'debt_amount', width: 140, align: 'right' },
  { title: '계약금(VAT제외)', key: 'contract_amount_ex_vat', dataIndex: 'contract_amount_ex_vat', width: 155, align: 'right' },
  { title: '계약금액', key: 'contract_amount', dataIndex: 'contract_amount', width: 140, align: 'right' },
  { title: '매입구분', key: 'purchase_type', dataIndex: 'purchase_type', width: 110, align: 'center' },
  { title: '하도급/비하도급', key: 'subcontract_type', dataIndex: 'subcontract_type', width: 140, align: 'center' },
  { title: '지불조건', key: 'payment_terms', dataIndex: 'payment_terms', width: 170, align: 'center', ellipsis: true },
  { title: '수금조건', key: 'collection_terms', dataIndex: 'collection_terms', width: 170, align: 'center', ellipsis: true },
  { title: '관련매출', key: 'related_revenue_no', dataIndex: 'related_revenue_no', width: 140, align: 'center', ellipsis: true },
  { title: '관련매출 수금일', key: 'related_revenue_collection_date', dataIndex: 'related_revenue_collection_date', width: 150, align: 'center' },
  { title: '관련매출 수금방법', key: 'related_revenue_collection_method', dataIndex: 'related_revenue_collection_method', width: 160, align: 'center' },
  { title: '지급예정일', key: 'payment_due_date', dataIndex: 'payment_due_date', width: 145, align: 'center' },
  { title: '실 지급일', key: 'actual_payment_date', dataIndex: 'actual_payment_date', width: 145, align: 'center' },
  { title: '지급구분', key: 'payment_type', dataIndex: 'payment_type', width: 110, align: 'center' },
  { title: '현금지급액', key: 'cash_paid_amount', dataIndex: 'cash_paid_amount', width: 140, align: 'right' },
  { title: '어음발행금액', key: 'note_issued_amount', dataIndex: 'note_issued_amount', width: 145, align: 'right' },
  { title: '어음만기일', key: 'note_maturity_date', dataIndex: 'note_maturity_date', width: 145, align: 'center' },
  { title: '지급액', key: 'payment_amount', dataIndex: 'payment_amount', width: 135, align: 'right' },
  { title: '채무잔액', key: 'payable_balance', dataIndex: 'payable_balance', width: 140, align: 'right' },
]

const displayItems = computed(() => {
  if (filterRange.value === 'overdue') return items.value.filter(row => row.overdue)
  if (filterRange.value === 'd30') {
    return items.value.filter(row => !row.overdue && row.days_left != null && row.days_left <= 30 && Number(row.payable_balance || 0) > 0)
  }
  if (filterRange.value === 'unpaid') return items.value.filter(row => Number(row.payable_balance || 0) > 0)
  return items.value
})

const statCards = computed(() => {
  const totalDebt = items.value.reduce((sum, row) => sum + Number(row.debt_amount || 0), 0)
  const balance = items.value.reduce((sum, row) => sum + Number(row.payable_balance || 0), 0)
  const overdue = items.value.filter(row => row.overdue).reduce((sum, row) => sum + Number(row.payable_balance || 0), 0)
  const due30 = items.value.filter(row => !row.overdue && row.days_left != null && row.days_left <= 30)
    .reduce((sum, row) => sum + Number(row.payable_balance || 0), 0)
  return [
    { key: 'total', label: '채무금액 합계', value: formatAmount(totalDebt), unit: '원', color: '#1677ff', cls: 'stat-blue' },
    { key: 'balance', label: '채무잔액', value: formatAmount(balance), unit: '원', color: '#fa8c16', cls: 'stat-orange' },
    { key: 'overdue', label: '연체금액', value: formatAmount(overdue), unit: '원', color: '#f5222d', cls: 'stat-red' },
    { key: 'due30', label: '30일 이내 지급예정', value: formatAmount(due30), unit: '원', color: '#722ed1', cls: 'stat-purple' },
  ]
})

function formatAmount(value) {
  return Number(value || 0).toLocaleString()
}

function formatInputAmount(value) {
  if (value === null || value === undefined || value === '') return ''
  return `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

function parseAmount(value) {
  return String(value || '').replace(/,/g, '')
}

function clearZero(row, key) {
  if (Number(row[key]) === 0) row[key] = null
}

function normalizeRow(row) {
  const normalized = { ...emptyForm, ...row }
  normalized.payment_amount = Number(normalized.cash_paid_amount || 0) + Number(normalized.note_issued_amount || 0)
  if (normalized.actual_payment_date && normalized.payment_type === '현금') {
    normalized.cash_paid_amount = Number(normalized.debt_amount || 0)
    normalized.note_issued_amount = 0
    normalized.payment_amount = Number(normalized.debt_amount || 0)
  } else if (normalized.actual_payment_date && normalized.payment_type === '어음') {
    normalized.cash_paid_amount = 0
    normalized.note_issued_amount = Number(normalized.debt_amount || 0)
    normalized.payment_amount = Number(normalized.debt_amount || 0)
  }
  normalized.payable_balance = Math.max(Number(normalized.debt_amount || 0) - normalized.payment_amount, 0)
  return normalized
}

function toPayload(row) {
  const normalized = normalizeRow(row)
  const paymentAmount = Number(normalized.cash_paid_amount || 0) + Number(normalized.note_issued_amount || 0)
  return {
    job_no: normalized.job_no || '',
    contract_name: normalized.contract_name || '',
    vendor_name: normalized.vendor_name || '',
    debt_date: normalized.debt_date || null,
    debt_amount: Number(normalized.debt_amount || 0),
    contract_amount_ex_vat: Number(normalized.contract_amount_ex_vat || 0),
    contract_amount: Number(normalized.contract_amount || 0),
    purchase_type: normalized.purchase_type || null,
    subcontract_type: normalized.subcontract_type || null,
    payment_terms: normalized.payment_terms || '',
    collection_terms: normalized.collection_terms || '',
    related_revenue_no: normalized.related_revenue_no || '',
    related_revenue: Number(normalized.related_revenue || 0),
    related_revenue_collection_date: normalized.related_revenue_collection_date || null,
    related_revenue_collection_method: normalized.related_revenue_collection_method || '',
    payment_due_date: normalized.payment_due_date || null,
    actual_payment_date: normalized.actual_payment_date || null,
    payment_type: normalized.payment_type || null,
    cash_paid_amount: Number(normalized.cash_paid_amount || 0),
    note_issued_amount: Number(normalized.note_issued_amount || 0),
    note_maturity_date: normalized.note_maturity_date || null,
    payment_amount: paymentAmount,
    notes: normalized.notes || '',
  }
}

async function load() {
  loading.value = true
  try {
    const res = await managementApi.getPayables()
    items.value = (res.data?.items || []).map(normalizeRow)
  } finally {
    loading.value = false
  }
}

async function saveInline(row) {
  if (!row.id) return
  Object.assign(row, normalizeRow(row))
  try {
    const res = await managementApi.updatePayable(row.id, toPayload(row))
    Object.assign(row, normalizeRow(res.data))
  } catch (e) {
    message.error(e.response?.data?.detail || '채무 정보 저장 오류')
    load()
  }
}

async function addRow() {
  adding.value = true
  try {
    const res = await managementApi.createPayable(toPayload(emptyForm))
    items.value = [normalizeRow(res.data), ...items.value]
    message.success('테이블에 채무 행이 추가되었습니다.')
  } catch (e) {
    message.error(e.response?.data?.detail || '채무 행 추가 오류')
  } finally {
    adding.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.stat-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue { border-left-color: #1677ff; }
.stat-orange { border-left-color: #fa8c16; }
.stat-red { border-left-color: #f5222d; }
.stat-purple { border-left-color: #722ed1; }
.stat-inner { display: flex; align-items: center; min-height: 58px; }
.stat-label { font-size: 12px; color: #8c8c8c; margin-bottom: 4px; }
.stat-value { font-size: 22px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit { font-size: 12px; font-weight: 400; margin-left: 3px; color: #8c8c8c; }
.table-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size: 15px; font-weight: 600; color: #1a2535; }
.cell-control { width: 100%; }
.num-cell { font-weight: 600; }
:deep(.row-overdue td) { background: #fff1f0 !important; }
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
:deep(.ant-table-cell) { white-space: nowrap; }
</style>
