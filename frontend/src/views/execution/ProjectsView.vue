<template>
  <div class="page-wrap">

    <!-- ── 통계 카드 ── -->
    <a-row :gutter="16">
      <a-col :flex="1" v-for="s in statsCards" :key="s.key">
        <a-card :bordered="false" class="stat-card" :class="s.cls">
          <div class="stat-inner">
            <div class="stat-icon" :class="s.iconCls">
              <component :is="s.icon" />
            </div>
            <div>
              <div class="stat-label">{{ s.label }}</div>
              <div class="stat-value" :style="`color:${s.color}`">
                {{ s.value }}<span class="stat-unit">건</span>
              </div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- ── 검색 조건 ── -->
    <a-card :bordered="false" class="filter-card">
      <table class="filter-table">
        <tbody>
          <tr>
            <th>발주처</th>
            <td>
              <a-input v-model:value="filters.client_name" placeholder="발주처명" allow-clear style="width:180px" />
            </td>
            <th>계약일자</th>
            <td>
              <a-space size="small">
                <a-date-picker v-model:value="filters.contract_from" value-format="YYYY-MM-DD" placeholder="시작" style="width:130px" />
                <span>~</span>
                <a-date-picker v-model:value="filters.contract_to" value-format="YYYY-MM-DD" placeholder="종료" style="width:130px" />
              </a-space>
            </td>
          </tr>
          <tr>
            <th>PM 부서</th>
            <td>
              <a-input v-model:value="filters.pm_dept" placeholder="부서명" allow-clear style="width:180px" />
            </td>
            <th>착공일자</th>
            <td>
              <a-space size="small">
                <a-date-picker v-model:value="filters.construct_from" value-format="YYYY-MM-DD" placeholder="시작" style="width:130px" />
                <span>~</span>
                <a-date-picker v-model:value="filters.construct_to" value-format="YYYY-MM-DD" placeholder="종료" style="width:130px" />
              </a-space>
            </td>
          </tr>
          <tr>
            <th>프로젝트</th>
            <td>
              <a-input v-model:value="filters.search" placeholder="코드 또는 프로젝트명" allow-clear style="width:220px" />
            </td>
            <th>계약금액</th>
            <td>
              <a-space size="small">
                <a-input-number v-model:value="filters.amount_from" :min="0" placeholder="최소"
                  style="width:130px" :formatter="v => v ? Number(v).toLocaleString() : ''"
                  :parser="v => v.replace(/,/g, '')" />
                <span>~</span>
                <a-input-number v-model:value="filters.amount_to" :min="0" placeholder="최대"
                  style="width:130px" :formatter="v => v ? Number(v).toLocaleString() : ''"
                  :parser="v => v.replace(/,/g, '')" />
              </a-space>
            </td>
          </tr>
          <tr>
            <th>진행상태</th>
            <td>
              <a-checkbox-group v-model:value="filters.statuses">
                <a-checkbox value="미진행">미진행</a-checkbox>
                <a-checkbox value="진행중">진행중</a-checkbox>
                <a-checkbox value="완료">완료</a-checkbox>
              </a-checkbox-group>
            </td>
            <th>도급구분</th>
            <td>
              <a-space>
                <a-checkbox-group v-model:value="filters.contract_forms">
                  <a-checkbox value="원도급">원도급</a-checkbox>
                  <a-checkbox value="하도급">하도급</a-checkbox>
                  <a-checkbox value="공동도급">공동도급</a-checkbox>
                </a-checkbox-group>
                <a-divider type="vertical" />
                <a-checkbox-group v-model:value="filters.contract_types">
                  <a-checkbox value="국내">국내</a-checkbox>
                  <a-checkbox value="국외">국외</a-checkbox>
                </a-checkbox-group>
              </a-space>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="filter-footer">
        <span class="filter-count">총 <b>{{ filtered.length }}</b>건</span>
        <a-space>
          <a-button @click="resetFilters">초기화</a-button>
        </a-space>
      </div>
    </a-card>

    <!-- ── 프로젝트 목록 테이블 ── -->
    <a-card :bordered="false" class="table-card">
      <template #title><span class="card-title">프로젝트 리스트</span></template>
      <template #extra>
        <a-button type="primary" @click="openDrawer(null)">
          <template #icon><PlusOutlined /></template>프로젝트 등록
        </a-button>
      </template>

      <a-table
        :columns="columns"
        :data-source="filtered"
        :loading="loading"
        :pagination="{ pageSize: 20, showSizeChanger: true }"
        row-key="id"
        size="middle"
        :scroll="{ x: 1100 }"
        :row-class-name="rowClass"
        @row-click="(record) => handleRowClick(record)"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'project_name'">
            <div class="name-cell">
              <span :class="selectedId === record.id ? 'name-selected' : ''">{{ record.project_name }}</span>
              <a-tag v-if="selectedId === record.id" color="blue" style="margin-left:6px;font-size:10px">선택됨</a-tag>
            </div>
          </template>
          <template v-if="column.key === 'contract_amount'">
            <span class="num-cell">{{ record.contract_amount > 0 ? Number(record.contract_amount).toLocaleString() : '—' }}</span>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor[record.status]">{{ record.status }}</a-tag>
            <a-tooltip v-if="isOverdue(record)" title="착공 종료일이 지났습니다">
              <span class="overdue-mark">⚠</span>
            </a-tooltip>
          </template>
          <template v-if="column.key === 'action'">
            <a-space size="small">
              <a @click.stop="openDrawer(record)">수정</a>
              <a-divider type="vertical" style="margin:0" />
              <a-popconfirm :title="`'${record.project_name}' 을(를) 삭제하시겠습니까?`"
                            ok-text="삭제" ok-type="danger" cancel-text="취소"
                            @confirm="handleDelete(record.id)" @click.stop>
                <a class="del-link">삭제</a>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- ── 등록/수정 Drawer ── -->
    <a-drawer v-model:open="drawerOpen"
              :title="editItem ? '프로젝트 수정' : '프로젝트 등록'"
              width="600"
              :body-style="{ paddingBottom: '72px' }">
      <a-form :model="form" layout="vertical" ref="formRef">

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">기본 정보</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="PJT NO." name="project_no">
              <a-input v-model:value="form.project_no" placeholder="예) PJT-2026-001" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="진행상태" name="status">
              <a-select v-model:value="form.status">
                <a-select-option value="미진행">미진행</a-select-option>
                <a-select-option value="진행중">진행중</a-select-option>
                <a-select-option value="완료">완료</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="프로젝트명" name="project_name"
              :rules="[{ required: true, message: '프로젝트명을 입력하세요.' }]">
              <a-input v-model:value="form.project_name" placeholder="프로젝트명 입력" />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="발주처" name="client_name"
              extra="직접 입력하거나 등록된 거래처를 검색·선택하세요.">
              <a-auto-complete
                v-model:value="form.client_name"
                :options="clientSuggestions"
                placeholder="발주처명 직접 입력 또는 검색"
                allow-clear
                @select="onClientSelect"
                @change="onClientChange"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">계약 현황</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="도급형태" name="contract_form">
              <a-select v-model:value="form.contract_form">
                <a-select-option v-for="f in CONTRACT_FORMS" :key="f" :value="f">{{ f }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="국내/국외" name="contract_type">
              <a-select v-model:value="form.contract_type">
                <a-select-option value="국내">국내</a-select-option>
                <a-select-option value="국외">국외</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="계약 시작일" name="contract_start">
              <a-date-picker v-model:value="form.contract_start" style="width:100%"
                             value-format="YYYY-MM-DD" @change="onContractStartChange" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="계약 종료일" name="contract_end">
              <a-date-picker v-model:value="form.contract_end" style="width:100%"
                             value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="계약금액 (원)" name="contract_amount">
              <a-input-number v-model:value="form.contract_amount" style="width:100%"
                              :min="0" :formatter="v => Number(v).toLocaleString()"
                              :parser="v => v.replace(/,/g, '')" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="도급비율 (%)" name="contract_rate">
              <a-input-number v-model:value="form.contract_rate" style="width:100%"
                              :min="0" :max="100" :step="0.01" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="지역" name="region">
              <a-input v-model:value="form.region" placeholder="공사 지역" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">착공 기간</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="착공 시작일" name="construct_start">
              <a-date-picker v-model:value="form.construct_start" style="width:100%"
                             value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="착공 종료일" name="construct_end">
              <a-date-picker v-model:value="form.construct_end" style="width:100%"
                             value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">담당자</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="담당 PM" name="pm_name">
              <a-input v-model:value="form.pm_name" placeholder="PM 성명" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="PM 부서" name="pm_dept">
              <a-input v-model:value="form.pm_dept" placeholder="부서명" />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="비고" name="notes">
              <a-textarea v-model:value="form.notes" :rows="3" placeholder="특이사항 입력" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>

      <template #footer>
        <div style="text-align:right">
          <a-space>
            <a-button @click="drawerOpen = false">취소</a-button>
            <a-button type="primary" :loading="saving" @click="handleSave">저장</a-button>
          </a-space>
        </div>
      </template>
    </a-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ProjectOutlined, PlayCircleOutlined, CheckCircleOutlined, PauseCircleOutlined, PlusOutlined,
} from '@ant-design/icons-vue'
import { executionApi, masterApi } from '@/api'

const CONTRACT_FORMS = ['원도급', '하도급', '공동도급', '위탁', '기타']

const items     = ref([])
const companies = ref([])
const loading   = ref(false)
const saving    = ref(false)
const drawerOpen = ref(false)
const editItem  = ref(null)
const formRef   = ref()
const selectedId = ref(null)

const statusColor = { 미진행: 'orange', 진행중: 'blue', 완료: 'green' }

// ── 필터 ──
const filters = reactive({
  search: '', client_name: '', pm_dept: '',
  contract_from: null, contract_to: null,
  construct_from: null, construct_to: null,
  amount_from: null, amount_to: null,
  statuses: ['미진행', '진행중', '완료'],
  contract_forms: [],
  contract_types: [],
})

function resetFilters() {
  Object.assign(filters, {
    search: '', client_name: '', pm_dept: '',
    contract_from: null, contract_to: null,
    construct_from: null, construct_to: null,
    amount_from: null, amount_to: null,
    statuses: ['미진행', '진행중', '완료'],
    contract_forms: [], contract_types: [],
  })
}

// ── 클라이언트 필터링 ──
const filtered = computed(() => items.value.filter(d => {
  if (filters.search && !d.project_name?.toLowerCase().includes(filters.search.toLowerCase())
      && !d.project_no?.toLowerCase().includes(filters.search.toLowerCase())) return false
  if (filters.client_name && !d.client_name?.toLowerCase().includes(filters.client_name.toLowerCase())) return false
  if (filters.pm_dept && d.pm_dept !== filters.pm_dept) return false
  if (filters.contract_from && d.contract_start && d.contract_start < filters.contract_from) return false
  if (filters.contract_to   && d.contract_end   && d.contract_end   > filters.contract_to)   return false
  if (filters.construct_from && d.construct_start && d.construct_start < filters.construct_from) return false
  if (filters.construct_to   && d.construct_end   && d.construct_end   > filters.construct_to)   return false
  if (filters.amount_from != null && d.contract_amount < filters.amount_from) return false
  if (filters.amount_to   != null && d.contract_amount > filters.amount_to)   return false
  if (filters.statuses.length < 3 && !filters.statuses.includes(d.status)) return false
  if (filters.contract_forms.length > 0 && !filters.contract_forms.includes(d.contract_form)) return false
  if (filters.contract_types.length > 0 && !filters.contract_types.includes(d.contract_type)) return false
  return true
}))

// ── 통계 카드 ──
const statsCards = computed(() => {
  const all = items.value
  return [
    { key: 'total',   label: '전체 프로젝트', value: all.length,                                         color: '#1a2535', cls: '', iconCls: 'icon-gray', icon: ProjectOutlined },
    { key: 'active',  label: '진행중',        value: all.filter(d => d.status === '진행중').length,  color: '#1677ff', cls: 'stat-blue',   iconCls: 'icon-blue',   icon: PlayCircleOutlined },
    { key: 'done',    label: '완료',          value: all.filter(d => d.status === '완료').length,    color: '#52c41a', cls: 'stat-green',  iconCls: 'icon-green',  icon: CheckCircleOutlined },
    { key: 'pending', label: '미진행',        value: all.filter(d => d.status === '미진행').length,  color: '#fa8c16', cls: 'stat-orange', iconCls: 'icon-orange', icon: PauseCircleOutlined },
  ]
})

// ── 테이블 컬럼 ──
const columns = [
  { title: 'No',        key: 'no',               width: 55,  align: 'center',
    customRender: ({ index }) => index + 1 },
  { title: 'PJT NO.',   dataIndex: 'project_no',  width: 140, align: 'center' },
  { title: 'PJT명',     key: 'project_name',      width: 220, align: 'center', ellipsis: true },
  { title: '발주처',    dataIndex: 'client_name',  width: 160, align: 'center', ellipsis: true },
  { title: '착공 시작', dataIndex: 'construct_start', width: 110, align: 'center' },
  { title: '착공 종료', dataIndex: 'construct_end',   width: 110, align: 'center' },
  { title: '계약금액',  key: 'contract_amount',   width: 140, align: 'right' },
  { title: '담당 PM',   dataIndex: 'pm_name',     width: 100, align: 'center' },
  { title: '진행상태',  key: 'status',            width: 110, align: 'center' },
  { title: '관리',      key: 'action',            width: 100, align: 'center', fixed: 'right' },
]

// ── 행 스타일 ──
function rowClass(record) {
  const classes = ['proj-row']
  if (selectedId.value === record.id) classes.push('proj-row--selected')
  if (isOverdue(record)) classes.push('proj-row--overdue')
  return classes.join(' ')
}

function isOverdue(record) {
  return record.status === '진행중' && record.construct_end &&
    record.construct_end < new Date().toISOString().slice(0, 10)
}

function handleRowClick(record) {
  selectedId.value = selectedId.value === record.id ? null : record.id
}

// ── 폼 ──
const emptyForm = {
  project_no: '', project_name: '', client_id: null, client_name: '',
  contract_form: '원도급', contract_type: '국내', status: '미진행',
  contract_amount: 0, contract_rate: 0,
  contract_start: null, contract_end: null,
  construct_start: null, construct_end: null,
  pm_name: '', pm_dept: '', region: '', notes: '',
}
const form = reactive({ ...emptyForm })

// 발주처 자동완성: 등록된 거래처 목록 제안 (직접 입력도 허용)
const clientSuggestions = computed(() => {
  const keyword = (form.client_name || '').toLowerCase()
  return companies.value
    .filter(c => !keyword || c.company_name.toLowerCase().includes(keyword))
    .map(c => ({ value: c.company_name, id: c.id }))
})

function onClientSelect(value, option) {
  // 목록에서 선택 시 client_id도 함께 설정
  form.client_id = option.id ?? null
}
function onClientChange(value) {
  // 직접 입력 시 client_id 초기화
  if (!value) { form.client_id = null; return }
  const match = companies.value.find(c => c.company_name === value)
  form.client_id = match ? match.id : null
}

function onContractStartChange(val) {
  if (val && !form.construct_start) form.construct_start = val
}

function openDrawer(item) {
  editItem.value = item
  Object.assign(form, item ? {
    project_no:      item.project_no     ?? '',
    project_name:    item.project_name,
    client_id:       item.client_id      ?? null,
    client_name:     item.client_name    ?? '',
    contract_form:   item.contract_form  ?? '원도급',
    contract_type:   item.contract_type  ?? '국내',
    status:          item.status         ?? '미진행',
    contract_amount: item.contract_amount ?? 0,
    contract_rate:   item.contract_rate   ?? 0,
    contract_start:  item.contract_start  ?? null,
    contract_end:    item.contract_end    ?? null,
    construct_start: item.construct_start ?? null,
    construct_end:   item.construct_end   ?? null,
    pm_name:         item.pm_name ?? '',
    pm_dept:         item.pm_dept ?? '',
    region:          item.region  ?? '',
    notes:           item.notes   ?? '',
  } : emptyForm)
  drawerOpen.value = true
}

async function handleSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    if (editItem.value) {
      await executionApi.updateProject(editItem.value.id, form)
      message.success('수정되었습니다.')
    } else {
      await executionApi.createProject(form)
      message.success('등록되었습니다.')
    }
    drawerOpen.value = false
    await load()
  } catch (e) {
    if (e?.errorFields) return
    message.error(e.response?.data?.detail || '저장 중 오류가 발생했습니다.')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id) {
  try {
    await executionApi.deleteProject(id)
    if (selectedId.value === id) selectedId.value = null
    message.success('삭제되었습니다.')
    await load()
  } catch (e) {
    message.error(e.response?.data?.detail || '삭제 중 오류가 발생했습니다.')
  }
}

async function load() {
  loading.value = true
  try {
    const [proj, co] = await Promise.all([
      executionApi.getProjects(),
      masterApi.getCompanies(),
    ])
    items.value     = proj.data
    companies.value = co.data
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }

/* ── 통계 카드 ── */
.stat-card   { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue   { border-left-color: #1677ff; }
.stat-green  { border-left-color: #52c41a; }
.stat-orange { border-left-color: #fa8c16; }
.stat-inner  { display: flex; align-items: center; gap: 14px; }
.stat-icon   { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.icon-gray   { background: #f0f2f5; color: #595959; }
.icon-blue   { background: #e6f4ff; color: #1677ff; }
.icon-green  { background: #f6ffed; color: #52c41a; }
.icon-orange { background: #fff7e6; color: #fa8c16; }
.stat-label  { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value  { font-size: 24px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit   { font-size: 13px; font-weight: 400; margin-left: 3px; color: #8c8c8c; }

/* ── 검색 조건 ── */
.filter-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.filter-table { width: 100%; border-collapse: collapse; }
.filter-table th {
  width: 90px; padding: 8px 12px; background: #fafafa;
  font-size: 12px; font-weight: 600; color: #595959;
  border: 1px solid #f0f0f0; white-space: nowrap; text-align: center;
}
.filter-table td { padding: 8px 12px; border: 1px solid #f0f0f0; }
.filter-footer {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 10px; padding-top: 8px; border-top: 1px solid #f5f5f5;
}
.filter-count { font-size: 13px; color: #595959; }
.filter-count b { color: #1677ff; }

/* ── 테이블 카드 ── */
.table-card  { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title  { font-size: 15px; font-weight: 600; color: #1a2535; }

/* ── 테이블 행 ── */
:deep(.proj-row) { cursor: pointer; transition: background 0.15s; }
:deep(.proj-row:hover td) { background: #f0f7ff !important; }
:deep(.proj-row--selected td) { background: #e6f4ff !important; }
:deep(.proj-row--overdue td) { background: #fff7e6 !important; }

.name-cell    { display: flex; align-items: center; }
.name-selected { font-weight: 600; color: #1677ff; }
.num-cell     { font-variant-numeric: tabular-nums; }
.overdue-mark { color: #fa8c16; margin-left: 4px; font-size: 13px; }
.del-link     { color: #e74c3c; }
.del-link:hover { color: #c0392b; }

/* ── Drawer 섹션 ── */
.sec-label { font-size: 12px; color: #8c8c8c; font-weight: 500; }

:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
