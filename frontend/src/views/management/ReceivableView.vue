<template>
  <div class="page-wrap">
    <a-row :gutter="16">
      <a-col :flex="1" v-for="card in statCards" :key="card.key">
        <a-card :bordered="false" class="stat-card" :class="card.cls">
          <div class="stat-inner">
            <div>
              <div class="stat-label">{{ card.label }}</div>
              <div class="stat-value" :style="`color:${card.color}`">
                {{ card.value }}<span class="stat-unit">{{ card.unit || '원' }}</span>
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-card :bordered="false" class="table-card">
      <template #title><span class="card-title">채권관리</span></template>
      <template #extra>
        <a-space>
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
        :data-source="items"
        :loading="loading"
        :pagination="clientPagination"
        row-key="id"
        size="middle"
        :scroll="{ x: 2740 }"
      
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'receivable_type'">
            <a-select v-model:value="record.receivable_type" class="cell-control" @change="saveInline(record)">
              <a-select-option v-for="type in RECEIVABLE_TYPES" :key="type" :value="type">{{ type }}</a-select-option>
            </a-select>
          </template>
          <template v-else-if="isManualRow(record) && TEXT_FIELDS.includes(column.dataIndex)">
            <a-input v-model:value="record[column.dataIndex]" class="cell-control" @blur="saveInline(record)" @pressEnter="saveInline(record)" />
          </template>
          <template v-else-if="column.key === 'due_date'">
            <a-date-picker v-model:value="record.due_date" class="cell-control" value-format="YYYY-MM-DD" @change="saveInline(record)" />
          </template>
          <template v-else-if="isManualRow(record) && column.key === 'sales_date'">
            <a-date-picker v-model:value="record.sales_date" class="cell-control" value-format="YYYY-MM-DD" @change="saveInline(record)" />
          </template>
          <template v-else-if="isManualRow(record) && column.key === 'amount'">
            <a-input-number v-model:value="record.amount" class="cell-control" :min="0" :formatter="formatInputAmount" :parser="parseAmount" @blur="saveInline(record)" @pressEnter="saveInline(record)" />
          </template>
          <template v-else-if="column.key === 'amount' || column.key === 'bad_debt_allowance'">
            {{ formatAmount(record[column.key]) }}
          </template>
          <template v-else-if="column.key === 'age_months'">
            {{ record.due_date ? record.age_months : '-' }}
          </template>
          <template v-else-if="column.key === 'bad_debt_rate'">
            {{ Number(record.bad_debt_rate || 0) * 100 }}%
          </template>
          <template v-else-if="column.key === 'customer_class'">
            <a-select v-model:value="record.customer_class" class="cell-control" @change="saveInline(record)">
              <a-select-option v-for="type in CUSTOMER_CLASSES" :key="type" :value="type">{{ type }}</a-select-option>
            </a-select>
          </template>
          <template v-else-if="column.key === 'collection_date'">
            <a-date-picker v-model:value="record.collection_date" class="cell-control" value-format="YYYY-MM-DD" @change="saveInline(record)" />
          </template>
          <template v-else-if="column.key === 'note_maturity_date'">
            <a-date-picker v-model:value="record.note_maturity_date" class="cell-control" value-format="YYYY-MM-DD" @change="saveInline(record)" />
          </template>
          <template v-else-if="column.key === 'note_issuer'">
            <a-input v-model:value="record.note_issuer" class="cell-control" @blur="saveInline(record)" @pressEnter="saveInline(record)" />
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
const RECEIVABLE_TYPES = ['외상매출금', '받을어음']
const CUSTOMER_CLASSES = ['특수관계자', '대리점', '일반']
const TEXT_FIELDS = [
  'business_division',
  'job_no',
  'department',
  'client_name',
  'project_name',
  'sales_manager',
  'construction_manager',
  'collection_terms',
]

const loading = ref(false)
const adding = ref(false)
const items = ref([])

const emptyForm = {
  receivable_type: '외상매출금',
  business_division: '',
  job_no: '',
  department: '',
  client_name: '',
  project_name: '',
  sales_manager: '',
  construction_manager: '',
  collection_terms: '',
  due_date: null,
  sales_date: null,
  amount: null,
  customer_class: '일반',
  collection_date: null,
  note_maturity_date: null,
  note_issuer: '',
}
const columns = [
  { title: '구분', key: 'receivable_type', dataIndex: 'receivable_type', width: 130, align: 'center' },
  { title: '사업부', dataIndex: 'business_division', width: 150, align: 'center', ellipsis: true },
  { title: 'JOB NO', dataIndex: 'job_no', width: 120, align: 'center' },
  { title: '부서', dataIndex: 'department', width: 140, align: 'center', ellipsis: true },
  { title: '거래처명', dataIndex: 'client_name', width: 180, align: 'center', ellipsis: true },
  { title: '프로젝트명', dataIndex: 'project_name', width: 220, align: 'center', ellipsis: true },
  { title: '영업담당자', dataIndex: 'sales_manager', width: 110, align: 'center' },
  { title: '공사담당자', dataIndex: 'construction_manager', width: 110, align: 'center' },
  { title: '수금조건', dataIndex: 'collection_terms', width: 180, align: 'center', ellipsis: true },
  { title: '수금예정일', key: 'due_date', dataIndex: 'due_date', width: 145, align: 'center' },
  { title: '매출일', key: 'sales_date', dataIndex: 'sales_date', width: 110, align: 'center' },
  { title: '금액', key: 'amount', dataIndex: 'amount', width: 140, align: 'right' },
  { title: '월령(수금예정일)', key: 'age_months', dataIndex: 'age_months', width: 145, align: 'center' },
  { title: '대손율', key: 'bad_debt_rate', dataIndex: 'bad_debt_rate', width: 90, align: 'center' },
  { title: '대손충당금', key: 'bad_debt_allowance', dataIndex: 'bad_debt_allowance', width: 140, align: 'right' },
  { title: '거래처 분류', key: 'customer_class', dataIndex: 'customer_class', width: 135, align: 'center' },
  { title: '수금일', key: 'collection_date', dataIndex: 'collection_date', width: 145, align: 'center' },
  { title: '어음 만기일', key: 'note_maturity_date', dataIndex: 'note_maturity_date', width: 145, align: 'center' },
  { title: '어음 발행인', key: 'note_issuer', dataIndex: 'note_issuer', width: 160, align: 'center' },
]

const statCards = computed(() => {
  const total = items.value.reduce((sum, row) => sum + Number(row.amount || 0), 0)
  const outstanding = items.value.reduce((sum, row) => sum + Number(row.outstanding_amount || 0), 0)
  const allowance = items.value.reduce((sum, row) => sum + Number(row.bad_debt_allowance || 0), 0)
  const collected = items.value.filter(row => row.collection_date).length
  return [
    { key: 'total', label: '채권 합계', value: formatAmount(total), color: '#1677ff', cls: 'stat-blue' },
    { key: 'outstanding', label: '미수금', value: formatAmount(outstanding), color: '#fa8c16', cls: 'stat-orange' },
    { key: 'allowance', label: '대손충당금', value: formatAmount(allowance), color: '#f5222d', cls: 'stat-red' },
    { key: 'collected', label: '수금완료', value: collected.toLocaleString(), color: '#52c41a', cls: 'stat-green', unit: '건' },
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

function toPayload(row) {
  return {
    receivable_type: row.receivable_type || '외상매출금',
    business_division: row.business_division || '',
    job_no: row.job_no || '',
    department: row.department || '',
    client_name: row.client_name || '',
    project_name: row.project_name || '',
    sales_manager: row.sales_manager || '',
    construction_manager: row.construction_manager || '',
    collection_terms: row.collection_terms || '',
    due_date: row.due_date || null,
    sales_date: row.sales_date || null,
    amount: Number(row.amount || 0),
    customer_class: row.customer_class || '일반',
    collection_date: row.collection_date || null,
    note_maturity_date: row.note_maturity_date || null,
    note_issuer: row.note_issuer || '',
    notes: row.notes || '',
  }
}

function isManualRow(row) {
  return !row.sales_bill_id && !row.billing_id
}

async function load() {
  loading.value = true
  try {
    const res = await managementApi.getReceivables()
    items.value = res.data?.items || []
  } finally {
    loading.value = false
  }
}

async function saveInline(row) {
  if (!row.id) return
  try {
    const res = await managementApi.updateReceivable(row.id, toPayload(row))
    Object.assign(row, res.data)
  } catch (e) {
    message.error(e.response?.data?.detail || '채권 정보 저장 오류')
    load()
  }
}

async function addRow() {
  adding.value = true
  try {
    const res = await managementApi.createReceivable(toPayload(emptyForm))
    items.value = [res.data, ...items.value]
    message.success('테이블에 채권 행이 추가되었습니다.')
  } catch (e) {
    message.error(e.response?.data?.detail || '채권 행 추가 오류')
  } finally {
    adding.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display:flex; flex-direction:column; gap:16px; }
.stat-card { border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,0.07); border-left:4px solid #e0e0e0; }
.stat-blue { border-left-color:#1677ff; }
.stat-green { border-left-color:#52c41a; }
.stat-orange { border-left-color:#fa8c16; }
.stat-red { border-left-color:#f5222d; }
.stat-inner { display:flex; align-items:center; min-height:58px; }
.stat-label { font-size:12px; color:#8c8c8c; margin-bottom:4px; }
.stat-value { font-size:22px; font-weight:700; color:#1a2535; line-height:1.2; }
.stat-unit { font-size:12px; font-weight:400; margin-left:3px; color:#8c8c8c; }
.table-card { border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size:15px; font-weight:600; color:#1a2535; }
.cell-control { width:100%; }
:deep(.ant-table-thead > tr > th) { text-align:center !important; background:#fafafa; }
:deep(.ant-card-head) { border-bottom:1px solid #f0f0f0; min-height:52px; }
</style>
