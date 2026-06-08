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
               :pagination="{ pageSize: 20, showSizeChanger: true }"
               row-key="id" size="middle" :scroll="{ x: 1050 }">
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
              <a-popconfirm title="삭제하시겠습니까?" ok-text="삭제" ok-type="danger" cancel-text="취소"
                            @confirm="handleDelete(record.id)">
                <a class="del-link">삭제</a>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-drawer v-model:open="drawerOpen" :title="editItem ? '청구 수정' : '청구 등록'"
              width="540" :body-style="{ paddingBottom:'72px' }">
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
          <a-col :span="24">
            <a-form-item label="프로젝트" name="project_id">
              <a-select v-model:value="form.project_id" allow-clear show-search
                        placeholder="프로젝트 선택" :options="projectOptions"
                        option-filter-prop="label" @change="onProjectChange" />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="발주처" name="client_name">
              <a-input v-model:value="form.client_name" placeholder="발주처명" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">청구 금액</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="청구일" name="bill_date">
              <a-date-picker v-model:value="form.bill_date" style="width:100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="지급기한" name="due_date">
              <a-date-picker v-model:value="form.due_date" style="width:100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="공급가액 (원)" name="bill_amount">
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
        </a-row>

        <a-divider orientation="left" orientation-margin="0"><span class="sec-label">세금계산서</span></a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="세금계산서 번호" name="invoice_no">
              <a-input v-model:value="form.invoice_no" placeholder="발행 후 입력" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="발행일" name="invoice_date">
              <a-date-picker v-model:value="form.invoice_date" style="width:100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="비고" name="notes">
              <a-textarea v-model:value="form.notes" :rows="2" />
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
    </a-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { FileTextOutlined, ClockCircleOutlined, CheckCircleOutlined, CheckOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { executionApi } from '@/api'

const STATUSES    = ['발행요청', '발행완료', '확인']
const statusColor = { 발행요청:'orange', 발행완료:'blue', 확인:'green' }

const items = ref([]), projects = ref([])
const loading = ref(false), saving = ref(false), drawerOpen = ref(false)
const editItem = ref(null), formRef = ref()
const filterProject = ref(null), filterStatus = ref(null)

const emptyForm = { bill_no:'', project_id:null, client_name:'', bill_amount:0, vat_amount:0, total_amount:0,
  bill_date:null, due_date:null, invoice_no:'', invoice_date:null, status:'발행요청', notes:'' }
const form = reactive({ ...emptyForm })

const projectOptions = computed(() =>
  projects.value.map(p => ({ value: p.id, label: `[${p.project_no||'—'}] ${p.project_name}`, client_name: p.client_name }))
)
const fmtNum = v => v ? Number(v).toLocaleString() : ''
const parseNum = v => v.replace(/,/g, '')

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
  { title: '공급가액', key: 'bill_amount',        width: 130, align: 'right' },
  { title: '부가세',  key: 'vat_amount',          width: 110, align: 'right' },
  { title: '합계',    key: 'total_amount',        width: 130, align: 'right' },
  { title: '청구일',  dataIndex: 'bill_date',     width: 110, align: 'center' },
  { title: '세금계산서', dataIndex: 'invoice_no', width: 130, align: 'center' },
  { title: '상태',    key: 'status',              width: 90,  align: 'center' },
  { title: '관리',    key: 'action',              width: 100, align: 'center', fixed: 'right' },
]

function calcVat() {
  form.vat_amount   = Math.round((form.bill_amount || 0) * 0.1)
  form.total_amount = (form.bill_amount || 0) + form.vat_amount
}
function calcTotal() {
  form.total_amount = (form.bill_amount || 0) + (form.vat_amount || 0)
}
function onProjectChange(id) {
  const p = projects.value.find(p => p.id === id)
  if (p && p.client_name) form.client_name = p.client_name
}

async function load() {
  loading.value = true
  try {
    const [bills, proj] = await Promise.all([
      executionApi.getSalesBills({ project_id: filterProject.value||undefined, status: filterStatus.value||undefined }),
      executionApi.getProjects(),
    ])
    items.value    = bills.data
    projects.value = proj.data
  } finally { loading.value = false }
}

function openDrawer(item) {
  editItem.value = item
  Object.assign(form, item ? { ...item } : emptyForm)
  drawerOpen.value = true
}

async function handleSave() {
  try {
    saving.value = true
    if (editItem.value) { await executionApi.updateSalesBill(editItem.value.id, form); message.success('수정되었습니다.') }
    else                { await executionApi.createSalesBill(form); message.success('등록되었습니다.') }
    drawerOpen.value = false; load()
  } catch (e) { message.error(e.response?.data?.detail || '오류') }
  finally { saving.value = false }
}

async function handleDelete(id) {
  try { await executionApi.deleteSalesBill(id); message.success('삭제되었습니다.'); load() }
  catch (e) { message.error(e.response?.data?.detail || '삭제 오류') }
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
