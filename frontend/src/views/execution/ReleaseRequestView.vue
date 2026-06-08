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
      <template #title><span class="card-title">출고 요청</span></template>
      <template #extra>
        <a-space>
          <a-select v-model:value="filterProject" allow-clear placeholder="프로젝트"
                    style="width:220px" :options="projectOptions" option-filter-prop="label"
                    show-search @change="load" />
          <a-select v-model:value="filterStatus" allow-clear placeholder="상태" style="width:110px" @change="load">
            <a-select-option v-for="s in STATUSES" :key="s" :value="s">{{ s }}</a-select-option>
          </a-select>
          <a-button type="primary" @click="openModal(null)">
            <template #icon><PlusOutlined /></template>출고 요청
          </a-button>
        </a-space>
      </template>

      <a-table :columns="columns" :data-source="items" :loading="loading"
               :pagination="{ pageSize: 20, showSizeChanger: true }"
               row-key="id" size="middle" :scroll="{ x: 950 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'quantity'">{{ record.quantity }} {{ record.unit }}</template>
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor[record.status]">{{ record.status }}</a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-space size="small">
              <a @click="openModal(record)">수정</a>
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

    <a-modal v-model:open="modalOpen" :title="editItem ? '출고 요청 수정' : '출고 요청 등록'"
             width="520px" @ok="handleSave" :confirm-loading="saving" ok-text="저장" cancel-text="취소">
      <a-form :model="form" layout="vertical" ref="formRef" style="margin-top:8px">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="요청번호" name="request_no">
              <a-input v-model:value="form.request_no" placeholder="자동 입력 가능" />
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
              <a-select v-model:value="form.project_id" allow-clear placeholder="프로젝트 선택"
                        :options="projectOptions" option-filter-prop="label" show-search />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="자재명" name="material_name"
              :rules="[{ required: true, message: '자재명을 입력하세요.' }]"
              extra="직접 입력하거나 등록된 자재를 검색하세요.">
              <a-auto-complete v-model:value="form.material_name" :options="materialSuggestions"
                               placeholder="자재명 입력" allow-clear
                               @select="onMaterialSelect" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="수량" name="quantity">
              <a-input-number v-model:value="form.quantity" style="width:100%" :min="0" :step="0.001" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="단위" name="unit">
              <a-input v-model:value="form.unit" placeholder="EA, m, kg …" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="요청일" name="request_date">
              <a-date-picker v-model:value="form.request_date" style="width:100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="필요일" name="needed_date">
              <a-date-picker v-model:value="form.needed_date" style="width:100%" value-format="YYYY-MM-DD" />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="비고" name="notes">
              <a-textarea v-model:value="form.notes" :rows="2" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { InboxOutlined, ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { executionApi, masterApi } from '@/api'

const STATUSES    = ['요청', '승인', '출고', '취소']
const statusColor = { 요청: 'orange', 승인: 'blue', 출고: 'green', 취소: 'red' }

const items = ref([]), projects = ref([]), materials = ref([])
const loading = ref(false), saving = ref(false), modalOpen = ref(false)
const editItem = ref(null), formRef = ref()
const filterProject = ref(null), filterStatus = ref(null)

const emptyForm = { request_no:'', project_id:null, material_name:'', material_id:null,
  quantity:0, unit:'', request_date:null, needed_date:null, status:'요청', notes:'' }
const form = reactive({ ...emptyForm })

const projectOptions = computed(() =>
  projects.value.map(p => ({ value: p.id, label: `[${p.project_no||'—'}] ${p.project_name}` }))
)
const materialSuggestions = computed(() =>
  materials.value.filter(m => !form.material_name || m.material_name.toLowerCase().includes((form.material_name||'').toLowerCase()))
    .map(m => ({ value: m.material_name, id: m.id, unit: m.unit }))
)

const statsCards = computed(() => [
  { key:'total', label:'전체',   value: items.value.length,                              color:'#1a2535', cls:'',           iconCls:'icon-gray',   icon: InboxOutlined },
  { key:'req',   label:'요청',   value: items.value.filter(r=>r.status==='요청').length, color:'#fa8c16', cls:'stat-orange', iconCls:'icon-orange', icon: ClockCircleOutlined },
  { key:'appr',  label:'승인',   value: items.value.filter(r=>r.status==='승인').length, color:'#1677ff', cls:'stat-blue',   iconCls:'icon-blue',   icon: CheckCircleOutlined },
  { key:'done',  label:'출고완료', value: items.value.filter(r=>r.status==='출고').length, color:'#52c41a', cls:'stat-green',  iconCls:'icon-green',  icon: CheckCircleOutlined },
])

const columns = [
  { title: '요청번호', dataIndex: 'request_no',   width: 140, align: 'center' },
  { title: '프로젝트', dataIndex: 'project_name', width: 180, align: 'center', ellipsis: true },
  { title: '자재명',  dataIndex: 'material_name', width: 200, align: 'center', ellipsis: true },
  { title: '수량/단위', key: 'quantity',           width: 110, align: 'center' },
  { title: '요청일',  dataIndex: 'request_date',  width: 110, align: 'center' },
  { title: '필요일',  dataIndex: 'needed_date',   width: 110, align: 'center' },
  { title: '상태',    key: 'status',              width: 90,  align: 'center' },
  { title: '관리',    key: 'action',              width: 100, align: 'center', fixed: 'right' },
]

function onMaterialSelect(value, option) {
  form.material_id = option.id ?? null
  if (option.unit) form.unit = option.unit
}

async function load() {
  loading.value = true
  try {
    const [r, proj, mat] = await Promise.all([
      executionApi.getReleaseRequests({ project_id: filterProject.value || undefined, status: filterStatus.value || undefined }),
      executionApi.getProjects(),
      masterApi.getMaterials(),
    ])
    items.value    = r.data
    projects.value = proj.data
    materials.value = mat.data
  } finally { loading.value = false }
}

function openModal(item) {
  editItem.value = item
  Object.assign(form, item ? { ...item } : emptyForm)
  modalOpen.value = true
}

async function handleSave() {
  try {
    await formRef.value.validate(); saving.value = true
    if (editItem.value) { await executionApi.updateReleaseRequest(editItem.value.id, form); message.success('수정되었습니다.') }
    else                { await executionApi.createReleaseRequest(form); message.success('등록되었습니다.') }
    modalOpen.value = false; load()
  } catch (e) { if (e?.errorFields) return; message.error(e.response?.data?.detail || '오류') }
  finally { saving.value = false }
}

async function handleDelete(id) {
  try { await executionApi.deleteReleaseRequest(id); message.success('삭제되었습니다.'); load() }
  catch (e) { message.error(e.response?.data?.detail || '삭제 오류') }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display:flex; flex-direction:column; gap:16px; }
.stat-card { border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,0.07); border-left:4px solid #e0e0e0; }
.stat-orange { border-left-color:#fa8c16; } .stat-blue  { border-left-color:#1677ff; }
.stat-green  { border-left-color:#52c41a; }
.stat-inner { display:flex; align-items:center; gap:14px; }
.stat-icon  { width:44px; height:44px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:20px; flex-shrink:0; }
.icon-gray   { background:#f0f2f5; color:#595959; } .icon-orange { background:#fff7e6; color:#fa8c16; }
.icon-blue   { background:#e6f4ff; color:#1677ff; } .icon-green  { background:#f6ffed; color:#52c41a; }
.stat-label { font-size:12px; color:#8c8c8c; margin-bottom:2px; }
.stat-value { font-size:22px; font-weight:700; color:#1a2535; line-height:1.2; }
.stat-unit  { font-size:12px; font-weight:400; margin-left:3px; color:#8c8c8c; }
.table-card { border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size:15px; font-weight:600; color:#1a2535; }
.del-link { color:#e74c3c; } .del-link:hover { color:#c0392b; }
:deep(.ant-table-thead > tr > th) { text-align:center !important; background:#fafafa; }
:deep(.ant-card-head) { border-bottom:1px solid #f0f0f0; min-height:52px; }
</style>
