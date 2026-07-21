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
      <template #title><span class="card-title">매출 청구 (세금계산서 발행 요청)</span></template>
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
               :pagination="{ defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'] }"
               row-key="id" size="middle" :scroll="{ x: 1280 }"
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="['bill_amount','vat_amount','total_amount'].includes(column.key)">
            {{ record[column.key] > 0 ? Number(record[column.key]).toLocaleString() : '—' }}
          </template>
          <template v-if="column.key === 'order_balance'">
            {{ record.order_balance > 0 ? Number(record.order_balance).toLocaleString() : '—' }}
          </template>
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor[record.status]">{{ record.status }}</a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-space size="small">
              <a @click="openDrawer(record)">수정</a>
              <a-divider type="vertical" style="margin:0" />
              <a-popconfirm v-if="record.status !== '승인'" title="승인 처리하고 채권관리로 생성하시겠습니까?"
                            ok-text="승인" cancel-text="취소" @confirm="handleApprove(record.id)">
                <a>승인</a>
              </a-popconfirm>
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

    <a-modal :mask-closable="false" v-model:open="drawerOpen" :title="editItem ? '청구 수정' : '청구 등록'"
              width="960" wrap-class-name="sales-billing-modal" :body-style="{ paddingBottom:'72px' }"
      centered>
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">PJT 정보</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="PJT" name="project_id">
              <a-select v-model:value="form.project_id" allow-clear show-search
                        placeholder="프로젝트 선택" :options="projectOptions"
                        option-filter-prop="label" @change="onProjectChange" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="PJT No." name="pjt_no">
              <a-input v-model:value="form.pjt_no" disabled />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="발주처" name="client_name">
              <a-input v-model:value="form.client_name" disabled />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="계약 금액" name="contract_amount">
              <a-input-number v-model:value="form.contract_amount" style="width:100%" disabled
                              :formatter="fmtNum" :parser="parseNum" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">세금계산서</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="발행일자" name="bill_date">
              <a-date-picker v-model:value="form.bill_date" style="width:100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="기재일자" name="invoice_date">
              <a-date-picker v-model:value="form.invoice_date" style="width:100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="발행금액(VAT 별도)" name="bill_amount">
              <a-input-number v-model:value="form.bill_amount" style="width:100%"
                              :min="0" :formatter="fmtNum" :parser="parseNum"
                              @change="calcVat" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="발행 이메일" name="issue_email">
              <a-input v-model:value="form.issue_email" placeholder="tax@example.com" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">거래처 담당자</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="이름" name="client_contact_name">
              <a-input v-model:value="form.client_contact_name" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="연락처" name="client_contact_phone">
              <a-input v-model:value="form.client_contact_phone" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="이메일" name="client_contact_email">
              <a-input v-model:value="form.client_contact_email" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">관련 매입</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="24">
            <div class="related-purchase-actions">
              <a-button type="primary" size="small" @click="addRelatedPurchase">
                <template #icon><PlusOutlined /></template>행 추가
              </a-button>
            </div>
            <a-table :columns="relatedPurchaseColumns" :data-source="form.related_purchases"
                     row-key="uid" size="small" :pagination="{ defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'] }" class="related-purchase-table"
        :sticky="{ offsetHeader: 56 }">
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'vendor_name'">
                  <a-select v-model:value="record.purchase_id" allow-clear show-search
                            placeholder="구매/계약 업체 선택" :options="purchaseOptions"
                            option-filter-prop="label" @change="id => onRelatedPurchaseChange(record, id)" />
                </template>
                <template v-else-if="column.key === 'issue_amount'">
                  <a-input-number v-model:value="record.issue_amount" style="width:100%" :min="0" :formatter="fmtNum" :parser="parseNum" />
                </template>
                <template v-else-if="column.key === 'issue_day'">
                  <a-select v-model:value="record.issue_day">
                    <a-select-option value="16">16일</a-select-option>
                    <a-select-option value="26">26일</a-select-option>
                  </a-select>
                </template>
                <template v-else-if="column.key === 'types'">
                  <a-checkbox-group v-model:value="record.types" class="purchase-type-checks">
                    <a-checkbox value="자재">자재</a-checkbox>
                    <a-checkbox value="외주">외주</a-checkbox>
                    <a-checkbox value="안전">안전</a-checkbox>
                    <a-checkbox value="기타">기타</a-checkbox>
                  </a-checkbox-group>
                </template>
              </template>
            </a-table>
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
import { FileTextOutlined, ClockCircleOutlined, CheckCircleOutlined, CheckOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { executionApi } from '@/api'

const REQ_MARKER = '\n---매출청구요구사항---\n'
const STATUSES    = ['발행요청', '발행완료', '확인', '승인']
const statusColor = { 발행요청:'orange', 발행완료:'blue', 확인:'green', 승인:'green' }

const items = ref([]), projects = ref([]), purchaseContracts = ref([])
const loading = ref(false), saving = ref(false), drawerOpen = ref(false)
const editItem = ref(null), formRef = ref()
const filterProject = ref(null), filterStatus = ref(null)

const emptyForm = { bill_no:'', project_id:null, client_name:'', bill_amount:0, vat_amount:0, total_amount:0,
  bill_date:null, due_date:null, invoice_no:'', invoice_date:null, status:'발행요청',
  attribution_month:null, order_balance:0, issue_type:'정발행', client_contact:'', notes:'',
  pjt_no:'', pjt_name:'', contract_amount:0, issue_email:'',
  client_contact_name:'', client_contact_phone:'', client_contact_email:'',
  related_purchases:[] }
const form = reactive({ ...emptyForm })

const projectOptions = computed(() =>
  projects.value.map(p => ({ value: p.id, label: `[${p.project_no||'—'}] ${p.project_name}` }))
)
const purchaseOptions = computed(() =>
  purchaseContracts.value
    .filter(p => !form.project_id || p.project_id === form.project_id)
    .map(p => ({ value: p.id, label: `${p.vendor_name || '-'} / ${fmtMoney(p.contract_amount)} / ${p.contract_type || '-'}` }))
)
const fmtNum = v => v ? Number(v).toLocaleString() : ''
const parseNum = v => v.replace(/,/g, '')
const fmtMoney = v => Number(v || 0).toLocaleString()

const statsCards = computed(() => {
  const totalAmt = items.value.reduce((s,r) => s + (r.total_amount||0), 0)
  return [
    { key:'total', label:'전체',   value: items.value.length,                                  color:'#1a2535', cls:'',           iconCls:'icon-gray',   icon: FileTextOutlined, unit:'건' },
    { key:'req',   label:'발행요청', value: items.value.filter(r=>r.status==='발행요청').length, color:'#fa8c16', cls:'stat-orange', iconCls:'icon-orange', icon: ClockCircleOutlined, unit:'건' },
    { key:'iss',   label:'발행완료', value: items.value.filter(r=>r.status==='발행완료').length, color:'#1677ff', cls:'stat-blue',   iconCls:'icon-blue',   icon: CheckCircleOutlined, unit:'건' },
    { key:'amt',   label:'청구 합계(백만)', value: Math.round(totalAmt/1e6).toLocaleString(),   color:'#722ed1', cls:'stat-purple', iconCls:'icon-purple', icon: CheckOutlined, unit:'원' },
  ]
})

const columns = [
  { title: '청구번호', dataIndex: 'bill_no',      width: 140, align: 'center' },
  { title: '프로젝트', dataIndex: 'project_name', width: 180, align: 'center', ellipsis: true },
  { title: '발주처',  dataIndex: 'client_name',  width: 160, align: 'center', ellipsis: true },
  { title: '귀속월',  dataIndex: 'attribution_month', width: 95, align: 'center' },
  { title: '발급구분', dataIndex: 'issue_type', width: 90, align: 'center' },
  { title: '공급가액', key: 'bill_amount',        width: 135, align: 'right' },
  { title: '부가세',  key: 'vat_amount',          width: 135, align: 'right' },
  { title: '합계',    key: 'total_amount',        width: 135, align: 'right' },
  { title: '수주잔',  key: 'order_balance',       width: 135, align: 'right' },
  { title: '청구일',  dataIndex: 'bill_date',     width: 110, align: 'center' },
  { title: '세금계산서', dataIndex: 'invoice_no', width: 130, align: 'center' },
  { title: '상태',    key: 'status',              width: 90,  align: 'center' },
  { title: '관리',    key: 'action',              width: 140, align: 'center', fixed: 'right' },
]

const relatedPurchaseColumns = [
  { title: '업체명', key: 'vendor_name', width: 170, align: 'center' },
  { title: '발행금액', key: 'issue_amount', width: 120, align: 'right' },
  { title: '발행일', key: 'issue_day', width: 70, align: 'center' },
  { title: '구분', key: 'types', width: 210, align: 'center' },
]

function makeRelatedPurchase(overrides = {}) {
  return {
    uid: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    purchase_id: null,
    vendor_name: '',
    issue_amount: 0,
    issue_day: '16',
    types: [],
    ...overrides,
  }
}

function typeFromPurchase(contractType) {
  if (['자재', '외주', '안전'].includes(contractType)) return [contractType]
  return ['기타']
}

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
    order_balance: form.order_balance,
    issue_type: form.issue_type,
    client_contact: form.client_contact,
    pjt_no: form.pjt_no,
    pjt_name: form.pjt_name,
    contract_amount: form.contract_amount,
    issue_email: form.issue_email,
    client_contact_name: form.client_contact_name,
    client_contact_phone: form.client_contact_phone,
    client_contact_email: form.client_contact_email,
    related_purchases: form.related_purchases
      .filter(row => row.purchase_id || row.vendor_name || row.issue_amount)
      .map(({ uid, ...row }) => row),
  }
  return `${form.notes || ''}${REQ_MARKER}${JSON.stringify(req)}`
}

function withRequirementMeta(item) {
  const { memo, req } = splitNotes(item.notes)
  return {
    ...item,
    notes: memo,
    attribution_month: req.attribution_month || '',
    order_balance: Number(req.order_balance) || 0,
    issue_type: req.issue_type || '',
    client_contact: req.client_contact || '',
    pjt_no: req.pjt_no || '',
    pjt_name: req.pjt_name || '',
    contract_amount: Number(req.contract_amount) || 0,
    issue_email: req.issue_email || '',
    client_contact_name: req.client_contact_name || '',
    client_contact_phone: req.client_contact_phone || '',
    client_contact_email: req.client_contact_email || '',
    related_purchases: Array.isArray(req.related_purchases) ? req.related_purchases : [],
  }
}

function toPayload() {
  return {
    bill_no: form.bill_no,
    project_id: form.project_id,
    client_name: form.client_name,
    bill_amount: form.bill_amount,
    vat_amount: form.vat_amount,
    total_amount: form.total_amount,
    bill_date: form.bill_date,
    due_date: form.due_date,
    invoice_no: form.invoice_no,
    invoice_date: form.invoice_date,
    status: form.status,
    notes: buildNotes(),
  }
}

function calcVat() {
  form.vat_amount   = Math.round((form.bill_amount || 0) * 0.1)
  form.total_amount = (form.bill_amount || 0) + form.vat_amount
}
function calcTotal() {
  form.total_amount = (form.bill_amount || 0) + (form.vat_amount || 0)
}
function onProjectChange(id) {
  const p = projects.value.find(p => p.id === id)
  form.pjt_no = p?.project_no || ''
  form.pjt_name = p?.project_name || ''
  form.client_name = p?.client_name || ''
  form.contract_amount = Number(p?.contract_amount) || 0
}

function onRelatedPurchaseChange(record, id) {
  const p = purchaseContracts.value.find(row => row.id === id)
  record.purchase_id = id || null
  record.vendor_name = p?.vendor_name || ''
  record.issue_amount = Number(p?.contract_amount) || 0
  record.types = p ? typeFromPurchase(p.contract_type) : []
}

function addRelatedPurchase() {
  form.related_purchases.push(makeRelatedPurchase())
}

async function load() {
  loading.value = true
  try {
    const [bills, proj, purchases] = await Promise.all([
      executionApi.getSalesBills({ project_id: filterProject.value||undefined, status: filterStatus.value||undefined }),
      executionApi.getProjects(),
      executionApi.getPurchaseContracts(),
    ])
    items.value    = bills.data.map(withRequirementMeta)
    projects.value = proj.data
    purchaseContracts.value = purchases.data
  } finally { loading.value = false }
}

function openDrawer(item) {
  editItem.value = item
  if (item) {
    const { memo, req } = splitNotes(item.notes)
    Object.assign(form, {
      ...emptyForm,
      ...item,
      notes: memo || '',
      attribution_month: req.attribution_month || null,
      order_balance: Number(req.order_balance) || 0,
      issue_type: req.issue_type || '정발행',
      client_contact: req.client_contact || '',
      pjt_no: req.pjt_no || '',
      pjt_name: req.pjt_name || item.project_name || '',
      contract_amount: Number(req.contract_amount) || 0,
      issue_email: req.issue_email || '',
      client_contact_name: req.client_contact_name || '',
      client_contact_phone: req.client_contact_phone || '',
      client_contact_email: req.client_contact_email || '',
      related_purchases: Array.isArray(req.related_purchases) && req.related_purchases.length
        ? req.related_purchases.map(row => makeRelatedPurchase(row))
        : [makeRelatedPurchase()],
    })
    if (!form.pjt_no || !form.contract_amount) onProjectChange(form.project_id)
  } else {
    Object.assign(form, { ...emptyForm, related_purchases: [makeRelatedPurchase()] })
  }
  drawerOpen.value = true
}

async function handleSave() {
  try {
    saving.value = true
    if (editItem.value) { await executionApi.updateSalesBill(editItem.value.id, toPayload()); message.success('수정되었습니다.') }
    else                { await executionApi.createSalesBill(toPayload()); message.success('등록되었습니다.') }
    drawerOpen.value = false; load()
  } catch (e) { message.error(e.response?.data?.detail || '오류') }
  finally { saving.value = false }
}

async function handleDelete(id) {
  try { await executionApi.deleteSalesBill(id); message.success('삭제되었습니다.'); load() }
  catch (e) { message.error(e.response?.data?.detail || '삭제 오류') }
}

async function handleApprove(id) {
  try {
    await executionApi.approveSalesBill(id)
    message.success('승인 처리되어 채권관리로 생성되었습니다.')
    load()
  } catch (e) {
    message.error(e.response?.data?.detail || '승인 처리 오류')
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
.purchase-type-checks {
  display:flex;
  justify-content:center;
  gap:8px;
  white-space:nowrap;
}
.related-purchase-table {
  margin-bottom:8px;
}
.related-purchase-actions {
  display:flex;
  justify-content:flex-end;
  margin-bottom:12px;
}
:deep(.ant-table-thead > tr > th) { text-align:center !important; background:#fafafa; }
:deep(.ant-card-head) { border-bottom:1px solid #f0f0f0; min-height:52px; }
</style>
