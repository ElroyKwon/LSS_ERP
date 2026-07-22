<template>
  <div class="page-wrap">
    <a-row :gutter="16">
      <a-col :flex="1" v-for="s in statsCards" :key="s.key">
        <a-card :bordered="false" class="stat-card" :class="s.cls">
          <div class="stat-inner">
            <div class="stat-icon" :class="s.iconCls"><component :is="s.icon" /></div>
            <div>
              <div class="stat-label">{{ s.label }}</div>
              <div class="stat-value" :style="`color:${s.color}`">{{ s.value }}<span class="stat-unit">{{ s.unit||'건' }}</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-card :bordered="false" class="table-card">
      <template #title><span class="card-title">매입 청구 (하도급 지급 요청)</span></template>
      <template #extra>
        <a-space>
          <a-select v-model:value="filterProject" allow-clear placeholder="프로젝트"
                    style="width:220px" :options="projectOptions" option-filter-prop="label"
                    show-search @change="load" />
          <a-select v-model:value="filterStatus" allow-clear placeholder="상태" style="width:120px" @change="load">
            <a-select-option v-for="s in STATUSES" :key="s" :value="s">{{ s }}</a-select-option>
          </a-select>
          <a-button type="primary" @click="openDrawer(null)">
            <template #icon><PlusOutlined /></template>청구 등록
          </a-button>
        </a-space>
      </template>

      <a-table :columns="columns" :data-source="items" :loading="loading"
               :pagination="clientPagination"
               row-key="id" size="middle" :scroll="{ x: 1240 }"
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="['bill_amount','vat_amount','total_amount'].includes(column.key)">
            {{ record[column.key] > 0 ? Number(record[column.key]).toLocaleString() : '—' }}
          </template>
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor[record.status]">{{ record.status }}</a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-space size="small">
              <a @click="openDrawer(record)">수정</a>
              <a-divider type="vertical" style="margin:0" />
              <a v-if="record.status !== '승인'" @click="handleApprove(record.id)">승인</a>
              <a-divider v-if="record.status !== '승인'" type="vertical" style="margin:0" />
              <a-popconfirm title="삭제하시겠습니까?" ok-text="삭제" ok-type="danger" cancel-text="취소"
                            @confirm="handleDelete(record.id)">
                <a class="del-link">삭제</a>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-modal :mask-closable="false" v-model:open="drawerOpen" :title="editItem ? '청구 수정' : '청구 등록'"
              width="840" wrap-class-name="purchase-billing-modal" :body-style="{ paddingBottom:'72px' }"
      centered>
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">기본 정보</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="청구번호" name="bill_no">
              <a-input v-model:value="form.bill_no" placeholder="자동 입력 가능" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="상태" name="status">
              <a-select v-model:value="form.status">
                <a-select-option v-for="s in STATUSES" :key="s" :value="s">{{ s }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="프로젝트" name="project_id">
              <a-select v-model:value="form.project_id" allow-clear show-search
                        placeholder="프로젝트 선택" :options="projectOptions" option-filter-prop="label"
                        @change="onProjectChange" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="원계약처" name="original_client_name">
              <a-input v-model:value="form.original_client_name" placeholder="프로젝트 선택 시 자동 입력" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="하도계약처" name="purchase_contract_id">
              <a-select v-model:value="form.purchase_contract_id" allow-clear show-search
                        placeholder="구매/계약에서 선택" :options="purchaseContractOptions"
                        option-filter-prop="label" @change="onContractChange" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="하도급사" name="vendor_name"
              :rules="[{ required: true, message: '하도급사명을 입력하세요.' }]"
              extra="직접 입력하거나 등록된 거래처를 검색하세요.">
              <a-auto-complete v-model:value="form.vendor_name" :options="vendorSuggestions"
                               placeholder="하도급사명 입력" allow-clear
                               @select="onVendorSelect" @change="onVendorChange" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">청구 금액</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="귀속 월" name="attribution_month">
              <a-date-picker v-model:value="form.attribution_month" picker="month" style="width:100%" value-format="YYYY-MM" placeholder="예) 2026-06" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="청구일" name="bill_date">
              <a-date-picker v-model:value="form.bill_date" style="width:100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="지급예정일" name="due_date">
              <a-date-picker v-model:value="form.due_date" style="width:100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="청구금액 (원)" name="bill_amount">
              <a-input-number v-model:value="form.bill_amount" style="width:100%"
                              :min="0" :formatter="fmtNum" :parser="parseNum"
                              @change="calcVat" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="부가세 (원)" name="vat_amount">
              <a-input-number v-model:value="form.vat_amount" style="width:100%"
                              :min="0" :formatter="fmtNum" :parser="parseNum"
                              @change="calcTotal" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="합계 (원)" name="total_amount">
              <a-input-number v-model:value="form.total_amount" style="width:100%"
                              :min="0" :formatter="fmtNum" :parser="parseNum" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="관련 매출청구" name="related_sales_bill">
              <a-input v-model:value="form.related_sales_bill" placeholder="해당 건 선택/입력" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="기성 정보" name="progress_info">
              <a-input v-model:value="form.progress_info" placeholder="기성 정보 불러오기/입력" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="지급구분" name="payment_method">
              <a-select v-model:value="form.payment_method">
                <a-select-option value="현금">현금</a-select-option>
                <a-select-option value="어음">어음</a-select-option>
                <a-select-option value="현금 및 어음">현금 및 어음</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
      <template #footer>
        <div style="text-align:right">
          <a-space>
            <a-button @click="drawerOpen=false">취소</a-button>
            <a-button type="primary" :loading="saving" @click="handleSave">저장</a-button>
          </a-space>
        </div>
      </template>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { FileTextOutlined, ClockCircleOutlined, CheckCircleOutlined, DollarOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { executionApi, masterApi } from '@/api'
import { createClientPagination } from '@/utils/pagination'

const clientPagination = createClientPagination()
const REQ_MARKER = '\n---매입청구요구사항---\n'
const STATUSES    = ['지급요청', '승인', '지급완료']
const statusColor = { 지급요청:'orange', 승인:'blue', 지급완료:'green' }

const items = ref([]), projects = ref([]), companies = ref([]), purchaseContracts = ref([])
const loading = ref(false), saving = ref(false), drawerOpen = ref(false)
const editItem = ref(null), formRef = ref()
const filterProject = ref(null), filterStatus = ref(null)

const emptyForm = { bill_no:'', project_id:null, vendor_name:'', vendor_id:null,
  bill_amount:0, vat_amount:0, total_amount:0, bill_date:null, due_date:null, status:'지급요청',
  attribution_month:null, original_client_name:'', purchase_contract_id:null,
  related_sales_bill:'', progress_info:'', payment_method:'현금', notes:'' }
const form = reactive({ ...emptyForm })

const projectOptions = computed(() =>
  projects.value.map(p => ({ value: p.id, label: `[${p.project_no||'—'}] ${p.project_name}`, client_name: p.client_name }))
)
const purchaseContractOptions = computed(() =>
  purchaseContracts.value
    .filter(c => !form.project_id || c.project_id === form.project_id)
    .map(c => ({ value: c.id, label: `[${c.contract_type}] ${c.vendor_name} - ${c.contract_name}`, vendor_name: c.vendor_name, vendor_id: c.vendor_id }))
)
const vendorSuggestions = computed(() =>
  companies.value.filter(c => !form.vendor_name || c.company_name.toLowerCase().includes((form.vendor_name||'').toLowerCase()))
    .map(c => ({ value: c.company_name, id: c.id }))
)
const fmtNum = v => v ? Number(v).toLocaleString() : ''
const parseNum = v => v.replace(/,/g, '')

const statsCards = computed(() => {
  const totalAmt = items.value.reduce((s,r) => s + (r.total_amount||0), 0)
  return [
    { key:'total', label:'전체',   value: items.value.length,                                  color:'#1a2535', cls:'',           iconCls:'icon-gray',   icon: FileTextOutlined, unit:'건' },
    { key:'req',   label:'지급요청', value: items.value.filter(r=>r.status==='지급요청').length, color:'#fa8c16', cls:'stat-orange', iconCls:'icon-orange', icon: ClockCircleOutlined, unit:'건' },
    { key:'appr',  label:'승인',   value: items.value.filter(r=>r.status==='승인').length,     color:'#1677ff', cls:'stat-blue',   iconCls:'icon-blue',   icon: CheckCircleOutlined, unit:'건' },
    { key:'amt',   label:'지급 합계(백만)', value: Math.round(totalAmt/1e6).toLocaleString(),  color:'#722ed1', cls:'stat-purple', iconCls:'icon-purple', icon: DollarOutlined, unit:'원' },
  ]
})

const columns = [
  { title: '청구번호', dataIndex: 'bill_no',      width: 140, align: 'center' },
  { title: '프로젝트', dataIndex: 'project_name', width: 180, align: 'center', ellipsis: true },
  { title: '귀속월', dataIndex: 'attribution_month', width: 95, align: 'center' },
  { title: '원계약처', dataIndex: 'original_client_name', width: 150, align: 'center', ellipsis: true },
  { title: '하도급사', dataIndex: 'vendor_name',  width: 160, align: 'center', ellipsis: true },
  { title: '지급구분', dataIndex: 'payment_method', width: 105, align: 'center' },
  { title: '청구금액', key: 'bill_amount',        width: 135, align: 'right' },
  { title: '부가세',  key: 'vat_amount',          width: 135, align: 'right' },
  { title: '합계',    key: 'total_amount',        width: 135, align: 'right' },
  { title: '청구일',  dataIndex: 'bill_date',     width: 110, align: 'center' },
  { title: '지급예정일', dataIndex: 'due_date',   width: 110, align: 'center' },
  { title: '상태',    key: 'status',              width: 90,  align: 'center' },
  { title: '관리',    key: 'action',              width: 100, align: 'center', fixed: 'right' },
]

function splitNotes(notes) {
  const raw = notes || ''
  const idx = raw.indexOf(REQ_MARKER)
  if (idx < 0) return { memo: raw, req: {} }
  try { return { memo: raw.slice(0, idx), req: JSON.parse(raw.slice(idx + REQ_MARKER.length)) || {} } }
  catch { return { memo: raw, req: {} } }
}

function buildNotes() {
  const req = {
    attribution_month: form.attribution_month,
    original_client_name: form.original_client_name,
    purchase_contract_id: form.purchase_contract_id,
    related_sales_bill: form.related_sales_bill,
    progress_info: form.progress_info,
    payment_method: form.payment_method,
  }
  return `${form.notes || ''}${REQ_MARKER}${JSON.stringify(req)}`
}

function withRequirementMeta(item) {
  const { memo, req } = splitNotes(item.notes)
  return {
    ...item,
    notes: memo,
    attribution_month: req.attribution_month || '',
    original_client_name: req.original_client_name || '',
    purchase_contract_id: req.purchase_contract_id || null,
    related_sales_bill: req.related_sales_bill || '',
    progress_info: req.progress_info || '',
    payment_method: req.payment_method || '',
  }
}

function toPayload() {
  return {
    bill_no: form.bill_no,
    project_id: form.project_id,
    vendor_name: form.vendor_name,
    vendor_id: form.vendor_id,
    bill_amount: form.bill_amount,
    vat_amount: form.vat_amount,
    total_amount: form.total_amount,
    bill_date: form.bill_date,
    due_date: form.due_date,
    status: form.status,
    notes: buildNotes(),
  }
}

function onVendorSelect(value, option) { form.vendor_id = option.id ?? null }
function onVendorChange(value) {
  const m = companies.value.find(c => c.company_name === value)
  form.vendor_id = m ? m.id : null
}
function onProjectChange(id) {
  const p = projects.value.find(p => p.id === id)
  form.original_client_name = p?.client_name || ''
}
function onContractChange(id, option) {
  form.vendor_name = option?.vendor_name || form.vendor_name
  form.vendor_id = option?.vendor_id ?? form.vendor_id
}
function calcVat()   { form.vat_amount = Math.round((form.bill_amount||0)*0.1); form.total_amount = (form.bill_amount||0) + form.vat_amount }
function calcTotal() { form.total_amount = (form.bill_amount||0) + (form.vat_amount||0) }

async function load() {
  loading.value = true
  try {
    const [bills, proj, co, pc] = await Promise.all([
      executionApi.getAPBills({ project_id: filterProject.value||undefined, status: filterStatus.value||undefined }),
      executionApi.getProjects(),
      masterApi.getCompanies(),
      executionApi.getPurchaseContracts(),
    ])
    items.value    = bills.data.map(withRequirementMeta)
    projects.value = proj.data
    companies.value = co.data
    purchaseContracts.value = pc.data
  } finally { loading.value = false }
}

function openDrawer(item) {
  editItem.value = item
  if (item) {
    const { memo, req } = splitNotes(item.notes)
    Object.assign(form, {
      ...item,
      notes: memo || '',
      attribution_month: req.attribution_month || null,
      original_client_name: req.original_client_name || '',
      purchase_contract_id: req.purchase_contract_id || null,
      related_sales_bill: req.related_sales_bill || '',
      progress_info: req.progress_info || '',
      payment_method: req.payment_method || '현금',
    })
  } else {
    Object.assign(form, emptyForm)
  }
  drawerOpen.value = true
}

async function handleSave() {
  try {
    saving.value = true
    if (editItem.value) { await executionApi.updateAPBill(editItem.value.id, toPayload()); message.success('수정되었습니다.') }
    else                { await executionApi.createAPBill(toPayload()); message.success('등록되었습니다.') }
    drawerOpen.value = false; load()
  } catch (e) { message.error(e.response?.data?.detail || '오류') }
  finally { saving.value = false }
}

async function handleDelete(id) {
  try { await executionApi.deleteAPBill(id); message.success('삭제되었습니다.'); load() }
  catch (e) { message.error(e.response?.data?.detail || '삭제 오류') }
}

async function handleApprove(id) {
  try {
    await executionApi.approveAPBill(id)
    message.success('승인되었고 채무관리 행이 생성되었습니다.')
    load()
  } catch (e) {
    message.error(e.response?.data?.detail || '승인 오류')
  }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display:flex; flex-direction:column; gap:16px; }
.stat-card { border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,0.07); border-left:4px solid #e0e0e0; }
.stat-orange { border-left-color:#fa8c16; } .stat-blue   { border-left-color:#1677ff; }
.stat-purple { border-left-color:#722ed1; }
.stat-inner { display:flex; align-items:center; gap:14px; }
.stat-icon  { width:44px; height:44px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:20px; flex-shrink:0; }
.icon-gray   { background:#f0f2f5; color:#595959; } .icon-orange { background:#fff7e6; color:#fa8c16; }
.icon-blue   { background:#e6f4ff; color:#1677ff; } .icon-purple { background:#f9f0ff; color:#722ed1; }
.stat-label { font-size:12px; color:#8c8c8c; margin-bottom:2px; }
.stat-value { font-size:22px; font-weight:700; color:#1a2535; line-height:1.2; }
.stat-unit  { font-size:12px; font-weight:400; margin-left:3px; color:#8c8c8c; }
.table-card { border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size:15px; font-weight:600; color:#1a2535; }
.sec-label  { font-size:12px; color:#8c8c8c; font-weight:500; }
.del-link { color:#e74c3c; } .del-link:hover { color:#c0392b; }
:deep(.ant-table-thead > tr > th) { text-align:center !important; background:#fafafa; }
:deep(.ant-card-head) { border-bottom:1px solid #f0f0f0; min-height:52px; }
</style>
