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
          <a-select v-model:value="filterStatus" allow-clear placeholder="상태" style="width:110px" @change="load">
            <a-select-option value="진행">진행</a-select-option>
            <a-select-option value="완료">완료</a-select-option>
            <a-select-option value="해지">해지</a-select-option>
          </a-select>
          <a-button type="primary" @click="openDrawer(null)">
            <template #icon><PlusOutlined /></template>계약 등록
          </a-button>
        </a-space>
      </template>

      <a-table :columns="columns" :data-source="items" :loading="loading"
               :pagination="{ pageSize: 20, showSizeChanger: true }"
               row-key="id" size="middle" :scroll="{ x: 1000 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'contract_amount'">{{ fmt(record.contract_amount) }}</template>
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

    <a-drawer v-model:open="drawerOpen" :title="editItem ? '계약 수정' : '계약 등록'"
              width="520" :body-style="{ paddingBottom:'72px' }">
      <a-form :model="form" layout="vertical" ref="formRef">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="계약번호" name="contract_no">
              <a-input v-model:value="form.contract_no" placeholder="자동 입력 가능" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="계약 구분" name="contract_type">
              <a-select v-model:value="form.contract_type">
                <a-select-option v-for="t in CONTRACT_TYPES" :key="t" :value="t">{{ t }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="계약명" name="contract_name"
              :rules="[{ required: true, message: '계약명을 입력하세요.' }]">
              <a-input v-model:value="form.contract_name" />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="프로젝트" name="project_id">
              <a-select v-model:value="form.project_id" allow-clear placeholder="프로젝트 선택"
                        :options="projectOptions" option-filter-prop="label" show-search />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="거래처" name="vendor_name"
              :rules="[{ required: true, message: '거래처명을 입력하세요.' }]"
              extra="직접 입력하거나 등록된 거래처를 검색하세요.">
              <a-auto-complete v-model:value="form.vendor_name" :options="vendorSuggestions"
                               placeholder="거래처명 입력" allow-clear
                               @select="onVendorSelect" @change="onVendorChange" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="계약금액 (원)" name="contract_amount">
              <a-input-number v-model:value="form.contract_amount" style="width:100%"
                              :min="0" :formatter="fmtNum" :parser="parseNum" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="상태" name="status">
              <a-select v-model:value="form.status">
                <a-select-option v-for="s in ['진행','완료','해지']" :key="s" :value="s">{{ s }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="계약 시작일" name="start_date">
              <a-date-picker v-model:value="form.start_date" style="width:100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="계약 종료일" name="end_date">
              <a-date-picker v-model:value="form.end_date" style="width:100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="비고" name="notes">
              <a-textarea v-model:value="form.notes" :rows="3" />
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
import { FileTextOutlined, CheckCircleOutlined, CloseCircleOutlined, PlusOutlined, DollarOutlined } from '@ant-design/icons-vue'
import { executionApi, masterApi } from '@/api'

const CONTRACT_TYPES = ['자재', '노무', '외주', '장비', '기타']
const statusColor    = { 진행: 'blue', 완료: 'green', 해지: 'red' }

const items = ref([]), projects = ref([]), companies = ref([])
const loading = ref(false), saving = ref(false), drawerOpen = ref(false)
const editItem = ref(null), formRef = ref()
const filterProject = ref(null), filterStatus = ref(null)

const emptyForm = { contract_no:'', project_id:null, vendor_name:'', vendor_id:null,
  contract_name:'', contract_type:'자재', contract_amount:0, start_date:null, end_date:null, status:'진행', notes:'' }
const form = reactive({ ...emptyForm })

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

const statsCards = computed(() => [
  { key:'total', label:'전체',  value: items.value.length,                              color:'#1a2535', cls:'',            iconCls:'icon-gray',   icon: FileTextOutlined },
  { key:'act',   label:'진행',  value: items.value.filter(r=>r.status==='진행').length, color:'#1677ff', cls:'stat-blue',   iconCls:'icon-blue',   icon: FileTextOutlined },
  { key:'done',  label:'완료',  value: items.value.filter(r=>r.status==='완료').length, color:'#52c41a', cls:'stat-green',  iconCls:'icon-green',  icon: CheckCircleOutlined },
  { key:'term',  label:'해지',  value: items.value.filter(r=>r.status==='해지').length, color:'#f5222d', cls:'stat-red',    iconCls:'icon-red',    icon: CloseCircleOutlined },
  { key:'amt',   label:'계약금액 합계(백만)', value: Math.round(items.value.reduce((s,r)=>s+(r.contract_amount||0),0)/1e6).toLocaleString(),
    color:'#722ed1', cls:'stat-purple', iconCls:'icon-purple', icon: DollarOutlined },
])

const columns = [
  { title: '계약번호', dataIndex: 'contract_no',    width: 140, align: 'center' },
  { title: '계약명',  dataIndex: 'contract_name',   width: 200, align: 'center', ellipsis: true },
  { title: '프로젝트', dataIndex: 'project_name',   width: 170, align: 'center', ellipsis: true },
  { title: '거래처',  dataIndex: 'vendor_name',     width: 160, align: 'center', ellipsis: true },
  { title: '구분',    dataIndex: 'contract_type',   width: 80,  align: 'center' },
  { title: '계약금액', key: 'contract_amount',      width: 140, align: 'right' },
  { title: '상태',    key: 'status',                width: 80,  align: 'center' },
  { title: '관리',    key: 'action',                width: 100, align: 'center', fixed: 'right' },
]

function onVendorSelect(value, option) { form.vendor_id = option.id ?? null }
function onVendorChange(value) {
  const m = companies.value.find(c => c.company_name === value)
  form.vendor_id = m ? m.id : null
}

async function load() {
  loading.value = true
  try {
    const [c, proj, co] = await Promise.all([
      executionApi.getPurchaseContracts({ project_id: filterProject.value || undefined, status: filterStatus.value || undefined }),
      executionApi.getProjects(),
      masterApi.getCompanies(),
    ])
    items.value    = c.data
    projects.value = proj.data
    companies.value = co.data
  } finally { loading.value = false }
}

function openDrawer(item) {
  editItem.value = item
  Object.assign(form, item ? { ...item } : emptyForm)
  drawerOpen.value = true
}

async function handleSave() {
  try {
    await formRef.value.validate(); saving.value = true
    if (editItem.value) { await executionApi.updatePurchaseContract(editItem.value.id, form); message.success('수정되었습니다.') }
    else                { await executionApi.createPurchaseContract(form); message.success('등록되었습니다.') }
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
:deep(.ant-table-thead > tr > th) { text-align:center !important; background:#fafafa; }
:deep(.ant-card-head) { border-bottom:1px solid #f0f0f0; min-height:52px; }
</style>
