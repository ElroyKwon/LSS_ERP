<template>
  <div>
    <CrudTable
      title="설계 의뢰"
      :columns="columns"
      :data="items"
      :loading="loading"
      :scroll-x="1260"
      :custom-row="designRowEvents"
      @create="openModal(null)"
    >
      <template #filters>
        <a-input-search
          v-model:value="search"
          placeholder="프로젝트명 검색"
          style="width: 200px"
          allow-clear
          @search="load"
        />
        <a-select
          v-model:value="filterStatus"
          placeholder="상태"
          style="width: 110px"
          allow-clear
          @change="load"
        >
          <a-select-option v-for="(label, val) in statusLabel" :key="val" :value="val">{{ label }}</a-select-option>
        </a-select>
      </template>

      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="statusColor[record.status]">{{ statusLabel[record.status] }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-space @click.stop>
            <a @click.stop="openModal(record)">수정</a>
            <a-divider type="vertical" />
            <a-popconfirm title="삭제하시겠습니까?" @confirm="handleDelete(record.id)">
              <a style="color: #e74c3c">삭제</a>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </CrudTable>

    <a-modal :mask-closable="false"
      v-model:open="modalOpen"
      :title="editItem ? '설계의뢰 수정' : '설계의뢰 신규 등록'"
      width="1120px"
      wrap-class-name="design-request-modal"
      @ok="handleSave"
      :confirm-loading="saving"
      ok-text="저장"
      cancel-text="취소"
    >
      <a-form :model="form" layout="vertical" ref="formRef" class="request-form">
        <div class="request-sheet">
          <div class="sheet-row project-row">
            <div class="section-cell">PROJECT</div>
            <div class="field-cell label-cell">PJT Name</div>
            <div class="field-cell wide-cell">
              <a-form-item name="project_name" :rules="[{ required: true, message: '프로젝트명을 입력하세요.' }]">
                <a-input v-model:value="form.project_name" placeholder="필수입력" />
              </a-form-item>
            </div>
          </div>

          <div class="sheet-row requester-row">
            <div class="section-cell">설계의뢰자</div>
            <div class="field-cell label-cell">부서명</div>
            <div class="field-cell">
              <a-form-item name="department">
                <a-input v-model:value="form.department" placeholder="필수입력" />
              </a-form-item>
            </div>
            <div class="field-cell label-cell">성명</div>
            <div class="field-cell">
              <a-form-item name="requester_name">
                <a-input v-model:value="form.requester_name" placeholder="필수입력" />
              </a-form-item>
            </div>
          </div>

          <div class="building-grid">
            <div class="section-cell building-title">건축정보</div>
            <div class="field-cell label-cell peach">개요</div>
            <div class="field-cell label-cell">면적 or 수전용량</div>
            <div class="field-cell">
              <a-form-item name="area_or_capacity">
                <a-input v-model:value="form.area_or_capacity" placeholder="예) 1,200㎡ / 5MW" />
              </a-form-item>
            </div>
            <div class="field-cell label-cell">위치</div>
            <div class="field-cell compact">
              <a-form-item name="location_city">
                <a-input v-model:value="form.location_city" placeholder="서울" />
              </a-form-item>
            </div>
            <div class="field-cell compact">
              <a-form-item name="location_district">
                <a-input v-model:value="form.location_district" placeholder="강남구" />
              </a-form-item>
            </div>
            <div class="field-cell label-cell peach">층수</div>
            <div class="field-cell label-cell">지상</div>
            <div class="field-cell floor-above-input">
              <a-form-item name="floors_above">
                <a-input-number v-model:value="form.floors_above" style="width:100%" :min="0" />
              </a-form-item>
            </div>
            <div class="field-cell label-cell floor-below-label">지하</div>
            <div class="field-cell floor-below-input">
              <a-form-item name="floors_below">
                <a-input-number v-model:value="form.floors_below" style="width:100%" :min="0" />
              </a-form-item>
            </div>
          </div>

          <div class="sheet-row">
            <div class="section-cell">설계단계</div>
            <div class="field-cell option-cell" v-for="v in DESIGN_STAGES" :key="v">
              <a-radio :checked="form.design_stage === v" @change="form.design_stage = v">{{ v }}</a-radio>
            </div>
            <div class="field-cell other-cell" v-if="form.design_stage === '기타'">
              <a-form-item name="design_stage_other">
                <a-input v-model:value="form.design_stage_other" placeholder="기타 내용 입력" />
              </a-form-item>
            </div>
          </div>

          <div class="sheet-row">
            <div class="section-cell">작업내용</div>
            <div class="field-cell option-cell" v-for="v in WORK_CONTENTS" :key="v">
              <a-radio :checked="form.work_content === v" @change="form.work_content = v">{{ v }}</a-radio>
            </div>
          </div>

          <div class="sheet-row">
            <div class="section-cell">설계대상</div>
            <div class="field-cell option-cell" v-for="v in DESIGN_TARGETS" :key="v">
              <a-checkbox :checked="form.design_targets.includes(v)" @change="toggleArray('design_targets', v, $event.target.checked)">
                {{ v }}
              </a-checkbox>
            </div>
            <div class="field-cell other-cell" v-if="form.design_targets.includes('기타')">
              <a-form-item name="design_targets_other">
                <a-input v-model:value="form.design_targets_other" placeholder="기타 내용 입력" />
              </a-form-item>
            </div>
          </div>

          <div class="sheet-row">
            <div class="section-cell">HMI</div>
            <div class="field-cell option-cell" v-for="v in HMI_OPTIONS" :key="v">
              <a-radio :checked="form.hmi === v" @change="form.hmi = v">{{ v }}</a-radio>
            </div>
            <div class="field-cell other-cell" v-if="form.hmi === '기타'">
              <a-form-item name="hmi_other">
                <a-input v-model:value="form.hmi_other" placeholder="기타 내용 입력" />
              </a-form-item>
            </div>
          </div>

          <div class="sheet-row">
            <div class="section-cell">컨트롤러</div>
            <div class="field-cell option-cell" v-for="v in CONTROLLER_OPTIONS" :key="v">
              <a-radio :checked="form.controller === v" @change="form.controller = v">{{ v }}</a-radio>
            </div>
            <div class="field-cell other-cell" v-if="form.controller === '기타'">
              <a-form-item name="controller_other">
                <a-input v-model:value="form.controller_other" placeholder="기타 내용 입력" />
              </a-form-item>
            </div>
          </div>

          <div class="sheet-row">
            <div class="section-cell">설계작업</div>
            <div class="field-cell option-cell" v-for="v in DESIGN_TASKS" :key="v">
              <a-checkbox :checked="form.design_tasks.includes(v)" @change="toggleArray('design_tasks', v, $event.target.checked)">
                {{ v }}
              </a-checkbox>
            </div>
          </div>

          <div class="contact-grid">
            <div class="section-cell contact-title">거래처 정보</div>
            <div class="field-cell label-cell peach">구분</div>
            <div class="field-cell label-cell peach company-col">상호</div>
            <div class="field-cell label-cell peach">담당자</div>
            <div class="field-cell label-cell peach">전화</div>
            <div class="field-cell label-cell peach">E-Mail</div>
            <template v-for="row in CONTACT_ROWS" :key="row.key">
              <div class="field-cell label-cell">{{ row.label }}</div>
              <div class="field-cell company-col">
                <a-form-item :name="`${row.key}_company`">
                  <a-select
                    v-if="row.companyField"
                    :value="form[row.companyField]"
                    show-search
                    allow-clear
                    placeholder="거래처 선택"
                    :filter-option="filterOpt"
                    @change="(val) => setContactCompany(row, val)"
                  >
                    <a-select-option v-for="c in companies" :key="c.id" :value="c.id">{{ c.company_name }}</a-select-option>
                  </a-select>
                  <a-input v-else v-model:value="form.partner_contacts[row.key].company_name" placeholder="상호 입력" />
                </a-form-item>
              </div>
              <div class="field-cell">
                <a-form-item :name="`${row.key}_manager`">
                  <a-input v-model:value="form.partner_contacts[row.key].manager" />
                </a-form-item>
              </div>
              <div class="field-cell">
                <a-form-item :name="`${row.key}_phone`">
                  <a-input v-model:value="form.partner_contacts[row.key].phone" />
                </a-form-item>
              </div>
              <div class="field-cell">
                <a-form-item :name="`${row.key}_email`">
                  <a-input v-model:value="form.partner_contacts[row.key].email" />
                </a-form-item>
              </div>
            </template>
          </div>

          <div class="sheet-row period-row">
            <div class="section-cell">작업기간</div>
            <div class="field-cell label-cell">의뢰일</div>
            <div class="field-cell">
              <a-form-item name="request_date">
                <a-date-picker v-model:value="form.request_date" style="width: 100%" value-format="YYYY-MM-DD" />
              </a-form-item>
            </div>
            <div class="field-cell label-cell">완료(요구)일</div>
            <div class="field-cell">
              <a-form-item name="due_date">
                <a-date-picker v-model:value="form.due_date" style="width: 100%" value-format="YYYY-MM-DD" />
              </a-form-item>
            </div>
            <div class="field-cell label-cell">소요시간</div>
            <div class="field-cell">
              <a-form-item name="required_hours">
                <a-input-number v-model:value="form.required_hours" style="width:100%" :min="0" addon-after="h" />
              </a-form-item>
            </div>
          </div>

          <div class="special-row">
            <div class="section-cell special-section">특기사항</div>
            <div class="special-lines">
              <div class="special-line" v-for="n in 11" :key="n">
                <span class="line-no">{{ n }}</span>
                <a-input v-model:value="form.special_notes[n - 1]" />
              </div>
            </div>
          </div>
        </div>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="viewerOpen"
      title="설계의뢰 상세"
      width="920px"
      wrap-class-name="design-request-viewer-modal"
      :footer="null"
    >
      <div v-if="selectedItem" class="design-viewer">
        <header class="viewer-header">
          <div>
            <p class="viewer-kicker">DESIGN REQUEST</p>
            <h2>{{ selectedItem.project_name || '-' }}</h2>
          </div>
          <a-tag :color="statusColor[selectedItem.status]">{{ statusLabel[selectedItem.status] || '-' }}</a-tag>
        </header>

        <section class="viewer-section">
          <h3>기본 정보</h3>
          <div class="viewer-grid">
            <div><span>요청 부서</span><strong>{{ selectedItem.department || '-' }}</strong></div>
            <div><span>요청자</span><strong>{{ selectedItem.requester_name || '-' }}</strong></div>
            <div><span>의뢰일</span><strong>{{ selectedItem.request_date || '-' }}</strong></div>
            <div><span>완료(요구)일</span><strong>{{ selectedItem.due_date || '-' }}</strong></div>
            <div><span>발주처</span><strong>{{ selectedItem.order_company_name || '-' }}</strong></div>
            <div><span>건설사</span><strong>{{ selectedItem.construction_company_name || '-' }}</strong></div>
            <div><span>거래처</span><strong>{{ selectedItem.partner_company_name || '-' }}</strong></div>
            <div><span>소요시간</span><strong>{{ viewerReq.required_hours ?? '-' }} h</strong></div>
          </div>
        </section>

        <section class="viewer-section">
          <h3>건축 정보</h3>
          <div class="viewer-grid">
            <div><span>면적 or 수전용량</span><strong>{{ viewerReq.area_or_capacity || '-' }}</strong></div>
            <div><span>위치</span><strong>{{ compactText([viewerReq.location_city, viewerReq.location_district]) }}</strong></div>
            <div><span>지상</span><strong>{{ viewerReq.floors_above ?? '-' }}</strong></div>
            <div><span>지하</span><strong>{{ viewerReq.floors_below ?? '-' }}</strong></div>
          </div>
        </section>

        <section class="viewer-section">
          <h3>설계 조건</h3>
          <div class="viewer-grid">
            <div><span>설계단계</span><strong>{{ visibleValue(viewerReq.design_stage, viewerReq.design_stage_other) || '-' }}</strong></div>
            <div><span>작업내용</span><strong>{{ viewerReq.work_content || '-' }}</strong></div>
            <div><span>설계대상</span><strong>{{ designTargetsText(viewerReq) || '-' }}</strong></div>
            <div><span>HMI</span><strong>{{ visibleValue(viewerReq.hmi, viewerReq.hmi_other) || '-' }}</strong></div>
            <div><span>컨트롤러</span><strong>{{ visibleValue(viewerReq.controller, viewerReq.controller_other) || '-' }}</strong></div>
            <div><span>설계작업</span><strong>{{ listText(viewerReq.design_tasks) || '-' }}</strong></div>
          </div>
        </section>

        <section class="viewer-section">
          <h3>거래처 정보</h3>
          <div class="viewer-contact-table">
            <div class="viewer-contact-head">구분</div>
            <div class="viewer-contact-head">상호</div>
            <div class="viewer-contact-head">담당자</div>
            <div class="viewer-contact-head">전화</div>
            <div class="viewer-contact-head">E-Mail</div>
            <template v-for="row in CONTACT_ROWS" :key="row.key">
              <div>{{ row.label }}</div>
              <div>{{ viewerContact(row.key).company_name || '-' }}</div>
              <div>{{ viewerContact(row.key).manager || '-' }}</div>
              <div>{{ viewerContact(row.key).phone || '-' }}</div>
              <div>{{ viewerContact(row.key).email || '-' }}</div>
            </template>
          </div>
        </section>

        <section class="viewer-section" v-if="viewerNotes.length">
          <h3>특기사항</h3>
          <ol class="viewer-note-list">
            <li v-for="note in viewerNotes" :key="note.index">
              <span>{{ note.index }}</span>
              <p>{{ note.text }}</p>
            </li>
          </ol>
        </section>

        <section class="viewer-section" v-if="viewerMemo">
          <h3>메모</h3>
          <p class="viewer-memo">{{ viewerMemo }}</p>
        </section>

        <div class="viewer-actions">
          <a-popconfirm title="삭제하시겠습니까?" @confirm="deleteFromViewer">
            <a-button danger>삭제</a-button>
          </a-popconfirm>
          <a-space>
            <a-button @click="viewerOpen = false">닫기</a-button>
            <a-button type="primary" @click="editFromViewer">수정</a-button>
          </a-space>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { computed, ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import CrudTable from '@/components/common/CrudTable.vue'
import { salesApi, masterApi } from '@/api'

const REQ_MARKER = '\n---설계요구사항---\n'
const DESIGN_STAGES = ['기본설계 DD', '실시설계 CD', 'SHOP', '기타']
const WORK_CONTENTS = ['신규설계', '치환설계']
const DESIGN_TARGETS = ['기계설비', '전력설비', '조명설비', 'DCIM', 'SI 류', '기타']
const HMI_OPTIONS = ['LSS EcoV', 'SVC', 'Smart-xD', 'TOUCH', '기타']
const CONTROLLER_OPTIONS = ['Modulo 6', 'PLC', '기타']
const DESIGN_TASKS = ['계통작업', '스케쥴', '평면작업', '견적작업', '시방서', '제안서']
const CONTACT_ROWS = [
  { key: 'client', label: '발주처', companyField: 'order_company_id' },
  { key: 'construction', label: '건설사', companyField: 'construction_company_id' },
  { key: 'mechanical_design', label: '기계설계' },
  { key: 'electrical_design', label: '전기설계' },
  { key: 'other', label: '기타', companyField: 'partner_company_id' },
]

const items = ref([])
const companies = ref([])
const loading = ref(false)
const saving = ref(false)
const modalOpen = ref(false)
const viewerOpen = ref(false)
const editItem = ref(null)
const selectedItem = ref(null)
const search = ref('')
const filterStatus = ref(undefined)
const formRef = ref()

const statusLabel = {
  received: '접수',
  in_progress: '진행중',
  completed: '완료',
  cancelled: '취소',
}
const statusColor = {
  received: 'orange',
  in_progress: 'blue',
  completed: 'green',
  cancelled: 'red',
}

const emptyContacts = () => ({
  client: { company_name: '', manager: '', phone: '', email: '' },
  construction: { company_name: '', manager: '', phone: '', email: '' },
  mechanical_design: { company_name: '', manager: '', phone: '', email: '' },
  electrical_design: { company_name: '', manager: '', phone: '', email: '' },
  other: { company_name: '', manager: '', phone: '', email: '' },
})

const makeEmptyForm = () => ({
  project_name: '',
  department: '',
  requester_name: '',
  order_company_id: null,
  construction_company_id: null,
  partner_company_id: null,
  request_date: null,
  due_date: null,
  status: 'received',
  notes: '',
  building_summary: '',
  area_or_capacity: '',
  location_city: '',
  location_district: '',
  floors_above: null,
  floors_below: null,
  design_stage: '기본설계 DD',
  design_stage_other: '',
  work_content: '신규설계',
  design_targets: [],
  design_targets_other: '',
  hmi: undefined,
  hmi_other: '',
  controller: undefined,
  controller_other: '',
  design_tasks: [],
  partner_contacts: emptyContacts(),
  required_hours: null,
  special_notes: Array(11).fill(''),
})
const form = reactive(makeEmptyForm())

const columns = [
  { title: '프로젝트명', dataIndex: 'project_name', width: 220, align: 'center', ellipsis: true },
  { title: '요청 부서', dataIndex: 'department', width: 120, align: 'center' },
  { title: '요청자 성명', dataIndex: 'requester_name', width: 120, align: 'center' },
  { title: '발주처', dataIndex: 'order_company_name', width: 160, ellipsis: true, align: 'center' },
  { title: '건설사', dataIndex: 'construction_company_name', width: 160, ellipsis: true, align: 'center' },
  { title: '거래처', dataIndex: 'partner_company_name', width: 160, ellipsis: true, align: 'center' },
  { title: '설계단계', dataIndex: 'design_stage_text', width: 140, align: 'center', ellipsis: true },
  { title: '설계대상', dataIndex: 'design_targets_text', width: 190, align: 'center', ellipsis: true },
  { title: '의뢰일', dataIndex: 'request_date', width: 110, align: 'center' },
  { title: '완료(요구)일', dataIndex: 'due_date', width: 120, align: 'center' },
  { title: '상태', key: 'status', width: 90, align: 'center' },
  { title: '관리', key: 'action', width: 90, align: 'center', fixed: 'right' },
]

const filterOpt = (input, opt) =>
  String(opt?.children?.[0] || '').toLowerCase().includes(input.toLowerCase())

async function load() {
  loading.value = true
  try {
    const [dr, co] = await Promise.all([
      salesApi.getDesignRequests({
        search: search.value || undefined,
        status: filterStatus.value || undefined,
      }),
      masterApi.getCompanies(),
    ])
    items.value = dr.data.map(withRequirementMeta)
    companies.value = co.data
  } finally {
    loading.value = false
  }
}

function splitNotes(notes) {
  const raw = notes || ''
  const idx = raw.indexOf(REQ_MARKER)
  if (idx < 0) return { memo: raw, req: {} }
  try {
    return { memo: raw.slice(0, idx), req: JSON.parse(raw.slice(idx + REQ_MARKER.length)) || {} }
  } catch {
    return { memo: raw, req: {} }
  }
}

function splitDesignNotes(item) {
  return splitNotes(item?.raw_notes ?? item?.notes)
}

function visibleValue(value, other) {
  return value === '기타' && other ? `기타(${other})` : value || ''
}

function buildNotes() {
  const req = {
    building_summary: form.building_summary,
    area_or_capacity: form.area_or_capacity,
    location_city: form.location_city,
    location_district: form.location_district,
    floors_above: form.floors_above,
    floors_below: form.floors_below,
    design_stage: form.design_stage,
    design_stage_other: form.design_stage_other,
    work_content: form.work_content,
    design_targets: form.design_targets,
    design_targets_other: form.design_targets_other,
    hmi: form.hmi,
    hmi_other: form.hmi_other,
    controller: form.controller,
    controller_other: form.controller_other,
    design_tasks: form.design_tasks,
    partner_contacts: form.partner_contacts,
    required_hours: form.required_hours,
    special_notes: form.special_notes,
  }
  return `${form.notes || ''}${REQ_MARKER}${JSON.stringify(req)}`
}

function withRequirementMeta(item) {
  const { memo, req } = splitNotes(item.notes)
  const targets = Array.isArray(req.design_targets) ? [...req.design_targets] : []
  if (targets.includes('기타') && req.design_targets_other) {
    targets[targets.indexOf('기타')] = `기타(${req.design_targets_other})`
  }
  return {
    ...item,
    raw_notes: item.notes,
    notes: memo,
    design_stage_text: visibleValue(req.design_stage, req.design_stage_other),
    design_targets_text: targets.join(', '),
  }
}

function toPayload() {
  return {
    project_name: form.project_name,
    department: form.department,
    requester_name: form.requester_name,
    order_company_id: form.order_company_id,
    construction_company_id: form.construction_company_id,
    partner_company_id: form.partner_company_id,
    request_date: form.request_date,
    due_date: form.due_date,
    status: form.status,
    notes: buildNotes(),
  }
}

function normalizeContacts(reqContacts = {}) {
  return {
    ...emptyContacts(),
    ...Object.fromEntries(
      Object.entries(reqContacts).map(([key, value]) => [
        key,
        { company_name: '', manager: '', phone: '', email: '', ...(value || {}) },
      ]),
    ),
  }
}

function resetForm(next) {
  Object.assign(form, makeEmptyForm(), next)
}

function openModal(item) {
  editItem.value = item
  if (item) {
    const { memo, req } = splitDesignNotes(item)
    resetForm({
      project_name: item.project_name || '',
      department: item.department || '',
      requester_name: item.requester_name || '',
      order_company_id: item.order_company_id || null,
      construction_company_id: item.construction_company_id || null,
      partner_company_id: item.partner_company_id || null,
      request_date: item.request_date || null,
      due_date: item.due_date || null,
      status: item.status || 'received',
      notes: memo || '',
      building_summary: req.building_summary || '',
      area_or_capacity: req.area_or_capacity || '',
      location_city: req.location_city || '',
      location_district: req.location_district || '',
      floors_above: req.floors_above ?? null,
      floors_below: req.floors_below ?? null,
      design_stage: req.design_stage || '기본설계 DD',
      design_stage_other: req.design_stage_other || '',
      work_content: req.work_content || '신규설계',
      design_targets: Array.isArray(req.design_targets) ? req.design_targets : [],
      design_targets_other: req.design_targets_other || '',
      hmi: req.hmi || undefined,
      hmi_other: req.hmi_other || '',
      controller: req.controller || undefined,
      controller_other: req.controller_other || '',
      design_tasks: Array.isArray(req.design_tasks) ? req.design_tasks : [],
      partner_contacts: normalizeContacts(req.partner_contacts),
      required_hours: req.required_hours ?? null,
      special_notes: Array.from({ length: 11 }, (_, i) => req.special_notes?.[i] || ''),
    })
  } else {
    resetForm()
  }
  modalOpen.value = true
}

const viewerParts = computed(() => splitDesignNotes(selectedItem.value))
const viewerReq = computed(() => viewerParts.value.req || {})
const viewerMemo = computed(() => viewerParts.value.memo || '')
const viewerNotes = computed(() =>
  (viewerReq.value.special_notes || [])
    .map((text, index) => ({ index: index + 1, text }))
    .filter((item) => String(item.text || '').trim()),
)

function compactText(parts) {
  return parts.filter(Boolean).join(' ') || '-'
}

function listText(value) {
  return Array.isArray(value) ? value.filter(Boolean).join(', ') : value || ''
}

function designTargetsText(req) {
  const targets = Array.isArray(req.design_targets) ? [...req.design_targets] : []
  if (targets.includes('기타') && req.design_targets_other) {
    targets[targets.indexOf('기타')] = `기타(${req.design_targets_other})`
  }
  return targets.filter(Boolean).join(', ')
}

function viewerContact(key) {
  return viewerReq.value.partner_contacts?.[key] || {}
}

function openViewer(item) {
  selectedItem.value = item
  viewerOpen.value = true
}

function editFromViewer() {
  if (!selectedItem.value) return
  viewerOpen.value = false
  openModal(selectedItem.value)
}

async function deleteFromViewer() {
  if (!selectedItem.value?.id) return
  await handleDelete(selectedItem.value.id)
  viewerOpen.value = false
}

function designRowEvents(record) {
  return {
    onClick: () => openViewer(record),
    onDblclick: () => openViewer(record),
    class: 'clickable-design-row',
  }
}

function toggleArray(field, value, checked) {
  const next = new Set(form[field])
  if (checked) next.add(value)
  else next.delete(value)
  form[field] = [...next]
}

function setContactCompany(row, value) {
  form[row.companyField] = value || null
  const company = companies.value.find((item) => item.id === value)
  form.partner_contacts[row.key].company_name = company?.company_name || ''
}

async function handleSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    if (editItem.value) {
      await salesApi.updateDesignRequest(editItem.value.id, toPayload())
      message.success('수정되었습니다.')
    } else {
      await salesApi.createDesignRequest(toPayload())
      message.success('등록되었습니다.')
    }
    modalOpen.value = false
    load()
  } catch (e) {
    if (e?.errorFields) return
    message.error(e.response?.data?.detail || '저장 중 오류가 발생했습니다.')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id) {
  try {
    await salesApi.deleteDesignRequest(id)
    message.success('삭제되었습니다.')
    load()
  } catch (e) {
    message.error(e.response?.data?.detail || '삭제 중 오류가 발생했습니다.')
  }
}

onMounted(load)
</script>

<style scoped>
.request-form {
  margin-top: 8px;
}
.request-sheet {
  border: 2px solid #1f1f1f;
  background: #fff;
  overflow-x: auto;
}
.sheet-row,
.special-row {
  display: grid;
  grid-template-columns: 120px repeat(6, minmax(130px, 1fr));
  min-width: 1040px;
  border-bottom: 1px solid #1f1f1f;
}
.sheet-row:last-child,
.special-row:last-child {
  border-bottom: 0;
}
.project-row {
  grid-template-columns: 120px 210px 1fr;
}
.requester-row {
  grid-template-columns: 120px 170px minmax(180px, 1fr) 170px minmax(180px, 1fr);
}
.building-grid {
  display: grid;
  grid-template-columns: 120px 116px 156px minmax(220px, 1fr) 156px minmax(130px, 1fr) minmax(130px, 1fr);
  min-width: 1040px;
  border-bottom: 1px solid #1f1f1f;
}
.building-title {
  grid-row: 1 / span 2;
}
.floor-below-input {
  grid-column: span 2;
}
.building-grid .field-cell:nth-child(n + 8) {
  border-top: 1px solid #1f1f1f;
}
.section-cell,
.field-cell {
  min-height: 36px;
  padding: 6px 8px;
  border-right: 1px dotted #6f6f6f;
  display: flex;
  align-items: center;
  justify-content: center;
}
.section-cell {
  background: #d6ffd6;
  border-right: 2px solid #1f1f1f;
  font-weight: 700;
  color: #111827;
  text-align: center;
  letter-spacing: 0;
}
.field-cell:last-child {
  border-right: 0;
}
.label-cell {
  background: #fff;
  font-weight: 500;
  color: #1f2937;
}
.peach {
  background: #fde7d9;
}
.wide-cell {
  justify-content: stretch;
}
.compact {
  min-width: 110px;
}
.status-cell {
  min-width: 120px;
}
.option-cell {
  justify-content: flex-start;
  min-width: 150px;
}
.other-cell {
  min-width: 220px;
}
.offset-left {
  grid-column-start: 2;
}
.contact-grid {
  display: grid;
  grid-template-columns: 120px 160px minmax(250px, 1.4fr) minmax(150px, 1fr) minmax(150px, 1fr) minmax(200px, 1.2fr);
  min-width: 1040px;
  border-bottom: 1px solid #1f1f1f;
}
.contact-title {
  grid-row: 1 / span 6;
  align-items: flex-start;
  padding-top: 16px;
}
.contact-grid .field-cell:nth-child(n + 7) {
  border-top: 1px dotted #6f6f6f;
}
.company-col {
  min-width: 250px;
}
.period-row {
  grid-template-columns: 120px 130px minmax(190px, 1fr) 150px minmax(190px, 1fr) 130px minmax(160px, 1fr);
}
.special-row {
  grid-template-columns: 120px 1fr;
}
.special-section {
  align-items: flex-start;
  padding-top: 14px;
}
.special-lines {
  display: flex;
  flex-direction: column;
}
.special-line {
  display: grid;
  grid-template-columns: 64px 1fr;
  min-height: 34px;
  border-bottom: 1px dotted #6f6f6f;
}
.special-line:last-child {
  border-bottom: 0;
}
.line-no {
  display: flex;
  align-items: center;
  justify-content: center;
  border-right: 1px dotted #6f6f6f;
  color: #1f2937;
}
:deep(.ant-form-item) {
  width: 100%;
  margin-bottom: 0;
}
:deep(.ant-input),
:deep(.ant-input-number),
:deep(.ant-picker),
:deep(.ant-select-selector) {
  border-radius: 4px !important;
}
:deep(.ant-input) {
  text-align: center;
}
:deep(.ant-checkbox-wrapper),
:deep(.ant-radio-wrapper) {
  margin-inline-end: 0;
  color: #111827;
}
:deep(.ant-table-thead > tr > th) {
  text-align: center !important;
}
:deep(.clickable-design-row) {
  cursor: pointer;
}
:deep(.clickable-design-row:hover > td) {
  background: #f0f7ff !important;
}
.design-viewer {
  background: #fff;
  color: #111827;
}
.viewer-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 4px 2px 18px;
  border-bottom: 2px solid #1f2937;
}
.viewer-kicker {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  color: #2563eb;
  letter-spacing: 0;
}
.viewer-header h2 {
  margin: 0;
  font-size: 22px;
  line-height: 1.35;
  font-weight: 800;
}
.viewer-section {
  padding: 18px 0;
  border-bottom: 1px solid #e5e7eb;
}
.viewer-section h3 {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 800;
  color: #1f4f8f;
}
.viewer-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border-top: 1px solid #edf0f3;
  border-left: 1px solid #edf0f3;
}
.viewer-grid > div {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  min-height: 42px;
  border-right: 1px solid #edf0f3;
  border-bottom: 1px solid #edf0f3;
}
.viewer-grid span,
.viewer-contact-head {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  background: #f8fafc;
  font-weight: 700;
  color: #475569;
}
.viewer-grid strong {
  display: flex;
  align-items: center;
  min-width: 0;
  padding: 8px 10px;
  font-weight: 500;
  white-space: pre-wrap;
  word-break: break-word;
}
.viewer-contact-table {
  display: grid;
  grid-template-columns: 100px minmax(160px, 1.2fr) minmax(100px, 0.8fr) minmax(120px, 0.9fr) minmax(180px, 1.3fr);
  border-top: 1px solid #edf0f3;
  border-left: 1px solid #edf0f3;
}
.viewer-contact-table > div {
  min-height: 38px;
  padding: 8px 10px;
  border-right: 1px solid #edf0f3;
  border-bottom: 1px solid #edf0f3;
  word-break: break-word;
}
.viewer-contact-head {
  padding: 8px;
}
.viewer-note-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.viewer-note-list li {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  min-height: 34px;
  border: 1px solid #edf0f3;
}
.viewer-note-list span {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
  font-weight: 700;
  color: #64748b;
}
.viewer-note-list p,
.viewer-memo {
  margin: 0;
  padding: 8px 10px;
  white-space: pre-wrap;
  word-break: break-word;
}
.viewer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 16px;
}

@media (max-width: 900px) {
  .viewer-grid {
    grid-template-columns: 1fr;
  }
  .viewer-contact-table {
    overflow-x: auto;
  }
}
</style>
