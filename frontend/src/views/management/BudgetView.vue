<template>
  <div class="page-wrap">

    <!-- 연도·부서 선택 -->
    <a-card :bordered="false" class="selector-card">
      <a-space size="middle" wrap>
        <span class="sel-label">연도</span>
        <a-select v-model:value="year" style="width:100px" @change="load">
          <a-select-option v-for="y in years" :key="y" :value="y">{{ y }}년</a-select-option>
        </a-select>
        <span class="sel-label">부서</span>
        <a-select v-model:value="filterDept" allow-clear placeholder="전체 부서" style="width:160px" @change="load">
          <a-select-option v-for="d in deptList" :key="d" :value="d">{{ d }}</a-select-option>
        </a-select>
        <a-button @click="openAddModal">
          <template #icon><PlusOutlined /></template>항목 추가
        </a-button>
      </a-space>
    </a-card>

    <!-- 통계 카드 -->
    <a-row :gutter="16">
      <a-col :flex="1" v-for="s in statsCards" :key="s.key">
        <a-card :bordered="false" class="stat-card" :class="s.cls">
          <div class="stat-inner">
            <div>
              <div class="stat-label">{{ s.label }}</div>
              <div class="stat-value" :style="`color:${s.color}`">{{ s.value }}<span class="stat-unit">백만</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 예산 테이블 (부서·항목별) -->
    <a-card :bordered="false" class="table-card">
      <template #title><span class="card-title">{{ year }}년 부서별 예산 현황</span></template>
      <a-table :columns="columns" :data-source="grouped" :loading="loading"
               :pagination="false" size="middle" :scroll="{ x: 900 }"
               :row-class-name="r => r.isDeptRow ? 'dept-row' : ''">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'department'">
            <b v-if="record.isDeptRow">{{ record.department }}</b>
            <span v-else class="indent-text">{{ record.category }}</span>
          </template>
          <template v-if="['q1','q2','q3','q4','total'].includes(column.key)">
            <span :class="record.isDeptRow ? 'num-bold' : ''">
              {{ record[column.key] > 0 ? fmtM(record[column.key]) : '—' }}
            </span>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag v-if="!record.isDeptRow" :color="statusColor[record.status]">{{ record.status }}</a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-space v-if="!record.isDeptRow" size="small">
              <a @click="openEditModal(record)">수정</a>
              <a-divider type="vertical" style="margin:0" />
              <a-popconfirm title="삭제하시겠습니까?" ok-text="삭제" ok-type="danger" cancel-text="취소"
                            @confirm="handleDelete(record.id)">
                <a class="del-link">삭제</a>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 추가/수정 모달 -->
    <a-modal v-model:open="modalOpen" :title="editItem ? '예산 수정' : '예산 항목 추가'"
             width="500px" @ok="handleSave" :confirm-loading="saving" ok-text="저장" cancel-text="취소">
      <a-form :model="form" layout="vertical" ref="formRef" style="margin-top:8px">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="부서" name="department"
              :rules="[{ required: true, message: '부서를 입력하세요.' }]">
              <a-auto-complete v-model:value="form.department" :options="deptOptions"
                               placeholder="부서명 입력" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="예산 항목" name="category"
              :rules="[{ required: true, message: '항목을 선택하세요.' }]">
              <a-select v-model:value="form.category">
                <a-select-option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="1Q (원)"><a-input-number v-model:value="form.q1" style="width:100%" :min="0" :formatter="fmtNum" :parser="parseNum" /></a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="2Q (원)"><a-input-number v-model:value="form.q2" style="width:100%" :min="0" :formatter="fmtNum" :parser="parseNum" /></a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="3Q (원)"><a-input-number v-model:value="form.q3" style="width:100%" :min="0" :formatter="fmtNum" :parser="parseNum" /></a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="4Q (원)"><a-input-number v-model:value="form.q4" style="width:100%" :min="0" :formatter="fmtNum" :parser="parseNum" /></a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="상태" name="status">
              <a-select v-model:value="form.status">
                <a-select-option v-for="s in ['작성중','확정','승인']" :key="s" :value="s">{{ s }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="비고" name="notes"><a-input v-model:value="form.notes" /></a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { managementApi } from '@/api'

const CATEGORIES = ["매출목표", "재료비", "노무비", "외주비", "경비", "판관비", "기타"]
const statusColor = { 작성중: 'default', 확정: 'blue', 승인: 'green' }

const now = new Date()
const years = Array.from({ length: 5 }, (_, i) => now.getFullYear() - 1 + i)

const items = ref([]), deptList = ref([])
const year = ref(now.getFullYear()), filterDept = ref(null)
const loading = ref(false), saving = ref(false)
const modalOpen = ref(false), editItem = ref(null), formRef = ref()

const emptyForm = { budget_year: now.getFullYear(), department: '', category: '재료비', q1: 0, q2: 0, q3: 0, q4: 0, status: '작성중', notes: '' }
const form = reactive({ ...emptyForm })

const fmtM = v => v > 0 ? Math.round(v / 1_000_000).toLocaleString() : '0'
const fmtNum = v => v ? Number(v).toLocaleString() : ''
const parseNum = v => v.replace(/,/g, '')

const deptOptions = computed(() => deptList.value.map(d => ({ value: d })))

// 부서별 그룹핑 (소계 행 포함)
const grouped = computed(() => {
  const deptMap = {}
  items.value.forEach(r => {
    if (!deptMap[r.department]) deptMap[r.department] = []
    deptMap[r.department].push(r)
  })
  const rows = []
  Object.entries(deptMap).forEach(([dept, list]) => {
    const subtotal = list.reduce((s, r) => ({ q1: s.q1 + r.q1, q2: s.q2 + r.q2, q3: s.q3 + r.q3, q4: s.q4 + r.q4, total: s.total + r.total }), { q1: 0, q2: 0, q3: 0, q4: 0, total: 0 })
    rows.push({ key: `dept-${dept}`, department: dept, ...subtotal, isDeptRow: true })
    list.forEach(r => rows.push({ ...r, key: r.id }))
  })
  return rows
})

const statsCards = computed(() => {
  const all = items.value
  const total   = all.reduce((s, r) => s + r.total, 0)
  const revenue = all.filter(r => r.category === '매출목표').reduce((s, r) => s + r.total, 0)
  const cost    = all.filter(r => r.category !== '매출목표').reduce((s, r) => s + r.total, 0)
  return [
    { key: 'rev',  label: '연간 매출목표', value: fmtM(revenue), color: '#1677ff', cls: 'stat-blue' },
    { key: 'cost', label: '연간 비용예산', value: fmtM(cost),    color: '#fa8c16', cls: 'stat-orange' },
    { key: 'total',label: '전체 예산합계', value: fmtM(total),   color: '#1a2535', cls: '' },
    { key: 'dept', label: '등록 부서 수',  value: Object.keys(grouped.value.filter(r => r.isDeptRow).reduce((a, r) => ({ ...a, [r.department]: 1 }), {})).length + '개', color: '#722ed1', cls: 'stat-purple' },
  ]
})

const columns = [
  { title: '부서 / 항목', key: 'department',  width: 180, align: 'center' },
  { title: '1Q',         key: 'q1',           width: 120, align: 'right' },
  { title: '2Q',         key: 'q2',           width: 120, align: 'right' },
  { title: '3Q',         key: 'q3',           width: 120, align: 'right' },
  { title: '4Q',         key: 'q4',           width: 120, align: 'right' },
  { title: '연간 합계',  key: 'total',        width: 130, align: 'right' },
  { title: '상태',       key: 'status',       width: 80,  align: 'center' },
  { title: '관리',       key: 'action',       width: 100, align: 'center', fixed: 'right' },
]

async function load() {
  loading.value = true
  try {
    const [res, depts] = await Promise.all([
      managementApi.getDeptBudgets(year.value, filterDept.value),
      managementApi.getDeptList(year.value),
    ])
    items.value = res.data; deptList.value = depts.data || []
  } finally { loading.value = false }
}

function openAddModal() {
  editItem.value = null
  Object.assign(form, { ...emptyForm, budget_year: year.value })
  modalOpen.value = true
}
function openEditModal(item) {
  editItem.value = item
  Object.assign(form, { ...item })
  modalOpen.value = true
}

async function handleSave() {
  try {
    await formRef.value.validate(); saving.value = true
    await managementApi.upsertDeptBudget({ ...form, budget_year: year.value })
    message.success(editItem.value ? '수정되었습니다.' : '등록되었습니다.')
    modalOpen.value = false; load()
  } catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') }
  finally { saving.value = false }
}

async function handleDelete(id) {
  try { await managementApi.deleteDeptBudget(id); message.success('삭제되었습니다.'); load() }
  catch (e) { message.error(e.response?.data?.detail || '삭제 오류') }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.selector-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.sel-label { font-size: 13px; font-weight: 600; color: #595959; }
.stat-card   { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue   { border-left-color: #1677ff; } .stat-orange { border-left-color: #fa8c16; }
.stat-purple { border-left-color: #722ed1; }
.stat-inner  { display: flex; align-items: center; gap: 14px; }
.stat-label  { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value  { font-size: 22px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit   { font-size: 11px; font-weight: 400; margin-left: 2px; color: #8c8c8c; }
.table-card  { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title  { font-size: 15px; font-weight: 600; color: #1a2535; }
.num-bold    { font-weight: 700; }
.indent-text { padding-left: 16px; color: #595959; }
.del-link    { color: #e74c3c; } .del-link:hover { color: #c0392b; }
:deep(.dept-row td) { background: #fafafa; }
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
