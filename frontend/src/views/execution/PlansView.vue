<template>
  <div class="page-wrap">

    <!-- 프로젝트·연도 선택 -->
    <a-card :bordered="false" class="selector-card">
      <a-space size="middle" wrap>
        <span class="sel-label">프로젝트</span>
        <a-select v-model:value="selectedProjectId" show-search allow-clear
                  placeholder="프로젝트 선택" style="width:320px"
                  :options="projectOptions" option-filter-prop="label"
                  @change="loadPlans" />
        <span class="sel-label">연도</span>
        <a-select v-model:value="selectedYear" style="width:100px" @change="loadPlans">
          <a-select-option v-for="y in years" :key="y" :value="y">{{ y }}년</a-select-option>
        </a-select>
      </a-space>
      <div v-if="selectedProject" class="proj-info">
        <a-tag :color="statusColor[selectedProject.status]">{{ selectedProject.status }}</a-tag>
        {{ selectedProject.client_name || '—' }}
        <span v-if="selectedProject.contract_amount > 0">
          · 계약금액 <b>{{ Number(selectedProject.contract_amount).toLocaleString() }}</b>원
        </span>
      </div>
    </a-card>

    <!-- 통계 요약 -->
    <a-row :gutter="16" v-if="selectedProjectId">
      <a-col :flex="1" v-for="s in summaryCards" :key="s.key">
        <a-card :bordered="false" class="stat-card" :class="s.cls">
          <div class="stat-inner">
            <div>
              <div class="stat-label">{{ s.label }}</div>
              <div class="stat-value" :style="`color:${s.color}`">
                {{ s.value }}<span class="stat-unit">백만</span>
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 월별 계획 테이블 -->
    <a-card :bordered="false" class="table-card" v-if="selectedProjectId">
      <template #title><span class="card-title">{{ selectedYear }}년 월별 매출 · 투입 계획</span></template>
      <template #extra>
        <a-button type="primary" size="small" @click="openBulkModal">
          <template #icon><EditOutlined /></template>일괄 계획 입력
        </a-button>
      </template>

      <a-table :columns="planCols" :data-source="planRows" :loading="planLoading"
               :pagination="false" size="middle" :scroll="{ x: 900 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'month'">
            <b>{{ record.month }}월</b>
          </template>
          <template v-if="['revenue_plan','material_plan','labor_plan','subcontract_plan','expense_plan','cost_total'].includes(column.key)">
            <span :class="record.isTotal ? 'num-bold' : ''">
              {{ record[column.key] > 0 ? fmtM(record[column.key]) : '—' }}
            </span>
          </template>
          <template v-if="column.key === 'action'">
            <a v-if="!record.isTotal" @click="openPlanModal(record)">입력</a>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-empty v-else description="프로젝트를 선택해주세요." style="margin-top:80px" />

    <!-- 월별 계획 입력 모달 -->
    <a-modal v-model:open="planModalOpen" :title="`${editPlan.month}월 계획 입력`"
             width="480px" @ok="savePlan" :confirm-loading="saving" ok-text="저장" cancel-text="취소">
      <a-form layout="vertical" style="margin-top:8px">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="매출 계획 (원)">
              <a-input-number v-model:value="editPlan.revenue_plan" style="width:100%"
                              :min="0" :formatter="fmtNum" :parser="parseNum" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="재료비 (원)">
              <a-input-number v-model:value="editPlan.material_plan" style="width:100%"
                              :min="0" :formatter="fmtNum" :parser="parseNum" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="노무비 (원)">
              <a-input-number v-model:value="editPlan.labor_plan" style="width:100%"
                              :min="0" :formatter="fmtNum" :parser="parseNum" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="외주비 (원)">
              <a-input-number v-model:value="editPlan.subcontract_plan" style="width:100%"
                              :min="0" :formatter="fmtNum" :parser="parseNum" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="경비 (원)">
              <a-input-number v-model:value="editPlan.expense_plan" style="width:100%"
                              :min="0" :formatter="fmtNum" :parser="parseNum" />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="비고">
              <a-input v-model:value="editPlan.notes" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { message } from 'ant-design-vue'
import { EditOutlined } from '@ant-design/icons-vue'
import { executionApi } from '@/api'

const now = new Date()
const years = Array.from({ length: 5 }, (_, i) => now.getFullYear() - 1 + i)

const projects         = ref([])
const selectedProjectId = ref(null)
const selectedYear      = ref(now.getFullYear())
const planRows          = ref([])
const planLoading       = ref(false)
const planModalOpen     = ref(false)
const saving            = ref(false)

const statusColor = { 미진행: 'orange', 진행중: 'blue', 완료: 'green' }

const editPlan = reactive({
  month: 1, revenue_plan: 0, material_plan: 0,
  labor_plan: 0, subcontract_plan: 0, expense_plan: 0, notes: '',
})

const projectOptions = computed(() =>
  projects.value.map(p => ({ value: p.id, label: `[${p.project_no || '—'}] ${p.project_name}` }))
)
const selectedProject = computed(() =>
  projects.value.find(p => p.id === selectedProjectId.value) || null
)

const fmtM = (v) => v > 0 ? Math.round(v / 1_000_000).toLocaleString() : '0'
const fmtNum = (v) => v ? Number(v).toLocaleString() : ''
const parseNum = (v) => v.replace(/,/g, '')

// 연간 합계
const totals = computed(() => {
  const rows = planRows.value.filter(r => !r.isTotal)
  return {
    revenue_plan:     rows.reduce((s, r) => s + (r.revenue_plan || 0), 0),
    material_plan:    rows.reduce((s, r) => s + (r.material_plan || 0), 0),
    labor_plan:       rows.reduce((s, r) => s + (r.labor_plan || 0), 0),
    subcontract_plan: rows.reduce((s, r) => s + (r.subcontract_plan || 0), 0),
    expense_plan:     rows.reduce((s, r) => s + (r.expense_plan || 0), 0),
  }
})

const summaryCards = computed(() => {
  const t = totals.value
  const costTotal = t.material_plan + t.labor_plan + t.subcontract_plan + t.expense_plan
  const margin = t.revenue_plan > 0 ? ((t.revenue_plan - costTotal) / t.revenue_plan * 100).toFixed(1) : 0
  return [
    { key: 'rev',  label: '연간 매출 계획', value: fmtM(t.revenue_plan), color: '#1677ff', cls: 'stat-blue' },
    { key: 'cost', label: '연간 투입 계획', value: fmtM(costTotal),       color: '#fa8c16', cls: 'stat-orange' },
    { key: 'gp',   label: '계획 이익',      value: fmtM(t.revenue_plan - costTotal), color: '#52c41a', cls: 'stat-green' },
    { key: 'rate', label: '계획 이익률',    value: margin + '%',          color: '#722ed1', cls: 'stat-purple' },
  ]
})

const planCols = [
  { title: '월',      key: 'month',            width: 65,  align: 'center' },
  { title: '매출 계획', key: 'revenue_plan',   width: 110, align: 'right' },
  { title: '재료비',  key: 'material_plan',    width: 110, align: 'right' },
  { title: '노무비',  key: 'labor_plan',       width: 110, align: 'right' },
  { title: '외주비',  key: 'subcontract_plan', width: 110, align: 'right' },
  { title: '경비',    key: 'expense_plan',     width: 100, align: 'right' },
  { title: '투입 합계', key: 'cost_total',     width: 120, align: 'right' },
  { title: '입력',    key: 'action',           width: 70,  align: 'center', fixed: 'right' },
]

async function loadProjects() {
  const res = await executionApi.getProjects()
  projects.value = res.data
}

async function loadPlans() {
  if (!selectedProjectId.value) return
  planLoading.value = true
  try {
    const res = await executionApi.getProjectPlans(selectedProjectId.value, selectedYear.value)
    const map = {}
    res.data.forEach(r => { map[r.plan_month] = r })
    planRows.value = Array.from({ length: 12 }, (_, i) => {
      const m = i + 1
      const r = map[m] || {}
      const cost = (r.material_plan || 0) + (r.labor_plan || 0) + (r.subcontract_plan || 0) + (r.expense_plan || 0)
      return {
        month: m,
        revenue_plan:     r.revenue_plan     || 0,
        material_plan:    r.material_plan    || 0,
        labor_plan:       r.labor_plan       || 0,
        subcontract_plan: r.subcontract_plan || 0,
        expense_plan:     r.expense_plan     || 0,
        cost_total:       cost,
        notes:            r.notes || '',
        isTotal: false,
      }
    })
    // 합계 행
    const t = totals.value
    planRows.value.push({
      month: '합계', isTotal: true,
      revenue_plan:     t.revenue_plan,
      material_plan:    t.material_plan,
      labor_plan:       t.labor_plan,
      subcontract_plan: t.subcontract_plan,
      expense_plan:     t.expense_plan,
      cost_total: t.material_plan + t.labor_plan + t.subcontract_plan + t.expense_plan,
    })
  } finally { planLoading.value = false }
}

function openPlanModal(record) {
  Object.assign(editPlan, {
    month:            record.month,
    revenue_plan:     record.revenue_plan,
    material_plan:    record.material_plan,
    labor_plan:       record.labor_plan,
    subcontract_plan: record.subcontract_plan,
    expense_plan:     record.expense_plan,
    notes:            record.notes || '',
  })
  planModalOpen.value = true
}

function openBulkModal() {
  message.info('월별로 "입력" 버튼을 눌러 각 월의 계획을 입력하세요.')
}

async function savePlan() {
  saving.value = true
  try {
    await executionApi.upsertProjectPlan({
      project_id:       selectedProjectId.value,
      plan_year:        selectedYear.value,
      plan_month:       editPlan.month,
      revenue_plan:     editPlan.revenue_plan || 0,
      material_plan:    editPlan.material_plan || 0,
      labor_plan:       editPlan.labor_plan || 0,
      subcontract_plan: editPlan.subcontract_plan || 0,
      expense_plan:     editPlan.expense_plan || 0,
      notes:            editPlan.notes,
    })
    message.success(`${editPlan.month}월 계획이 저장되었습니다.`)
    planModalOpen.value = false
    await loadPlans()
  } catch (e) {
    message.error(e.response?.data?.detail || '저장 중 오류가 발생했습니다.')
  } finally { saving.value = false }
}

onMounted(loadProjects)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.selector-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.sel-label { font-size: 13px; font-weight: 600; color: #595959; }
.proj-info { margin-top: 10px; font-size: 13px; color: #595959; }

.stat-card   { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue   { border-left-color: #1677ff; }
.stat-orange { border-left-color: #fa8c16; }
.stat-green  { border-left-color: #52c41a; }
.stat-purple { border-left-color: #722ed1; }
.stat-inner  { display: flex; align-items: center; gap: 14px; }
.stat-label  { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value  { font-size: 22px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit   { font-size: 11px; font-weight: 400; margin-left: 2px; color: #8c8c8c; }

.table-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size: 15px; font-weight: 600; color: #1a2535; }
.num-bold   { font-weight: 700; }

:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-table-tbody > tr:last-child td) { background: #f5f5f5; font-weight: 600; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
