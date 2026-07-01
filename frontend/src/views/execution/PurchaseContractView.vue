<template>
  <div class="page-wrap">
    <a-row :gutter="16">
      <a-col :flex="1" v-for="s in statsCards" :key="s.key">
        <a-card :bordered="false" class="stat-card" :class="s.cls">
          <div class="stat-inner">
            <div class="stat-icon" :class="s.iconCls"><component :is="s.icon" /></div>
            <div>
              <div class="stat-label">{{ s.label }}</div>
              <div class="stat-value" :style="`color:${s.color}`">{{ s.value }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-card :bordered="false" class="table-card">
      <template #title><span class="card-title">구매 / 계약</span></template>
      <template #extra>
        <a-space>
          <a-select v-model:value="filterProject" allow-clear placeholder="프로젝트 필터"
                    style="width:220px" :options="projectOptions" option-filter-prop="label"
                    show-search @change="load" />
          <a-select v-model:value="filterStatus" allow-clear placeholder="상태" style="width:120px" @change="load">
            <a-select-option v-for="s in STATUSES" :key="s" :value="s">{{ s }}</a-select-option>
          </a-select>
          <a-button type="primary" @click="openDrawer(null)">
            <template #icon><PlusOutlined /></template>발주 등록
          </a-button>
        </a-space>
      </template>

      <a-table :columns="columns" :data-source="items" :loading="loading"
               :pagination="{ pageSize: 20, showSizeChanger: true }"
               row-key="id" size="middle" :scroll="{ x: 1000 }"
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'contract_amount'">{{ fmt(record.contract_amount) }}</template>
          <template v-if="column.key === 'contract_amount_vat'">{{ fmt(contractAmountVat(record)) }}</template>
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor[record.status]">{{ record.status }}</a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-space size="small">
              <a @click="openDrawer(record)">수정</a>
              <a-divider type="vertical" style="margin:0" />
              <a @click="handlePdf(record)">PDF</a>
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

    <a-modal v-model:open="drawerOpen" :title="editItem ? '구매 발주서 수정' : '구매 발주서 등록'"
              :width="945" wrap-class-name="purchase-contract-modal" :body-style="{ paddingBottom:'72px' }"
      centered>
      <a-form :model="form" layout="vertical" ref="formRef" class="order-form">
        <div class="order-sheet" ref="orderSheetRef">
          <div class="order-title">구 매 발 주 서</div>

          <div class="order-top">
            <div class="vendor-box">
              <a-form-item name="vendor_name" :rules="[{ required: true, message: '거래처명을 입력하세요.' }]">
                <a-auto-complete v-model:value="form.vendor_name" :options="vendorSuggestions"
                                 placeholder="수신 거래처" allow-clear
                                 @select="onVendorSelect" @change="onVendorChange" />
              </a-form-item>
              <span class="honorific">귀중</span>
            </div>
            <div class="buyer-box">
              <div class="buyer-row"><span>사업장 :</span><a-input v-model:value="form.buyer_company" /></div>
              <div class="buyer-row"><span>대표자 :</span><a-input v-model:value="form.buyer_ceo" /></div>
              <div class="buyer-row"><span>주소 :</span><a-input v-model:value="form.buyer_address" /></div>
              <div class="buyer-row"><span>전화번호 :</span><a-input v-model:value="form.buyer_phone" /></div>
              <div class="buyer-row"><span>팩스번호 :</span><a-input v-model:value="form.buyer_fax" /></div>
            </div>
          </div>

          <div class="order-no-row">
            <span>발주번호 :</span>
            <a-form-item name="contract_no">
              <a-input v-model:value="form.contract_no" placeholder="예) 2606-113" />
            </a-form-item>
          </div>

          <div class="order-info-grid">
            <div class="label-cell">금액합계</div>
            <div class="value-cell amount-cell">{{ fmt(totalAmount) }} 원</div>
            <div class="label-cell">지불조건</div>
            <div class="value-cell">
              <a-form-item name="payment_terms">
                <a-input v-model:value="form.payment_terms" placeholder="예) 익월말 결제" />
              </a-form-item>
            </div>
            <div class="label-cell">납품장소</div>
            <div class="value-cell">
              <a-form-item name="delivery_place">
                <a-input v-model:value="form.delivery_place" placeholder="예) 현장" />
              </a-form-item>
            </div>
            <div class="label-cell">프로젝트</div>
            <div class="value-cell">
              <a-form-item name="project_id">
                <a-select v-model:value="form.project_id" allow-clear placeholder="프로젝트 선택"
                          :options="projectOptions" option-filter-prop="label" show-search
                          @change="onProjectChange" />
              </a-form-item>
            </div>
            <div class="label-cell">발주일자</div>
            <div class="value-cell">
              <a-form-item name="start_date">
                <a-date-picker v-model:value="form.start_date" style="width:100%" value-format="YYYY-MM-DD" />
              </a-form-item>
            </div>
            <div class="label-cell">PJT No.</div>
            <div class="value-cell">
              <a-form-item name="pjt_no">
                <a-input v-model:value="form.pjt_no" />
              </a-form-item>
            </div>
          </div>

          <div class="order-message">
            위와 같이 발주하오니 계약조건을 준수하여 납품하여 주시기 바랍니다.
            <div class="manager-line">
              <b>발주담당자명 :</b>
              <a-input v-model:value="form.order_manager" placeholder="담당자" />
              <a-input v-model:value="form.order_manager_phone" placeholder="연락처" />
            </div>
          </div>

          <div class="tax-row">
            <span>부가세구분 :</span>
            <a-form-item name="vat_type">
              <a-select v-model:value="form.vat_type">
                <a-select-option value="매입과세">매입과세</a-select-option>
                <a-select-option value="면세">면세</a-select-option>
                <a-select-option value="영세">영세</a-select-option>
              </a-select>
            </a-form-item>
          </div>

          <div class="notice-box">
            <a-form-item name="notice_top_text">
              <a-textarea v-model:value="form.notice_top_text" :rows="3" class="notice-textarea notice-top" />
            </a-form-item>
            <a-form-item name="order_manager_contact" class="notice-contact-field">
              <a-input v-model:value="form.order_manager_contact" placeholder="담당자 : 연락처" />
            </a-form-item>
            <a-form-item name="notice_bottom_text">
              <a-textarea v-model:value="form.notice_bottom_text" :rows="1" class="notice-textarea notice-bottom" />
            </a-form-item>
          </div>

          <div class="item-toolbar">
            <span>발주 품목</span>
            <a-button size="small" type="primary" @click="addOrderItem">
              <template #icon><PlusOutlined /></template>품목 추가
            </a-button>
          </div>

          <div class="order-items">
            <div class="item-head">No.</div>
            <div class="item-head">품명</div>
            <div class="item-head">규격</div>
            <div class="item-head">단위</div>
            <div class="item-head">발주수량</div>
            <div class="item-head">단가</div>
            <div class="item-head">금액 (VAT 별도)</div>
            <div class="item-head">관리</div>
            <template v-for="(row, idx) in form.order_items" :key="row.uid">
              <div class="item-cell center">{{ idx + 1 }}</div>
              <div class="item-cell"><a-input v-model:value="row.item_name" /></div>
              <div class="item-cell"><a-input v-model:value="row.spec" /></div>
              <div class="item-cell"><a-input v-model:value="row.unit" /></div>
              <div class="item-cell"><a-input-number v-model:value="row.quantity" style="width:100%" :min="0" :formatter="fmtNum" :parser="parseNum" /></div>
              <div class="item-cell"><a-input-number v-model:value="row.unit_price" style="width:100%" :min="0" :formatter="fmtNum" :parser="parseNum" /></div>
              <div class="item-cell amount">{{ fmt(lineAmount(row)) }}</div>
              <div class="item-cell center">
                <a-button size="small" danger @click="removeOrderItem(idx)">삭제</a-button>
              </div>
            </template>
            <div class="item-foot">소계</div>
            <div class="item-foot"></div>
            <div class="item-foot"></div>
            <div class="item-foot"></div>
            <div class="item-foot amount">{{ totalQuantity.toLocaleString() }}</div>
            <div class="item-foot"></div>
            <div class="item-foot amount">{{ fmt(totalAmount) }}</div>
            <div class="item-foot"></div>
          </div>

        </div>
      </a-form>
      <template #footer>
        <div style="text-align:right">
          <a-space>
            <a-button :disabled="!editItem" @click="handlePdf(editItem)">PDF 출력</a-button>
            <a-button @click="drawerOpen=false">취소</a-button>
            <a-button type="primary" :loading="saving" @click="handleSave">저장</a-button>
          </a-space>
        </div>
      </template>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { FileTextOutlined, CheckCircleOutlined, CloseCircleOutlined, PlusOutlined, DollarOutlined } from '@ant-design/icons-vue'
import { executionApi, masterApi } from '@/api'
import { printElementAsPdf } from '@/utils/pdfExport'

const REQ_MARKER = '\n---구매계약요구사항---\n'
const CONTRACT_TYPES = ['자재', '외주', '안전', '기타']
const STATUSES = ['입력', '구매팀확인', '승인', '완료', '해지']
const statusColor = { 입력: 'orange', 구매팀확인: 'blue', 승인: 'purple', 완료: 'green', 해지: 'red', 진행: 'blue' }

const items = ref([]), projects = ref([]), companies = ref([])
const loading = ref(false), saving = ref(false), drawerOpen = ref(false)
const editItem = ref(null), formRef = ref(), orderSheetRef = ref()
const filterProject = ref(null), filterStatus = ref(null)

const defaultNotice = [
  'ㆍ 세금계산서 및 거래명세표는 메일로 발송 바랍니다. (수신 : tax @ lssauter.co.kr)',
  'ㆍ 전자세금계산서 송부하실 주소 : tax @ lssauter.co.kr',
  'ㆍ 자세한 납기일 및 납품 장소는 아래 담당자와 상의하시기 바랍니다.',
  'ㆍ 세금계산서 발행 시 No. 표 7자리 숫자를 같이 표기 바랍니다.',
].join('\n')
const defaultNoticeTop = [
  'ㆍ 세금계산서 및 거래명세표는 메일로 발송 바랍니다. (수신 : tax @ lssauter.co.kr)',
  'ㆍ 전자세금계산서 송부하실 주소 : tax @ lssauter.co.kr',
  'ㆍ 자세한 납기일 및 납품 장소는 아래 담당자와 상의하시기 바랍니다.',
].join('\n')
const defaultNoticeBottom = 'ㆍ 세금계산서 발행 시 No. 표 7자리 숫자를 같이 표기 바랍니다.'

const DEFAULT_BUYER_COMPANY = 'LS사우타(주)'
const DEFAULT_BUYER_ADDRESS = '경기도 안양시 동안구 엘에스로 127(호계동, LS타워)'

const makeOrderItem = (overrides = {}) => ({
  uid: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
  item_name: '',
  spec: '',
  unit: 'EA',
  quantity: 1,
  unit_price: 0,
  ...overrides,
})

const makeEmptyForm = () => ({
  contract_no:'',
  project_id:null,
  vendor_name:'',
  vendor_id:null,
  contract_name:'',
  contract_type:'자재',
  contract_amount:0,
  start_date:null,
  end_date:null,
  status:'입력',
  subcontract_flag:'미해당',
  payment_terms:'',
  delivery_place:'현장',
  pjt_no:'',
  vat_type:'매입과세',
  buyer_company:DEFAULT_BUYER_COMPANY,
  buyer_ceo:'김성용',
  buyer_address:DEFAULT_BUYER_ADDRESS,
  buyer_phone:'02-3442-5544',
  buyer_fax:'02-3442-5546',
  order_manager:'',
  order_manager_phone:'',
  order_manager_contact:'',
  notice_text: defaultNotice,
  notice_top_text: defaultNoticeTop,
  notice_bottom_text: defaultNoticeBottom,
  order_items:[makeOrderItem()],
  notes:'',
})
const form = reactive(makeEmptyForm())

const projectOptions = computed(() =>
  projects.value.map(p => ({ value: p.id, label: `[${p.project_no||'—'}] ${p.project_name}` }))
)
const vendorSuggestions = computed(() =>
  companies.value.filter(c => !form.vendor_name || c.company_name.toLowerCase().includes((form.vendor_name||'').toLowerCase()))
    .map(c => ({ value: c.company_name, id: c.id }))
)
const fmtNum = v => v ? Number(v).toLocaleString() : ''
const parseNum = v => v.replace(/,/g, '')
const fmt = v => v > 0 ? Number(v).toLocaleString() : '—'
const contractAmountVat = r => Math.round((Number(r?.contract_amount) || 0) * 1.1)
const lineAmount = row => Math.round((Number(row?.quantity) || 0) * (Number(row?.unit_price) || 0))
const totalAmount = computed(() => form.order_items.reduce((sum, row) => sum + lineAmount(row), 0))
const totalQuantity = computed(() => form.order_items.reduce((sum, row) => sum + (Number(row?.quantity) || 0), 0))
const splitNoticeText = text => {
  const lines = (text || defaultNotice).split('\n')
  return {
    top: lines.slice(0, 3).join('\n') || defaultNoticeTop,
    bottom: lines.slice(3).join('\n') || defaultNoticeBottom,
  }
}

const statsCards = computed(() => [
  { key:'total', label:'전체',  value: items.value.length,                              color:'#1a2535', cls:'',            iconCls:'icon-gray',   icon: FileTextOutlined },
  { key:'act',   label:'승인대기',  value: items.value.filter(r=>['입력','구매팀확인','진행'].includes(r.status)).length, color:'#1677ff', cls:'stat-blue',   iconCls:'icon-blue',   icon: FileTextOutlined },
  { key:'done',  label:'완료',  value: items.value.filter(r=>r.status==='완료').length, color:'#52c41a', cls:'stat-green',  iconCls:'icon-green',  icon: CheckCircleOutlined },
  { key:'term',  label:'해지',  value: items.value.filter(r=>r.status==='해지').length, color:'#f5222d', cls:'stat-red',    iconCls:'icon-red',    icon: CloseCircleOutlined },
  { key:'amt',   label:'계약금액 합계(백만)', value: Math.round(items.value.reduce((s,r)=>s+(r.contract_amount||0),0)/1e6).toLocaleString(),
    color:'#722ed1', cls:'stat-purple', iconCls:'icon-purple', icon: DollarOutlined },
])

const columns = [
  { title: '구매번호', dataIndex: 'contract_no',    width: 140, align: 'center' },
  { title: '계약명',  dataIndex: 'contract_name',   width: 200, align: 'center', ellipsis: true },
  { title: '프로젝트', dataIndex: 'project_name',   width: 170, align: 'center', ellipsis: true },
  { title: '거래처',  dataIndex: 'vendor_name',     width: 160, align: 'center', ellipsis: true },
  { title: '구분',    dataIndex: 'contract_type',   width: 80,  align: 'center' },
  { title: '하도급',  dataIndex: 'subcontract_flag', width: 90, align: 'center' },
  { title: '계약금액', key: 'contract_amount',      width: 140, align: 'right' },
  { title: 'VAT포함', key: 'contract_amount_vat',  width: 140, align: 'right' },
  { title: '지불조건', dataIndex: 'payment_terms',  width: 140, align: 'center' },
  { title: '상태',    key: 'status',                width: 100,  align: 'center' },
  { title: '관리',    key: 'action',                width: 130, align: 'center', fixed: 'right' },
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
    subcontract_flag: form.subcontract_flag,
    payment_terms: form.payment_terms,
    delivery_place: form.delivery_place,
    pjt_no: form.pjt_no,
    vat_type: form.vat_type,
    buyer_company: form.buyer_company,
    buyer_ceo: form.buyer_ceo,
    buyer_address: form.buyer_address,
    buyer_phone: form.buyer_phone,
    buyer_fax: form.buyer_fax,
    order_manager: form.order_manager,
    order_manager_phone: form.order_manager_phone,
    order_manager_contact: form.order_manager_contact,
    notice_text: [form.notice_top_text, form.notice_bottom_text].filter(Boolean).join('\n'),
    notice_top_text: form.notice_top_text,
    notice_bottom_text: form.notice_bottom_text,
    order_items: form.order_items.map(({ uid, ...row }) => row),
  }
  return `${form.notes || ''}${REQ_MARKER}${JSON.stringify(req)}`
}

function withRequirementMeta(item) {
  const { memo, req } = splitNotes(item.notes)
  return {
    ...item,
    notes: memo,
    subcontract_flag: req.subcontract_flag || '미해당',
    payment_terms: req.payment_terms || '',
    delivery_place: req.delivery_place || '',
    pjt_no: req.pjt_no || '',
  }
}

function toPayload() {
  const amount = totalAmount.value || Number(form.contract_amount) || 0
  return {
    contract_no: form.contract_no,
    project_id: form.project_id,
    vendor_name: form.vendor_name,
    vendor_id: form.vendor_id,
    contract_name: form.contract_name || `${form.vendor_name || '구매'} 발주`,
    contract_type: form.contract_type,
    contract_amount: amount,
    start_date: form.start_date,
    end_date: form.end_date,
    status: form.status,
    notes: buildNotes(),
  }
}

function onVendorSelect(value, option) { form.vendor_id = option.id ?? null }
function onVendorChange(value) {
  const m = companies.value.find(c => c.company_name === value)
  form.vendor_id = m ? m.id : null
}

function onProjectChange(value) {
  const project = projects.value.find(p => p.id === value)
  if (project) {
    form.pjt_no = project.project_no || form.pjt_no
    if (!form.contract_name) form.contract_name = `${project.project_name} 구매 발주`
  }
}

function addOrderItem() {
  form.order_items.push(makeOrderItem())
}

function removeOrderItem(index) {
  if (form.order_items.length === 1) {
    form.order_items = [makeOrderItem()]
    return
  }
  form.order_items.splice(index, 1)
}

async function load() {
  loading.value = true
  try {
    const [c, proj, co] = await Promise.all([
      executionApi.getPurchaseContracts({ project_id: filterProject.value || undefined, status: filterStatus.value || undefined }),
      executionApi.getProjects(),
      masterApi.getCompanies(),
    ])
    items.value    = c.data.map(withRequirementMeta)
    projects.value = proj.data
    companies.value = co.data
  } finally { loading.value = false }
}

function openDrawer(item) {
  editItem.value = item
  if (item) {
    const { memo, req } = splitNotes(item.notes)
    const noticeParts = splitNoticeText(req.notice_text)
    Object.assign(form, {
      ...makeEmptyForm(),
      ...item,
      notes: memo || '',
      subcontract_flag: req.subcontract_flag || '미해당',
      payment_terms: req.payment_terms || '',
      delivery_place: req.delivery_place || '현장',
      pjt_no: req.pjt_no || '',
      vat_type: req.vat_type || '매입과세',
      buyer_company: !req.buyer_company || req.buyer_company === 'LS사우터(주)' ? DEFAULT_BUYER_COMPANY : req.buyer_company,
      buyer_ceo: req.buyer_ceo || '김성용',
      buyer_address: !req.buyer_address || req.buyer_address === '경기도 안양시 동안구 엘에스로 127' ? DEFAULT_BUYER_ADDRESS : req.buyer_address,
      buyer_phone: req.buyer_phone || '02-3442-5544',
      buyer_fax: req.buyer_fax || '02-3442-5546',
      order_manager: req.order_manager || '',
      order_manager_phone: req.order_manager_phone || '',
      order_manager_contact: req.order_manager_contact || [req.order_manager, req.order_manager_phone].filter(Boolean).join(' : '),
      notice_text: req.notice_text || defaultNotice,
      notice_top_text: req.notice_top_text || noticeParts.top,
      notice_bottom_text: req.notice_bottom_text || noticeParts.bottom,
      order_items: Array.isArray(req.order_items) && req.order_items.length
        ? req.order_items.map(row => makeOrderItem(row))
        : [makeOrderItem({ unit_price: item.contract_amount || 0 })],
    })
  } else {
    Object.assign(form, makeEmptyForm())
  }
  drawerOpen.value = true
}

async function handlePdf(item) {
  if (!item && !editItem.value) {
    message.warning('저장된 발주서만 PDF 출력할 수 있습니다.')
    return
  }
  if (item && editItem.value?.id !== item.id) openDrawer(item)
  else if (!drawerOpen.value) drawerOpen.value = true

  await nextTick()
  try {
    printElementAsPdf(orderSheetRef.value, {
      title: `구매발주서_${form.contract_no || form.vendor_name || '미지정'}`,
      pageStyle: `
        body { padding: 0; }
        .order-sheet {
          width: 190mm !important;
          min-width: 0 !important;
          overflow: visible !important;
          border: 2px solid #2430ad !important;
          padding: 8mm !important;
        }
        .order-top,
        .order-no-row,
        .order-info-grid,
        .order-message,
        .tax-row,
        .notice-box,
        .item-toolbar,
        .order-items,
        .memo-field {
          min-width: 0 !important;
        }
        .item-toolbar,
        .item-cell button,
        .memo-field {
          display: none !important;
        }
      `,
    })
  } catch (e) {
    message.error(e.message || 'PDF 출력 창을 열 수 없습니다.')
  }
}

async function handleSave() {
  try {
    await formRef.value.validate(); saving.value = true
    if (editItem.value) { await executionApi.updatePurchaseContract(editItem.value.id, toPayload()); message.success('수정되었습니다.') }
    else                { await executionApi.createPurchaseContract(toPayload()); message.success('등록되었습니다.') }
    drawerOpen.value = false; load()
  } catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') }
  finally { saving.value = false }
}

async function handleDelete(id) {
  try { await executionApi.deletePurchaseContract(id); message.success('삭제되었습니다.'); load() }
  catch (e) { message.error(e.response?.data?.detail || '삭제 오류') }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.stat-card { border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,0.07); border-left:4px solid #e0e0e0; }
.stat-blue   { border-left-color:#1677ff; } .stat-green  { border-left-color:#52c41a; }
.stat-red    { border-left-color:#f5222d; } .stat-purple { border-left-color:#722ed1; }
.stat-inner { display:flex; align-items:center; gap:14px; }
.stat-icon  { width:44px; height:44px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:20px; flex-shrink:0; }
.icon-gray   { background:#f0f2f5; color:#595959; } .icon-blue   { background:#e6f4ff; color:#1677ff; }
.icon-green  { background:#f6ffed; color:#52c41a; } .icon-red    { background:#fff1f0; color:#f5222d; }
.icon-purple { background:#f9f0ff; color:#722ed1; }
.stat-label { font-size:12px; color:#8c8c8c; margin-bottom:2px; }
.stat-value { font-size:22px; font-weight:700; color:#1a2535; line-height:1.2; }
.stat-unit  { font-size:12px; font-weight:400; margin-left:3px; color:#8c8c8c; }
.table-card { border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size:15px; font-weight:600; color:#1a2535; }
.del-link { color:#e74c3c; } .del-link:hover { color:#c0392b; }
.order-form {
  margin-top: 4px;
}
.order-sheet {
  border: 2px solid #2430ad;
  background: #fff;
  padding: 18px 18px 20px;
  color: #111827;
  overflow-x: auto;
}
.order-title {
  margin: 4px auto 18px;
  width: 280px;
  text-align: center;
  color: #0b168b;
  font-size: 30px;
  font-weight: 800;
  letter-spacing: 8px;
  border-bottom: 4px double #5156c6;
  line-height: 1.35;
}
.order-top {
  display: grid;
  grid-template-columns: minmax(320px, 1fr) 430px;
  gap: 28px;
  min-width: 900px;
  margin-bottom: 18px;
}
.vendor-box {
  display: grid;
  grid-template-columns: 1fr 76px;
  gap: 12px;
  align-items: end;
  padding-top: 30px;
  border-bottom: 3px solid #333;
}
.honorific {
  font-size: 20px;
  font-weight: 800;
  text-align: center;
}
.buyer-box {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 13px;
  text-align: left;
}
.buyer-row {
  display: grid;
  grid-template-columns: 78px 1fr;
  align-items: center;
  gap: 6px;
}
.buyer-row span {
  font-weight: 700;
  text-align: left;
  white-space: nowrap;
}
.buyer-row :deep(.ant-input) {
  text-align: left;
  padding-left: 4px;
}
.order-no-row {
  display: grid;
  grid-template-columns: 82px 170px;
  gap: 8px;
  align-items: center;
  min-width: 900px;
  margin-bottom: 8px;
  font-size: 13px;
}
.order-no-row > span {
  font-weight: 700;
}
.order-info-grid {
  display: grid;
  grid-template-columns: 120px minmax(250px, 1fr) 110px minmax(250px, 1fr);
  min-width: 900px;
  border: 2px solid #2430ad;
  border-bottom: 0;
}
.label-cell,
.value-cell {
  min-height: 36px;
  padding: 5px 8px;
  border-right: 2px solid #2430ad;
  border-bottom: 2px solid #2430ad;
  display: flex;
  align-items: center;
}
.label-cell {
  justify-content: center;
  background: #bfeeee;
  font-weight: 800;
}
.value-cell {
  background: #fff;
}
.order-info-grid .value-cell:nth-child(4n) {
  border-right: 0;
}
.amount-cell {
  justify-content: flex-end;
  font-weight: 700;
}
.order-message {
  min-width: 900px;
  border: 2px solid #2430ad;
  border-top: 0;
  padding: 14px 16px 10px;
  text-align: center;
  font-weight: 600;
}
.manager-line {
  display: grid;
  grid-template-columns: 116px 180px 190px;
  justify-content: center;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
  font-weight: 600;
}
.tax-row {
  display: grid;
  grid-template-columns: 96px 160px;
  gap: 8px;
  align-items: center;
  min-width: 900px;
  margin: 8px 0;
  font-weight: 700;
}
.notice-box {
  min-width: 900px;
  border: 2px solid #555;
  padding: 10px 14px;
  margin-bottom: 8px;
  text-align: left;
}
.notice-box :deep(.ant-input) {
  text-align: left;
}
.notice-box :deep(textarea.ant-input) {
  line-height: 1.8;
  resize: none;
}
.notice-textarea {
  border: 0 !important;
  box-shadow: none !important;
  padding: 4px 0 !important;
  overflow: hidden;
}
.notice-bottom {
  margin-top: 2px;
}
.notice-contact-field {
  margin-top: 0;
  margin-left: 14px;
  width: 260px !important;
}
.notice-contact-field :deep(.ant-input) {
  text-align: left !important;
}
.item-toolbar {
  min-width: 900px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 10px 0 6px;
  font-weight: 700;
}
.order-items {
  display: grid;
  grid-template-columns: 54px minmax(120px, 1fr) minmax(220px, 1.8fr) 70px 110px 110px 130px 72px;
  min-width: 900px;
  border-left: 2px solid #2430ad;
  border-top: 2px solid #2430ad;
}
.item-head,
.item-cell,
.item-foot {
  min-height: 36px;
  padding: 5px 6px;
  border-right: 2px solid #2430ad;
  border-bottom: 2px solid #2430ad;
  display: flex;
  align-items: center;
}
.item-head {
  justify-content: center;
  background: #bfeeee;
  font-weight: 800;
  text-align: center;
}
.item-cell {
  background: #fff;
}
.item-foot {
  background: #ffe4c4;
  font-weight: 800;
}
.center {
  justify-content: center;
  text-align: center;
}
.amount {
  justify-content: flex-end;
  text-align: right;
}
.memo-field {
  min-width: 900px;
  margin-top: 10px;
}
.order-sheet :deep(.ant-form-item) {
  width: 100%;
  margin-bottom: 0;
}
.order-sheet :deep(.ant-input),
.order-sheet :deep(.ant-input-number),
.order-sheet :deep(.ant-picker),
.order-sheet :deep(.ant-select-selector),
.order-sheet :deep(.ant-input-number-input) {
  border-radius: 2px !important;
}
.order-info-grid :deep(.ant-input-number-input),
.order-info-grid :deep(.ant-input),
.order-items :deep(.ant-input-number-input),
.order-items :deep(.ant-input) {
  text-align: center;
}
.buyer-box :deep(.ant-input),
.notice-box :deep(.ant-input),
.notice-box :deep(textarea.ant-input) {
  text-align: left !important;
}
:deep(.ant-table-thead > tr > th) { text-align:center !important; background:#fafafa; }
:deep(.ant-card-head) { border-bottom:1px solid #f0f0f0; min-height:52px; }
</style>
