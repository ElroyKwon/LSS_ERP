<template>
  <div class="page-wrap">
    <a-row :gutter="16">
      <a-col :span="6">
        <a-card :bordered="false" class="stat-card stat-blue">
          <div class="stat-inner">
            <div class="stat-icon icon-blue"><ApartmentOutlined /></div>
            <div>
              <div class="stat-label">전체 부서</div>
              <div class="stat-value">{{ items.length }}<span class="stat-unit">개</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card :bordered="false" class="stat-card stat-green">
          <div class="stat-inner">
            <div class="stat-icon icon-green"><CheckCircleOutlined /></div>
            <div>
              <div class="stat-label">활성</div>
              <div class="stat-value">{{ activeCount }}<span class="stat-unit">개</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card :bordered="false" class="stat-card stat-orange">
          <div class="stat-inner">
            <div class="stat-icon icon-orange"><BranchesOutlined /></div>
            <div>
              <div class="stat-label">최상위 조직</div>
              <div class="stat-value">{{ rootCount }}<span class="stat-unit">개</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-card :bordered="false" class="table-card">
      <template #title>
        <span class="card-title">부서 관리</span>
      </template>
      <template #extra>
        <a-space>
          <a-input-number v-model:value="yearFilter" :min="2000" :max="2100" style="width: 110px" @change="load" />
          <a-input-search v-model:value="search" placeholder="부서명/코드 검색" allow-clear style="width: 220px" />
          <a-switch v-model:checked="includeInactive" checked-children="전체" un-checked-children="활성" @change="load" />
          <a-button type="primary" @click="openDrawer(null, null)">
            <template #icon><PlusOutlined /></template>
            최상위 추가
          </a-button>
        </a-space>
      </template>

      <a-row :gutter="16">
        <a-col :span="10">
          <div class="tree-panel">
            <a-tree
              v-model:selectedKeys="selectedKeys"
              :tree-data="treeData"
              :loading="loading"
              block-node
              default-expand-all
              @select="onSelect"
            />
          </div>
        </a-col>
        <a-col :span="14">
          <div v-if="selectedDept" class="detail-panel">
            <div class="detail-head">
              <div>
                <div class="detail-title">{{ selectedDept.name }}</div>
                <div class="detail-sub">{{ selectedDept.code }} · {{ typeLabel[selectedDept.dept_type] || selectedDept.dept_type }}</div>
              </div>
              <a-tag :color="selectedDept.is_active ? 'green' : 'red'">
                {{ selectedDept.is_active ? '활성' : '비활성' }}
              </a-tag>
            </div>

            <a-descriptions bordered size="small" :column="2">
              <a-descriptions-item label="적용연도">{{ selectedDept.org_year || '-' }}</a-descriptions-item>
              <a-descriptions-item label="정렬순서">{{ selectedDept.sort_order }}</a-descriptions-item>
              <a-descriptions-item label="상위부서" :span="2">{{ parentName(selectedDept.parent_id) }}</a-descriptions-item>
              <a-descriptions-item label="비고" :span="2">{{ selectedDept.notes || '-' }}</a-descriptions-item>
            </a-descriptions>

            <div class="detail-actions">
              <a-button type="primary" @click="openDrawer(selectedDept, null)">수정</a-button>
              <a-button @click="openDrawer(null, selectedDept)">하위 추가</a-button>
              <a-popconfirm
                title="해당 부서와 하위 부서를 비활성화하시겠습니까?"
                ok-text="비활성화"
                cancel-text="취소"
                @confirm="deleteDepartment(selectedDept)"
              >
                <a-button danger>비활성화</a-button>
              </a-popconfirm>
            </div>
          </div>
          <a-empty v-else description="좌측 조직도에서 부서를 선택하세요" />
        </a-col>
      </a-row>
    </a-card>

    <a-drawer
      v-model:open="drawerOpen"
      :title="editItem ? '부서 수정' : '부서 추가'"
      width="520"
      :body-style="{ paddingBottom: '72px' }"
    >
      <a-form ref="formRef" :model="form" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="적용연도" name="org_year" :rules="[{ required: true, message: '적용연도를 입력하세요' }]">
              <a-input-number v-model:value="form.org_year" :min="2000" :max="2100" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="조직구분" name="dept_type">
              <a-select v-model:value="form.dept_type">
                <a-select-option value="office">실</a-select-option>
                <a-select-option value="division">부문</a-select-option>
                <a-select-option value="business">사업부</a-select-option>
                <a-select-option value="team">팀</a-select-option>
                <a-select-option value="part">Part</a-select-option>
                <a-select-option value="common">공통</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="상위부서" name="parent_id">
              <a-tree-select
                v-model:value="form.parent_id"
                :tree-data="parentTreeData"
                allow-clear
                tree-default-expand-all
                placeholder="최상위 조직이면 비워두세요"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="부서코드" name="code">
              <a-input v-model:value="form.code" placeholder="미입력 시 자동 생성" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="정렬순서" name="sort_order">
              <a-input-number v-model:value="form.sort_order" :min="0" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="부서명" name="name" :rules="[{ required: true, message: '부서명을 입력하세요' }]">
              <a-input v-model:value="form.name" />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="비고" name="notes">
              <a-textarea v-model:value="form.notes" :rows="3" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="활성 여부" name="is_active">
              <a-switch v-model:checked="form.is_active" checked-children="활성" un-checked-children="비활성" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>

      <template #footer>
        <div class="drawer-footer">
          <a-button @click="drawerOpen = false">취소</a-button>
          <a-button type="primary" :loading="saving" @click="saveDepartment">저장</a-button>
        </div>
      </template>
    </a-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApartmentOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
  PlusOutlined,
} from '@ant-design/icons-vue'
import { masterApi } from '@/api'

const nowYear = new Date().getFullYear()
const items = ref([])
const loading = ref(false)
const saving = ref(false)
const drawerOpen = ref(false)
const editItem = ref(null)
const formRef = ref()
const search = ref('')
const selectedKeys = ref([])
const yearFilter = ref(nowYear)
const includeInactive = ref(true)

const emptyForm = {
  code: '',
  name: '',
  parent_id: null,
  org_year: nowYear,
  dept_type: 'team',
  sort_order: 0,
  is_active: true,
  notes: '',
}
const form = reactive({ ...emptyForm })

const typeLabel = {
  office: '실',
  division: '부문',
  business: '사업부',
  team: '팀',
  part: 'Part',
  common: '공통',
}

const activeCount = computed(() => items.value.filter(item => item.is_active).length)
const rootCount = computed(() => items.value.filter(item => !item.parent_id).length)
const selectedDept = computed(() => items.value.find(item => String(item.id) === String(selectedKeys.value[0])))

const filteredItems = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return items.value
  return items.value.filter(item =>
    item.name.toLowerCase().includes(q) ||
    String(item.code || '').toLowerCase().includes(q)
  )
})

const treeData = computed(() => buildTree(filteredItems.value))
const parentTreeData = computed(() => buildTree(items.value.filter(item => !editItem.value || item.id !== editItem.value.id)))

function buildTree(rows) {
  const sorted = [...rows].sort((a, b) =>
    (a.parent_id || 0) - (b.parent_id || 0) ||
    (a.sort_order || 0) - (b.sort_order || 0) ||
    a.name.localeCompare(b.name)
  )
  const nodes = sorted.map(item => ({
    title: `${item.name}${item.is_active ? '' : ' (비활성)'}`,
    label: item.name,
    value: item.id,
    key: String(item.id),
    disabled: item.is_active === false && !includeInactive.value,
    children: [],
  }))
  const byId = new Map(nodes.map(node => [node.value, node]))
  const roots = []
  sorted.forEach(item => {
    const node = byId.get(item.id)
    const parent = byId.get(item.parent_id)
    if (parent) parent.children.push(node)
    else roots.push(node)
  })
  return roots
}

function parentName(parentId) {
  if (!parentId) return '최상위'
  return items.value.find(item => item.id === parentId)?.name || '-'
}

function onSelect(keys) {
  selectedKeys.value = keys
}

async function load() {
  loading.value = true
  try {
    const res = await masterApi.getDepartments({
      org_year: yearFilter.value,
      include_inactive: includeInactive.value,
    })
    items.value = res.data
    if (selectedKeys.value[0] && !items.value.some(item => String(item.id) === String(selectedKeys.value[0]))) {
      selectedKeys.value = []
    }
  } finally {
    loading.value = false
  }
}

function openDrawer(item, parent) {
  editItem.value = item
  Object.assign(form, item ? { ...emptyForm, ...item } : {
    ...emptyForm,
    parent_id: parent?.id || null,
    org_year: parent?.org_year || yearFilter.value || nowYear,
    sort_order: nextSortOrder(parent?.id || null),
  })
  drawerOpen.value = true
}

function nextSortOrder(parentId) {
  const siblings = items.value.filter(item => (item.parent_id || null) === (parentId || null))
  return siblings.reduce((max, item) => Math.max(max, Number(item.sort_order) || 0), 0) + 1
}

async function saveDepartment() {
  try {
    await formRef.value.validate()
    saving.value = true
    const payload = { ...form, code: form.code || null }
    if (editItem.value) {
      await masterApi.updateDepartment(editItem.value.id, payload)
      message.success('부서 정보가 수정되었습니다.')
    } else {
      await masterApi.createDepartment(payload)
      message.success('부서가 추가되었습니다.')
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

async function deleteDepartment(record) {
  try {
    await masterApi.deleteDepartment(record.id)
    message.success('부서가 비활성화되었습니다.')
    selectedKeys.value = []
    await load()
  } catch (e) {
    message.error(e.response?.data?.detail || '비활성화 중 오류가 발생했습니다.')
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
.icon-blue { background: #e6f4ff; color: #1677ff; }
.icon-green { background: #f6ffed; color: #52c41a; }
.icon-orange { background: #fff7e6; color: #fa8c16; }
.stat-label { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value { font-size: 24px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit { font-size: 13px; font-weight: 400; margin-left: 3px; color: #8c8c8c; }
.table-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size: 15px; font-weight: 600; color: #1a2535; }
.tree-panel { min-height: 460px; padding: 12px; border: 1px solid #f0f0f0; border-radius: 8px; background: #fff; }
.detail-panel { min-height: 460px; padding: 18px; border: 1px solid #f0f0f0; border-radius: 8px; background: #fff; }
.detail-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px; }
.detail-title { font-size: 20px; font-weight: 700; color: #1a2535; }
.detail-sub { margin-top: 4px; color: #8c8c8c; font-size: 13px; }
.detail-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
.drawer-footer { display: flex; justify-content: flex-end; gap: 8px; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
