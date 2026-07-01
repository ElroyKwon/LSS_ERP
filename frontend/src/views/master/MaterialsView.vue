<template>
  <div class="page-wrap">
    <a-row :gutter="16">
      <a-col :flex="1">
        <a-card :bordered="false" class="stat-card">
          <div class="stat-inner">
            <div class="stat-icon icon-gray"><InboxOutlined /></div>
            <div>
              <div class="stat-label">전체 자재</div>
              <div class="stat-value">{{ stats.total }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :flex="1">
        <a-card :bordered="false" class="stat-card stat-blue">
          <div class="stat-inner">
            <div class="stat-icon icon-blue"><BuildOutlined /></div>
            <div>
              <div class="stat-label">원재료</div>
              <div class="stat-value" style="color:#1677ff">{{ stats.raw }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :flex="1">
        <a-card :bordered="false" class="stat-card stat-green">
          <div class="stat-inner">
            <div class="stat-icon icon-green"><AppstoreOutlined /></div>
            <div>
              <div class="stat-label">부재료</div>
              <div class="stat-value" style="color:#52c41a">{{ stats.sub }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :flex="1">
        <a-card :bordered="false" class="stat-card stat-orange">
          <div class="stat-inner">
            <div class="stat-icon icon-orange"><ShoppingOutlined /></div>
            <div>
              <div class="stat-label">상품</div>
              <div class="stat-value" style="color:#fa8c16">{{ stats.goods }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <div class="type-guide">
      <span class="type-guide-title">계정구분</span>
      <span v-for="option in materialTypeOptions" :key="option.value" class="type-guide-item">
        {{ option.value }} {{ option.label }}
      </span>
    </div>

    <a-card :bordered="false" class="table-card">
      <template #title><span class="card-title">자재 관리</span></template>
      <template #extra>
        <a-space>
          <a-select v-model:value="filterType" placeholder="계정구분 전체" style="width:150px" allow-clear @change="resetAndLoad">
            <a-select-option v-for="option in materialTypeOptions" :key="option.value" :value="option.value">
              {{ option.value }}. {{ option.label }}
            </a-select-option>
          </a-select>
          <a-input-search
            v-model:value="search"
            placeholder="품번 / 품명 검색"
            style="width:220px"
            allow-clear
            @search="resetAndLoad"
          />
          <input ref="excelInput" type="file" accept=".xlsx,.xlsm,.xls" style="display:none" @change="handleExcelFile" />
          <a-button :loading="importing" @click="excelInput?.click()">
            <template #icon><UploadOutlined /></template>엑셀 업로드
          </a-button>
          <a-button @click="downloadTemplate">
            <template #icon><DownloadOutlined /></template>양식 다운로드
          </a-button>
          <a-button type="primary" @click="openEditor(null)">
            <template #icon><PlusOutlined /></template>신규 등록
          </a-button>
        </a-space>
      </template>

      <a-table
        :columns="columns"
        :data-source="items"
        :loading="loading"
        :pagination="tablePagination"
        row-key="id"
        size="middle"
        :scroll="{ x: 1890 }"
        @change="handleTableChange"
      
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'material_type'">
            <a-tag :color="typeColor[record.material_type]">{{ record.material_type || '-' }}</a-tag>
          </template>
          <template v-else-if="column.key === 'conversion_factor'">
            <span class="num-text">{{ formatPrice(record.conversion_factor) }}</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="openEditor(record)">
                <template #icon><EditOutlined /></template>수정
              </a-button>
              <a-popconfirm
                title="삭제하시겠습니까?"
                ok-text="삭제"
                cancel-text="취소"
                @confirm="handleDelete(record.id)"
              >
                <a-button type="link" size="small" danger>
                  <template #icon><DeleteOutlined /></template>삭제
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-modal
      v-model:open="editorOpen"
      :title="editItem ? '자재 수정' : '자재 신규 등록'"
      width="900px"
      wrap-class-name="material-editor-modal"
      :confirm-loading="saving"
      ok-text="저장"
      cancel-text="취소"
      @ok="handleSave"
    >
      <div class="legacy-editor">
        <div class="legacy-list">
          <div class="legacy-grid-head">
            <div></div>
            <div>품번</div>
            <div>품명</div>
            <div>규격</div>
          </div>
          <div class="legacy-grid-body">
            <div
              v-for="item in items"
              :key="item.id"
              :class="['legacy-grid-row', editItem?.id === item.id ? 'selected' : '']"
              @click="openEditor(item)"
            >
              <div class="check-cell-body">
                <a-checkbox
                  :checked="editItem?.id === item.id"
                  @click.stop
                  @change="openEditor(item)"
                />
              </div>
              <div>{{ item.material_code }}</div>
              <div>{{ item.material_name }}</div>
              <div>{{ item.spec }}</div>
            </div>
          </div>
          <div class="legacy-grid-foot"></div>
        </div>

        <a-form ref="formRef" :model="form" class="legacy-form">
          <a-tabs v-model:activeKey="activeTab" type="card" size="small" class="legacy-tabs">
            <a-tab-pane key="master" tab="MASTER/SPEC">
              <div class="spec-box">
                <FormLine label="회사코드" name="material_company_group_code" wide>
                  <a-input v-model:value="form.material_company_group_code" />
                </FormLine>
                <FormLine label="품번" name="material_code" required wide>
                  <a-input v-model:value="form.material_code" />
                </FormLine>
                <FormLine label="품명" name="material_name" required wide>
                  <a-input v-model:value="form.material_name" />
                </FormLine>
                <FormLine label="규격" name="spec" wide>
                  <a-input v-model:value="form.spec" />
                </FormLine>

                <div class="two-col">
                  <FormLine label="계정구분" name="material_type">
                    <a-select v-model:value="form.material_type">
                      <a-select-option v-for="option in materialTypeOptions" :key="option.value" :value="option.value">
                        {{ option.value }}. {{ option.label }}
                      </a-select-option>
                    </a-select>
                  </FormLine>
                  <FormLine label="조달구분" name="procurement_type">
                    <a-select v-model:value="form.procurement_type">
                      <a-select-option value="purchase">0. 구매</a-select-option>
                      <a-select-option value="make">1. 생산</a-select-option>
                      <a-select-option value="outsourcing">2. 외주</a-select-option>
                    </a-select>
                  </FormLine>
                </div>

                <div class="three-col">
                  <FormLine label="재고단위" name="unit">
                    <a-input v-model:value="form.unit" class="small-unit-input" />
                  </FormLine>
                  <FormLine label="관리단위" name="management_unit">
                    <a-input v-model:value="form.management_unit" class="small-unit-input" />
                  </FormLine>
                  <FormLine label="환산계수" name="conversion_factor">
                    <a-input-number v-model:value="form.conversion_factor" :precision="6" class="conversion-input" />
                    <a-button class="mini-button" @click="setDefaultConversion">F2</a-button>
                  </FormLine>
                </div>

                <div class="two-col">
                  <FormLine label="품목군" name="item_group_code">
                    <a-input v-model:value="form.item_group_code" class="code-input" />
                    <a-button class="icon-button" @click="openLookup('itemGroup', 'item_group_code', 'item_group_name')"><SearchOutlined /></a-button>
                    <a-input v-model:value="form.item_group_name" />
                  </FormLine>
                  <div></div>
                </div>

                <div class="two-col">
                  <FormLine label="LOT여부" name="lot_use_yn">
                    <a-select v-model:value="form.lot_use_yn">
                      <a-select-option value="N">0. 미사용</a-select-option>
                      <a-select-option value="Y">1. 사용</a-select-option>
                    </a-select>
                  </FormLine>
                  <FormLine label="SET품목" name="set_item_yn">
                    <a-select v-model:value="form.set_item_yn">
                      <a-select-option value="N">0. 부</a-select-option>
                      <a-select-option value="Y">1. 여</a-select-option>
                    </a-select>
                  </FormLine>
                </div>

                <div class="two-col">
                  <FormLine label="검사여부" name="inspection_type">
                    <a-select v-model:value="form.inspection_type">
                      <a-select-option value="none">0. 무검사</a-select-option>
                      <a-select-option value="incoming">1. 입고검사</a-select-option>
                      <a-select-option value="final">2. 최종검사</a-select-option>
                    </a-select>
                  </FormLine>
                  <FormLine label="사용여부" name="use_yn">
                    <a-select v-model:value="form.use_yn">
                      <a-select-option value="Y">1. 사용</a-select-option>
                      <a-select-option value="N">0. 미사용</a-select-option>
                    </a-select>
                  </FormLine>
                </div>

                <div class="two-col">
                  <FormLine label="LOT수량" name="lot_quantity">
                    <a-input-number v-model:value="form.lot_quantity" :precision="2" />
                  </FormLine>
                  <FormLine label="BATCH수량" name="batch_quantity">
                    <a-input-number v-model:value="form.batch_quantity" :precision="2" />
                  </FormLine>
                </div>

                <div class="two-col">
                  <FormLine label="도면번호" name="drawing_no">
                    <a-input v-model:value="form.drawing_no" />
                  </FormLine>
                  <FormLine label="BARCODE" name="barcode">
                    <a-input v-model:value="form.barcode" />
                  </FormLine>
                </div>

                <div class="two-col">
                  <FormLine label="HS CODE" name="hs_code">
                    <a-input v-model:value="form.hs_code" />
                  </FormLine>
                  <FormLine label="재질" name="material_quality">
                    <a-input v-model:value="form.material_quality" />
                  </FormLine>
                </div>

                <div class="two-col">
                  <FormLine label="폭" name="width_value">
                    <a-input-number v-model:value="form.width_value" :precision="6" />
                    <a-input v-model:value="form.width_unit" class="unit-input" />
                  </FormLine>
                  <FormLine label="길이" name="length_value">
                    <a-input-number v-model:value="form.length_value" :precision="6" />
                    <a-input v-model:value="form.length_unit" class="unit-input" />
                  </FormLine>
                </div>

                <div class="two-col">
                  <FormLine label="높이" name="height_value">
                    <a-input-number v-model:value="form.height_value" :precision="6" />
                    <a-input v-model:value="form.height_unit" class="unit-input" />
                  </FormLine>
                  <FormLine label="밀도" name="density_value">
                    <a-input-number v-model:value="form.density_value" :precision="6" />
                  </FormLine>
                </div>

                <div class="two-col">
                  <FormLine label="부피" name="depth_value">
                    <a-input-number v-model:value="form.depth_value" :precision="6" />
                    <a-input v-model:value="form.depth_unit" class="unit-input" />
                    <a-button class="calc-button" @click="calculateVolume">부피계산(F2)</a-button>
                  </FormLine>
                  <div></div>
                </div>

                <div class="two-col">
                  <FormLine label="중량" name="weight_value">
                    <a-input-number v-model:value="form.weight_value" :precision="6" />
                    <a-input v-model:value="form.weight_unit" class="unit-input" />
                    <a-button class="calc-button" @click="calculateWeight">중량계산(F2)</a-button>
                  </FormLine>
                  <div></div>
                </div>

                <div class="two-col">
                  <FormLine label="면적" name="area_value">
                    <a-input-number v-model:value="form.area_value" :precision="6" />
                    <a-input v-model:value="form.area_unit" class="unit-input" />
                    <a-button class="calc-button" @click="calculateArea">면적계산(F2)</a-button>
                  </FormLine>
                  <div></div>
                </div>

                <div class="two-col">
                  <FormLine label="과세구분" name="tax_type">
                    <a-select v-model:value="form.tax_type">
                      <a-select-option value="">선택</a-select-option>
                      <a-select-option value="tax">과세</a-select-option>
                      <a-select-option value="free">면세</a-select-option>
                    </a-select>
                  </FormLine>
                  <FormLine label="WEB주문품목적용" name="web_order_yn">
                    <a-select v-model:value="form.web_order_yn">
                      <a-select-option value="">선택</a-select-option>
                      <a-select-option value="Y">Y</a-select-option>
                      <a-select-option value="N">N</a-select-option>
                    </a-select>
                  </FormLine>
                </div>

              </div>
            </a-tab-pane>
          </a-tabs>
        </a-form>
      </div>
    </a-modal>

    <a-modal v-model:open="lookupOpen" title="품목군 조회" width="480px" :footer="null">
      <a-table
        :columns="lookupColumns"
        :data-source="lookupRows"
        :pagination="{ pageSize: 20, showSizeChanger: true }"
        row-key="code"
        size="small"
        :custom-row="record => ({ onDblclick: () => selectLookup(record) })"
      
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <a-button type="link" size="small" @click="selectLookup(record)">선택</a-button>
          </template>
        </template>
      </a-table>
    </a-modal>
  </div>
</template>

<script setup>
import { defineComponent, h, ref, reactive, computed, onMounted, resolveComponent } from 'vue'
import { message } from 'ant-design-vue'
import { masterApi } from '@/api'
import {
  AppstoreOutlined,
  BuildOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  InboxOutlined,
  PlusOutlined,
  SearchOutlined,
  ShoppingOutlined,
  UploadOutlined,
} from '@ant-design/icons-vue'

const FormLine = defineComponent({
  name: 'FormLine',
  props: {
    label: { type: String, default: '' },
    name: { type: String, required: true },
    required: { type: Boolean, default: false },
    wide: { type: Boolean, default: false },
  },
  setup(props, { slots }) {
    const AFormItem = resolveComponent('a-form-item')
    return () => h('div', { class: ['form-line', props.wide ? 'wide' : ''] }, [
      h('label', { class: 'field-label' }, props.label),
      h(
        AFormItem,
        {
          name: props.name,
          rules: props.required ? [{ required: true, message: `${props.label}을 입력하세요.` }] : [],
        },
        slots.default?.(),
      ),
    ])
  },
})

const items = ref([])
const statsData = ref({ total: 0, raw: 0, sub: 0, goods: 0 })
const loading = ref(false)
const saving = ref(false)
const importing = ref(false)
const editorOpen = ref(false)
const lookupOpen = ref(false)
const editItem = ref(null)
const activeTab = ref('master')
const filterType = ref(null)
const search = ref('')
const formRef = ref()
const excelInput = ref()
const pagination = reactive({ current: 1, pageSize: 20, total: 0 })
const lookupConfig = ref({ codeField: '', nameField: '' })

const emptyForm = {
  material_company_group_code: '',
  material_code: '',
  material_name: '',
  spec: '',
  unit: 'EA',
  management_unit: 'EA',
  conversion_factor: 1,
  material_type: '5',
  procurement_type: 'purchase',
  item_group_code: '',
  item_group_name: '',
  lot_use_yn: 'N',
  inspection_type: 'none',
  lot_quantity: 0,
  drawing_no: '',
  hs_code: '',
  width_value: 0,
  width_unit: '',
  height_value: 0,
  height_unit: '',
  depth_value: 0,
  depth_unit: '',
  weight_value: 0,
  weight_unit: '',
  area_value: 0,
  area_unit: '',
  set_item_yn: 'N',
  use_yn: 'Y',
  batch_quantity: 0,
  barcode: '',
  material_quality: '',
  length_value: 0,
  length_unit: '',
  density_value: 0,
  tax_type: '',
  web_order_yn: '',
  standard_price: 0,
  notes: '',
  order_notes: '',
}

const form = reactive({ ...emptyForm })

const materialTypeOptions = [
  { value: '0', label: '원재료' },
  { value: '1', label: '부재료' },
  { value: '2', label: '제품' },
  { value: '4', label: '반제품' },
  { value: '5', label: '상품' },
  { value: '6', label: '저장품' },
  { value: '7', label: '비용' },
  { value: '8', label: '수익' },
]
const typeColor = {
  0: 'blue',
  1: 'green',
  2: 'purple',
  4: 'cyan',
  5: 'orange',
  6: 'geekblue',
  7: 'red',
  8: 'gold',
  raw: 'blue',
  sub: 'green',
  goods: 'orange',
}
const typeLabel = Object.fromEntries(materialTypeOptions.map(option => [option.value, option.label]))
Object.assign(typeLabel, { raw: '원재료', sub: '부재료', goods: '상품' })
function isMaterialType(item, ...values) {
  return values.includes(String(item.material_type || ''))
}

const stats = computed(() => ({
  total: statsData.value.total,
  raw: statsData.value.raw,
  sub: statsData.value.sub,
  goods: statsData.value.goods,
}))

const tablePagination = computed(() => ({
  current: pagination.current,
  pageSize: pagination.pageSize,
  total: pagination.total,
  showSizeChanger: true,
  showTotal: total => `총 ${total.toLocaleString()}건`,
}))

const columns = [
  { title: '회사코드', dataIndex: 'material_company_group_code', width: 90, align: 'center' },
  { title: '품번', dataIndex: 'material_code', width: 220, align: 'center', ellipsis: true },
  { title: '품명', dataIndex: 'material_name', width: 260, align: 'center', ellipsis: true },
  { title: '규격', dataIndex: 'spec', width: 300, align: 'center', ellipsis: true },
  { title: '계정구분', key: 'material_type', dataIndex: 'material_type', width: 90, align: 'center' },
  { title: '조달구분', dataIndex: 'procurement_type', width: 90, align: 'center' },
  { title: '재고단위', dataIndex: 'unit', width: 90, align: 'center' },
  { title: '관리단위', dataIndex: 'management_unit', width: 90, align: 'center' },
  { title: '환산계수', key: 'conversion_factor', dataIndex: 'conversion_factor', width: 135, align: 'right' },
  { title: '사용여부', dataIndex: 'use_yn', width: 90, align: 'center' },
  { title: 'LOT여부', dataIndex: 'lot_use_yn', width: 84, align: 'center' },
  { title: 'SET여부', dataIndex: 'set_item_yn', width: 84, align: 'center' },
  { title: '검사여부', dataIndex: 'inspection_type', width: 90, align: 'center' },
  { title: '관리', key: 'action', width: 160, align: 'center', fixed: 'right' },
]

const lookupColumns = [
  { title: '코드', dataIndex: 'code', width: 130, align: 'center' },
  { title: '명칭', dataIndex: 'name', width: 240, align: 'center', ellipsis: true },
  { title: '선택', key: 'action', width: 80, align: 'center' },
]

const lookupRows = [
  { code: 'RAW', name: '원재료' },
  { code: 'SUB', name: '부재료' },
  { code: 'GOODS', name: '상품' },
  { code: 'SAUTER', name: 'SAUTER 품목' },
]

function formatPrice(value) {
  const number = Number(value || 0)
  return number.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 6 })
}

async function load() {
  loading.value = true
  try {
    const res = await masterApi.getMaterials({
      material_type: filterType.value || undefined,
      search: search.value || undefined,
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    items.value = res.data.items || res.data
    pagination.total = res.data.total ?? items.value.length
    statsData.value = res.data.stats || {
      total: items.value.length,
      raw: items.value.filter(m => isMaterialType(m, '0', 'raw')).length,
      sub: items.value.filter(m => isMaterialType(m, '1', 'sub')).length,
      goods: items.value.filter(m => isMaterialType(m, '5', 'goods')).length,
    }
  } finally {
    loading.value = false
  }
}

function resetAndLoad() {
  pagination.current = 1
  load()
}

function handleTableChange(nextPagination) {
  pagination.current = nextPagination.current || 1
  pagination.pageSize = nextPagination.pageSize || 20
  load()
}

function saveBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.URL.revokeObjectURL(url)
}

async function downloadTemplate() {
  const res = await masterApi.downloadMaterialsTemplate()
  saveBlob(res.data, '자재_관리_양식.xlsx')
}

async function handleExcelFile(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await masterApi.importMaterialsExcel(formData)
    const { imported = 0, updated = 0, skipped = 0 } = res.data || {}
    message.success(`엑셀 업로드 완료: 신규 ${imported}건, 수정 ${updated}건, 제외 ${skipped}건`)
    await load()
  } catch (e) {
    message.error(e.response?.data?.detail || '엑셀 업로드 중 오류가 발생했습니다.')
  } finally {
    importing.value = false
  }
}

async function openEditor(item) {
  editItem.value = item
  activeTab.value = 'master'
  let detail = item
  if (item?.id) {
    const res = await masterApi.getMaterial(item.id)
    detail = res.data
  }
  Object.assign(form, emptyForm, detail || {})
  editorOpen.value = true
}

function openLookup(_type, codeField, nameField) {
  lookupConfig.value = { codeField, nameField }
  lookupOpen.value = true
}

function selectLookup(record) {
  if (lookupConfig.value.codeField) form[lookupConfig.value.codeField] = record.code
  if (lookupConfig.value.nameField) form[lookupConfig.value.nameField] = record.name
  lookupOpen.value = false
}

function toNumber(value) {
  return Number(value || 0)
}

function round6(value) {
  return Math.round(value * 1000000) / 1000000
}

function setDefaultConversion() {
  form.conversion_factor = 1
  message.success('환산계수를 1로 설정했습니다.')
}

function calculateVolume() {
  const width = toNumber(form.width_value)
  const height = toNumber(form.height_value)
  const length = toNumber(form.length_value)
  if (!width || !height || !length) {
    message.warning('폭, 높이, 길이를 입력하세요.')
    return
  }
  form.depth_value = round6(width * height * length)
  message.success('부피를 계산했습니다.')
}

function calculateWeight() {
  const volume = toNumber(form.depth_value)
  const density = toNumber(form.density_value)
  if (!volume || !density) {
    message.warning('부피와 밀도를 입력하세요.')
    return
  }
  form.weight_value = round6(volume * density)
  message.success('중량을 계산했습니다.')
}

function calculateArea() {
  const width = toNumber(form.width_value)
  const length = toNumber(form.length_value)
  if (!width || !length) {
    message.warning('폭과 길이를 입력하세요.')
    return
  }
  form.area_value = round6(width * length)
  message.success('면적을 계산했습니다.')
}

function normalizePayload() {
  const payload = { ...form }
  ;[
    'conversion_factor',
    'lot_quantity',
    'width_value',
    'height_value',
    'depth_value',
    'weight_value',
    'area_value',
    'batch_quantity',
    'length_value',
    'density_value',
    'standard_price',
  ].forEach((key) => {
    if (payload[key] === '') payload[key] = null
  })
  return payload
}

async function handleSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    const payload = normalizePayload()
    if (editItem.value) {
      await masterApi.updateMaterial(editItem.value.id, payload)
      message.success('수정되었습니다.')
    } else {
      await masterApi.createMaterial(payload)
      message.success('등록되었습니다.')
    }
    editorOpen.value = false
    load()
  } catch (e) {
    if (e?.errorFields) return
    message.error(e.response?.data?.detail || '오류가 발생했습니다.')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id) {
  try {
    await masterApi.deleteMaterial(id)
    message.success('삭제되었습니다.')
    load()
  } catch (e) {
    message.error(e.response?.data?.detail || '삭제 중 오류가 발생했습니다.')
  }
}

onMounted(load)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.stat-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue { border-left-color: #1677ff; }
.stat-green { border-left-color: #52c41a; }
.stat-orange { border-left-color: #fa8c16; }
.stat-inner { display: flex; align-items: center; gap: 14px; }
.stat-icon { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.icon-gray { background: #f0f2f5; color: #595959; }
.icon-blue { background: #e6f4ff; color: #1677ff; }
.icon-green { background: #f6ffed; color: #52c41a; }
.icon-orange { background: #fff7e6; color: #fa8c16; }
.stat-label { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value { font-size: 24px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit { font-size: 13px; font-weight: 400; margin-left: 3px; color: #8c8c8c; }
.type-guide {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 10px;
  padding: 10px 12px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
  font-size: 12px;
}
.type-guide-title { font-weight: 700; color: #1a2535; margin-right: 2px; }
.type-guide-item { color: #595959; white-space: nowrap; }
.table-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size: 15px; font-weight: 600; color: #1a2535; }
.num-text { font-variant-numeric: tabular-nums; }
.del-link { color: #e74c3c; }
.del-link:hover { color: #c0392b; }
.legacy-editor {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 10px;
  height: 100%;
  min-height: 0;
  background: #f7fbff;
  overflow: hidden;
}
.legacy-list { border: 1px solid #b9d3ef; background: #fff; display: flex; flex-direction: column; min-width: 0; min-height: 0; }
.legacy-grid-head { display: grid; grid-template-columns: 34px 86px 1fr 80px; background: #2f76a7; color: #fff; font-weight: 700; font-size: 13px; height: 30px; line-height: 30px; text-align: center; }
.legacy-grid-head > div { border-right: 1px solid rgba(255,255,255,0.35); }
.legacy-grid-body { flex: 1; overflow: auto; background: #fff; }
.legacy-grid-row { display: grid; grid-template-columns: 34px 86px 1fr 80px; min-height: 28px; border-bottom: 1px solid #e6f0fb; cursor: pointer; font-size: 12px; }
.legacy-grid-row:hover { background: #eef6ff; }
.legacy-grid-row.selected { background: #e6f4ff; }
.legacy-grid-row > div { padding: 5px 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; border-right: 1px solid #eef2f7; }
.check-cell-body { display: flex; align-items: center; justify-content: center; padding: 0 !important; }
.legacy-grid-foot { height: 24px; border-top: 1px solid #f4c06d; background: linear-gradient(90deg, #fff0c4 0 80px, #f38b00 80px 170px, #fff0c4 170px); }
.legacy-form { min-width: 0; min-height: 0; overflow: hidden; }
.legacy-tabs { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.spec-box { border: 1px solid #8fbbe8; border-top: none; background: #eaf4fb; padding: 10px 16px 24px; min-height: 100%; }
.two-col { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px; }
.three-col { display: grid; grid-template-columns: 112px 112px minmax(170px, 1fr); gap: 10px; }
.form-line { display: grid; grid-template-columns: 70px minmax(0, 1fr); align-items: center; min-height: 25px; }
.field-label { text-align: right; padding-right: 8px; font-size: 13px; color: #111; white-space: nowrap; }
.code-input { max-width: 92px; }
.small-unit-input { max-width: 64px; }
.unit-input { max-width: 44px; }
.conversion-input { max-width: 96px; }
.icon-button { width: 24px; padding: 0; flex: 0 0 24px; color: #557ca5; }
.mini-button { height: 24px; padding: 0 5px; }
.calc-button { height: 24px; padding: 0 8px; }
:deep(.legacy-tabs > .ant-tabs-nav) { flex: 0 0 auto; margin: 0; }
:deep(.legacy-tabs .ant-tabs-tab) { min-width: 112px; justify-content: center; border-color: #8aa9cf !important; background: linear-gradient(#f7f7f7, #d7d7d7) !important; font-weight: 700; }
:deep(.legacy-tabs .ant-tabs-tab-active) { background: #eaf4fb !important; border-bottom-color: #eaf4fb !important; }
:deep(.legacy-tabs .ant-tabs-content-holder) { flex: 1 1 auto; min-height: 0; border-top: 1px solid #8fbbe8; overflow: hidden; background: #eaf4fb; }
:deep(.legacy-tabs .ant-tabs-content) { height: 100%; }
:deep(.legacy-tabs .ant-tabs-tabpane) { height: 100%; padding: 0 0 18px; overflow: auto; box-sizing: border-box; }
:deep(.material-editor-modal .ant-modal) { top: 24px; }
:deep(.material-editor-modal .ant-modal-body) {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}
:deep(.form-line .ant-form-item) { margin: 0; min-width: 0; }
:deep(.form-line .ant-form-item-control-input) { min-height: 24px; }
:deep(.form-line .ant-form-item-control-input-content) { display: flex; align-items: center; gap: 4px; min-width: 0; }
:deep(.form-line .ant-input),
:deep(.form-line .ant-select-selector),
:deep(.form-line .ant-input-number) { border-color: #8fb3dc !important; border-radius: 0 !important; height: 24px; background: #ffffd7; font-size: 12px; }
:deep(.form-line .ant-input-number-input) { height: 22px; font-size: 12px; text-align: right; }
:deep(.wide .ant-form-item-control-input-content > .ant-input) { max-width: 352px; }
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-table-thead > tr > th),
:deep(.ant-table-tbody > tr > td) { white-space: nowrap; }
:deep(.ant-table-tbody > tr > td) {
  height: 44px;
  padding-top: 8px;
  padding-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
}
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
