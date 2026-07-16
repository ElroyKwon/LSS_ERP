<template>
  <div class="page-wrap">
    <CrudTable
      title="견적 관리"
      :columns="columns"
      :data="items"
      :loading="loading"
      :scroll-x="2660"
      :custom-row="estimateRowEvents"
      create-label="견적 등록"
      @create="openDrawer(null)"
    >
      <template #filters>
        <a-input-search
          v-model:value="search"
          placeholder="견적번호/프로젝트명 검색"
          style="width: 240px"
          allow-clear
          @search="load"
        />
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="amountColumnKeys.includes(column.key)">
          <span class="num-cell">{{ formatAmount(record[column.key]) }}</span>
        </template>
        <template v-else-if="column.key === 'project_name'">
          <a-button type="link" class="title-link" @click.stop="openDrawer(record, 'view')">
            {{ record.project_name || '-' }}
          </a-button>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space>
            <a-button v-if="canManageEstimate(record)" size="small" type="link" @click.stop="openDrawer(record, 'edit')">수정</a-button>
            <a-popconfirm
              v-if="canManageEstimate(record)"
              title="견적을 삭제하시겠습니까?"
              ok-text="삭제"
              ok-type="danger"
              cancel-text="취소"
              @confirm="deleteEstimate(record)"
            >
              <a-button size="small" type="link" danger @click.stop>삭제</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </CrudTable>

    <a-modal :mask-closable="false"
      v-model:open="drawerOpen"
      :title="modalTitle"
      :width="840"
      wrap-class-name="estimate-editor-modal"
      :body-style="{ paddingBottom: '76px' }"
    
      centered>
      <a-form ref="formRef" :model="form" layout="vertical" class="estimate-form" :disabled="viewOnly">
        <a-divider orientation="left">기본 정보</a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="견적번호" name="estimate_no" :rules="[{ required: true, message: '견적번호를 입력하세요.' }]">
              <a-input v-model:value="form.estimate_no" disabled />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="설계번호" name="design_no">
              <a-input v-model:value="form.design_no" placeholder="설계번호 입력" />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="프로젝트명" name="project_name" :rules="[{ required: true, message: '프로젝트명을 입력하세요.' }]">
              <a-input v-model:value="form.project_name" placeholder="프로젝트명 입력" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="지역" name="region">
              <a-input v-model:value="form.region" placeholder="지역 입력" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="사업부명" name="business_division">
              <a-input v-model:value="form.business_division" placeholder="사업부명 입력" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="영업담당자" name="sales_manager">
              <a-input v-model:value="form.sales_manager" placeholder="영업담당자 입력" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="경쟁사" name="competitor">
              <a-input v-model:value="form.competitor" placeholder="경쟁사 입력" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left">거래 및 일정</a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="제출처" name="submit_to">
              <a-input v-model:value="form.submit_to" placeholder="제출처 입력" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="발주처" name="client_name">
              <a-input v-model:value="form.client_name" placeholder="발주처 입력" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="발주예정일" name="expected_order_date">
              <a-date-picker v-model:value="form.expected_order_date" style="width: 100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="납기" name="delivery_date">
              <a-date-picker v-model:value="form.delivery_date" style="width: 100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="견적일자" name="estimate_date">
              <a-date-picker v-model:value="form.estimate_date" style="width: 100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left">금액</a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="견적가" name="estimate_price">
              <a-input-number
                v-model:value="form.estimate_price"
                style="width: 100%"
                :min="0"
                :formatter="amountFormatter"
                :parser="amountParser"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="매출원가" name="sales_cost">
              <a-input-number
                v-model:value="form.sales_cost"
                style="width: 100%"
                :min="0"
                :formatter="amountFormatter"
                :parser="amountParser"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item>
              <template #label>
                <span>판관비 <span class="field-hint">Factor {{ overheadRate }}%</span></span>
              </template>
              <a-input-number
                :value="calculatedOverhead"
                style="width: 100%"
                disabled
                :formatter="amountFormatter"
                :parser="amountParser"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="세전이익">
              <a-input-number
                :value="calculatedProfit"
                style="width: 100%"
                disabled
                :formatter="amountFormatter"
                :parser="amountParser"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left">첨부파일</a-divider>
        <a-upload
          v-if="!viewOnly"
          v-model:file-list="pendingFiles"
          :before-upload="beforeUpload"
          multiple
        >
          <a-button>
            <template #icon><UploadOutlined /></template>
            파일 선택
          </a-button>
        </a-upload>
        <a-list
          v-if="attachments.length"
          size="small"
          class="attachment-list"
          :data-source="attachments"
        >
          <template #renderItem="{ item }">
            <a-list-item>
              <template #actions>
                <a-button type="link" size="small" @click="downloadAttachment(item)">다운로드</a-button>
                <a-popconfirm v-if="!viewOnly" title="첨부파일을 삭제하시겠습니까?" @confirm="deleteAttachment(item)">
                  <a-button type="link" size="small" danger>삭제</a-button>
                </a-popconfirm>
              </template>
              <a-list-item-meta>
                <template #title>{{ item.original_name }}</template>
                <template #description>{{ formatFileSize(item.file_size) }}</template>
              </a-list-item-meta>
            </a-list-item>
          </template>
        </a-list>
      </a-form>

      <template #footer>
        <div class="drawer-footer">
          <a-button @click="drawerOpen = false">{{ viewOnly ? '닫기' : '취소' }}</a-button>
          <a-button v-if="!viewOnly" type="primary" :loading="saving" @click="handleSave">저장</a-button>
        </div>
      </template>
    </a-modal>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { UploadOutlined } from '@ant-design/icons-vue'
import CrudTable from '@/components/common/CrudTable.vue'
import { salesApi, masterApi } from '@/api'
import { useAuthStore } from '@/store/auth'

const ESTIMATE_META_MARKER = '\n---estimate-meta---\n'
const now = new Date()

const items = ref([])
const auth = useAuthStore()
const overheadRates = ref([])
const loading = ref(false)
const saving = ref(false)
const drawerOpen = ref(false)
const editItem = ref(null)
const viewOnly = ref(false)
const search = ref('')
const formRef = ref()
const attachments = ref([])
const pendingFiles = ref([])

const form = reactive(createEmptyForm())

const amountColumnKeys = ['estimate_price', 'sales_cost', 'overhead_amount', 'profit_amount']
const columns = [
  { title: '견적번호', dataIndex: 'estimate_no', width: 120, align: 'center', fixed: 'left' },
  { title: '설계번호', dataIndex: 'design_no', width: 120, align: 'center' },
  { title: '프로젝트명', dataIndex: 'project_name', width: 220, align: 'center', ellipsis: true },
  { title: '지역', dataIndex: 'region', width: 110, align: 'center' },
  { title: '사업부명', dataIndex: 'business_division', width: 140, align: 'center' },
  { title: '영업담당자', dataIndex: 'sales_manager', width: 120, align: 'center' },
  { title: '제출처', dataIndex: 'submit_to', width: 160, align: 'center', ellipsis: true },
  { title: '발주처', dataIndex: 'client_name', width: 160, align: 'center', ellipsis: true },
  { title: '발주예정일', dataIndex: 'expected_order_date', width: 120, align: 'center' },
  { title: '납기', dataIndex: 'delivery_date', width: 120, align: 'center' },
  { title: '견적일자', dataIndex: 'estimate_date', width: 120, align: 'center' },
  { title: '작성자', dataIndex: 'creator_name', width: 120, align: 'center' },
  { title: '작성일시', dataIndex: 'created_at', width: 160, align: 'center' },
  { title: '경쟁사', dataIndex: 'competitor', width: 150, align: 'center', ellipsis: true },
  { title: '견적가', key: 'estimate_price', dataIndex: 'estimate_price', width: 140, align: 'right' },
  { title: '매출원가', key: 'sales_cost', dataIndex: 'sales_cost', width: 140, align: 'right' },
  { title: '판관비', key: 'overhead_amount', dataIndex: 'overhead_amount', width: 140, align: 'right' },
  { title: '세전이익', key: 'profit_amount', dataIndex: 'profit_amount', width: 140, align: 'right' },
  { title: '관리', key: 'action', width: 90, align: 'center', fixed: 'right' },
]

const overheadRate = computed(() => {
  const currentYear = Number(form.estimate_date?.slice(0, 4) || now.getFullYear())
  const matched = overheadRates.value.find(row => Number(row.rate_year) === currentYear) || overheadRates.value[0]
  return Number(matched?.overhead_rate || 0)
})

const calculatedOverhead = computed(() => Math.round(toNumber(form.estimate_price) * overheadRate.value / 100))
const calculatedProfit = computed(() => toNumber(form.estimate_price) - toNumber(form.sales_cost) - calculatedOverhead.value)
const modalTitle = computed(() => {
  if (viewOnly.value) return '견적 상세'
  return editItem.value ? '견적 수정' : '견적 등록'
})
const currentUserId = computed(() => auth.user?.id ?? auth.user?.user_id ?? null)

function createEmptyForm() {
  return {
    estimate_no: '',
    design_no: '',
    project_name: '',
    region: '',
    business_division: '',
    sales_manager: '',
    submit_to: '',
    client_name: '',
    expected_order_date: null,
    delivery_date: null,
    estimate_date: null,
    competitor: '',
    estimate_price: 0,
    sales_cost: 0,
    notes: '',
  }
}

function splitEstimateNotes(notes) {
  const raw = notes || ''
  const idx = raw.indexOf(ESTIMATE_META_MARKER)
  if (idx < 0) return { memo: raw, meta: {} }
  try {
    return {
      memo: raw.slice(0, idx),
      meta: JSON.parse(raw.slice(idx + ESTIMATE_META_MARKER.length)) || {},
    }
  } catch {
    return { memo: raw, meta: {} }
  }
}

function normalizeEstimate(row) {
  const { memo, meta } = splitEstimateNotes(row.notes)
  const estimatePrice = toNumber(row.total_amount)
  const salesCost = toNumber(row.expense_amount)
  return {
    ...row,
    notes: memo,
    design_no: meta.design_no || '',
    project_name: row.title || '',
    region: meta.region || '',
    business_division: meta.business_division || '',
    sales_manager: meta.sales_manager || '',
    submit_to: meta.submit_to || '',
    client_name: meta.client_name || '',
    expected_order_date: meta.expected_order_date || null,
    delivery_date: meta.delivery_date || null,
    competitor: meta.competitor || '',
    estimate_price: estimatePrice,
    sales_cost: salesCost,
    overhead_amount: toNumber(row.overhead_amount),
    profit_amount: toNumber(row.profit_amount),
  }
}

function buildEstimateNo() {
  const year = String(now.getFullYear()).slice(-2)
  const prefix = `E${year}`
  const maxSeq = items.value.reduce((max, item) => {
    const match = String(item.estimate_no || '').match(new RegExp(`^${prefix}(\\d{3})$`))
    return match ? Math.max(max, Number(match[1])) : max
  }, 0)
  return `${prefix}${String(maxSeq + 1).padStart(3, '0')}`
}

async function load() {
  loading.value = true
  try {
    const [estimateRes, rateRes] = await Promise.all([
      salesApi.getEstimates({ search: search.value || undefined }),
      masterApi.getOverheadRates(),
    ])
    items.value = (estimateRes.data || []).map(normalizeEstimate)
    overheadRates.value = rateRes.data || []
  } finally {
    loading.value = false
  }
}

function canManageEstimate(item) {
  const ownerId = item?.created_by ?? null
  if (auth.isAdmin) return true
  if (currentUserId.value === null || ownerId === null) return false
  return Number(ownerId) === Number(currentUserId.value)
}

function estimateRowEvents(record) {
  return {
    onClick: () => openDrawer(record, 'view'),
  }
}

function openDrawer(item, mode = 'edit') {
  editItem.value = item
  viewOnly.value = !!item && mode === 'view'
  Object.assign(form, createEmptyForm())
  attachments.value = []
  pendingFiles.value = []
  if (item) {
    Object.assign(form, {
      estimate_no: item.estimate_no || '',
      design_no: item.design_no || '',
      project_name: item.project_name || '',
      region: item.region || '',
      business_division: item.business_division || '',
      sales_manager: item.sales_manager || '',
      submit_to: item.submit_to || '',
      client_name: item.client_name || '',
      expected_order_date: item.expected_order_date || null,
      delivery_date: item.delivery_date || null,
      estimate_date: item.estimate_date || null,
      competitor: item.competitor || '',
      estimate_price: toNumber(item.estimate_price),
      sales_cost: toNumber(item.sales_cost),
      notes: item.notes || '',
    })
  } else {
    form.estimate_no = buildEstimateNo()
    form.estimate_date = today()
  }
  drawerOpen.value = true
  if (item?.id) {
    loadAttachments(item.id)
  }
}

async function loadAttachments(estimateId) {
  const res = await salesApi.getEstimateAttachments(estimateId)
  attachments.value = res.data || []
}

function buildPayload() {
  const meta = {
    design_no: form.design_no,
    region: form.region,
    business_division: form.business_division,
    sales_manager: form.sales_manager,
    submit_to: form.submit_to,
    client_name: form.client_name,
    expected_order_date: form.expected_order_date,
    delivery_date: form.delivery_date,
    competitor: form.competitor,
  }
  return {
    estimate_no: form.estimate_no,
    title: form.project_name,
    client_id: null,
    estimate_type: 'bas',
    estimate_date: form.estimate_date,
    total_amount: toNumber(form.estimate_price),
    labor_amount: 0,
    material_amount: 0,
    subcontract_amount: 0,
    expense_amount: toNumber(form.sales_cost),
    overhead_amount: calculatedOverhead.value,
    profit_amount: calculatedProfit.value,
    status: 'draft',
    notes: `${form.notes || ''}${ESTIMATE_META_MARKER}${JSON.stringify(meta)}`,
    items: [],
  }
}

async function handleSave() {
  if (viewOnly.value) return
  try {
    await formRef.value.validate()
    saving.value = true
    const payload = buildPayload()
    let saved
    if (editItem.value) {
      saved = await salesApi.updateEstimate(editItem.value.id, payload)
      message.success('수정되었습니다.')
    } else {
      saved = await salesApi.createEstimate(payload)
      message.success('등록되었습니다.')
    }
    await uploadPendingFiles(saved.data?.id || editItem.value?.id)
    drawerOpen.value = false
    await load()
  } catch (e) {
    if (e?.errorFields) return
    message.error(e.response?.data?.detail || '저장 중 오류가 발생했습니다.')
  } finally {
    saving.value = false
  }
}

async function deleteEstimate(item) {
  try {
    await salesApi.deleteEstimate(item.id)
    message.success('견적이 삭제되었습니다.')
    if (editItem.value?.id === item.id) {
      drawerOpen.value = false
    }
    await load()
  } catch (e) {
    message.error(e.response?.data?.detail || '삭제 중 오류가 발생했습니다.')
  }
}

function beforeUpload() {
  return false
}

async function uploadPendingFiles(estimateId) {
  if (!estimateId || pendingFiles.value.length === 0) return
  await Promise.all(pendingFiles.value.map(file => {
    const formData = new FormData()
    formData.append('file', file.originFileObj || file)
    return salesApi.uploadEstimateAttachment(estimateId, formData)
  }))
  pendingFiles.value = []
}

function downloadAttachment(item) {
  window.open(`/api/estimate-attachments/${item.id}/download`, '_blank')
}

async function deleteAttachment(item) {
  await salesApi.deleteEstimateAttachment(item.id)
  attachments.value = attachments.value.filter(row => row.id !== item.id)
  message.success('첨부파일이 삭제되었습니다.')
}

function toNumber(value) {
  const parsed = Number(String(value ?? 0).replace(/,/g, ''))
  return Number.isFinite(parsed) ? parsed : 0
}

function amountFormatter(value) {
  return value ? `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : ''
}

function amountParser(value) {
  return value ? Number(`${value}`.replace(/,/g, '')) : 0
}

function formatAmount(value) {
  const amount = toNumber(value)
  return amount ? amount.toLocaleString() : '-'
}

function formatFileSize(value) {
  const size = Number(value || 0)
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  if (size >= 1024) return `${Math.round(size / 1024).toLocaleString()} KB`
  return `${size.toLocaleString()} B`
}

function today() {
  const yyyy = now.getFullYear()
  const mm = String(now.getMonth() + 1).padStart(2, '0')
  const dd = String(now.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.num-cell { display: block; text-align: right; }
.title-link { padding: 0; height: auto; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.page-wrap :deep(.ant-table-row) { cursor: pointer; }
.field-hint { color: #8c8c8c; font-size: 12px; font-weight: 400; }
.attachment-list { margin-top: 10px; border: 1px solid #f0f0f0; border-radius: 6px; }
.drawer-footer { display: flex; justify-content: flex-end; gap: 8px; }
.estimate-form :deep(.ant-col-8),
.estimate-form :deep(.ant-col-12),
.estimate-form :deep(.ant-col-24) {
  flex: 0 0 50%;
  max-width: 50%;
}
.estimate-form :deep(.ant-input),
.estimate-form :deep(.ant-input-number),
.estimate-form :deep(.ant-picker),
.estimate-form :deep(.ant-select) {
  max-width: 100%;
}
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
</style>
