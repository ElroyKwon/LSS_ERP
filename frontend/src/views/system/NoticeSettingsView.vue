<template>
  <div class="page-wrap">
    <a-row :gutter="16">
      <a-col :span="8">
        <a-card :bordered="false" class="stat-card stat-blue">
          <div class="stat-inner">
            <div>
              <div class="stat-label">전체 공지</div>
              <div class="stat-value">{{ notices.length }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card :bordered="false" class="stat-card stat-green">
          <div class="stat-inner">
            <div>
              <div class="stat-label">게시 중</div>
              <div class="stat-value">{{ activeCount }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card :bordered="false" class="stat-card stat-orange">
          <div class="stat-inner">
            <div>
              <div class="stat-label">게시 예정</div>
              <div class="stat-value">{{ upcomingCount }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-card :bordered="false" class="table-card">
      <template #title>
        <span class="card-title">공지사항</span>
      </template>
      <template #extra>
        <a-space>
          <a-input-search v-model:value="keyword" placeholder="제목 검색" allow-clear style="width: 220px" />
          <a-button type="primary" @click="openCreate">신규 등록</a-button>
        </a-space>
      </template>

      <a-table
        :columns="columns"
        :data-source="filteredNotices"
        :loading="loading"
        :pagination="{ pageSize: 10 }"
        :scroll="{ x: 980 }"
        row-key="id"
        size="middle"
      
        :sticky="{ offsetHeader: 56 }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'period'">
            {{ record.start_date }} ~ {{ record.end_date }}
          </template>
          <template v-else-if="column.key === 'is_active'">
            <a-tag :color="getStatusColor(record)">{{ getStatusText(record) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'content'">
            <span class="ellipsis-text">{{ record.content }}</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button size="small" @click="openEdit(record)">수정</a-button>
              <a-popconfirm title="공지사항을 삭제할까요?" @confirm="removeNotice(record.id)">
                <a-button size="small" danger>삭제</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-modal
      v-model:open="drawerOpen"
      :title="editingId ? '공지사항 수정' : '공지사항 등록'"
      width="620px"
      destroy-on-close
      :confirm-loading="saving"
      wrap-class-name="notice-center-modal"
      ok-text="저장"
      cancel-text="취소"
      @ok="saveNotice"
    >
      <a-form layout="vertical">
        <a-form-item label="제목" required>
          <a-input v-model:value="form.title" placeholder="공지 제목" />
        </a-form-item>
        <a-form-item label="게시 기간" required>
          <a-range-picker
            v-model:value="form.period"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item label="게시 여부">
          <a-switch v-model:checked="form.is_active" checked-children="게시" un-checked-children="중지" />
        </a-form-item>
        <a-form-item label="내용" required>
          <a-textarea v-model:value="form.content" :rows="10" placeholder="공지 내용을 입력하세요." />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { masterApi } from '@/api'

const notices = ref([])
const loading = ref(false)
const saving = ref(false)
const drawerOpen = ref(false)
const editingId = ref(null)
const keyword = ref('')

const form = reactive({
  title: '',
  content: '',
  period: [],
  is_active: true,
})

const columns = [
  { title: '제목', dataIndex: 'title', width: 220, align: 'center', ellipsis: true },
  { title: '내용', key: 'content', dataIndex: 'content', width: 260, align: 'center', ellipsis: true },
  { title: '게시 기간', key: 'period', width: 220, align: 'center' },
  { title: '상태', key: 'is_active', width: 90, align: 'center' },
  { title: '등록자', dataIndex: 'creator_name', width: 120, align: 'center' },
  { title: '관리', key: 'action', width: 150, align: 'center', fixed: 'right' },
]

const todayKey = computed(() => {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
})

const activeCount = computed(() => notices.value.filter((row) => getStatusText(row) === '게시 중').length)
const upcomingCount = computed(() => notices.value.filter((row) => getStatusText(row) === '게시 예정').length)
const filteredNotices = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return notices.value
  return notices.value.filter((row) => (row.title || '').toLowerCase().includes(q))
})

function resetForm() {
  editingId.value = null
  form.title = ''
  form.content = ''
  form.period = []
  form.is_active = true
}

function getStatusText(row) {
  if (!row.is_active) return '중지'
  if (row.start_date > todayKey.value) return '게시 예정'
  if (row.end_date < todayKey.value) return '기간 종료'
  return '게시 중'
}

function getStatusColor(row) {
  const status = getStatusText(row)
  if (status === '게시 중') return 'green'
  if (status === '게시 예정') return 'blue'
  if (status === '중지') return 'red'
  return 'default'
}

async function loadNotices() {
  loading.value = true
  try {
    const res = await masterApi.getNotices()
    notices.value = res.data || []
  } catch (err) {
    message.error(err.response?.data?.detail || '공지사항을 불러오지 못했습니다.')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  resetForm()
  drawerOpen.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.title = row.title || ''
  form.content = row.content || ''
  form.period = [row.start_date, row.end_date].filter(Boolean)
  form.is_active = !!row.is_active
  drawerOpen.value = true
}

function validateForm() {
  if (!form.title.trim()) return '제목을 입력하세요.'
  if (!form.period || form.period.length !== 2) return '게시 기간을 선택하세요.'
  if (!form.content.trim()) return '내용을 입력하세요.'
  return ''
}

async function saveNotice() {
  const error = validateForm()
  if (error) {
    message.warning(error)
    return
  }
  const payload = {
    title: form.title.trim(),
    content: form.content.trim(),
    start_date: form.period[0],
    end_date: form.period[1],
    is_active: form.is_active,
  }
  saving.value = true
  try {
    if (editingId.value) {
      await masterApi.updateNotice(editingId.value, payload)
      message.success('공지사항을 수정했습니다.')
    } else {
      await masterApi.createNotice(payload)
      message.success('공지사항을 등록했습니다.')
    }
    drawerOpen.value = false
    await loadNotices()
  } catch (err) {
    message.error(err.response?.data?.detail || '공지사항 저장에 실패했습니다.')
  } finally {
    saving.value = false
  }
}

async function removeNotice(id) {
  try {
    await masterApi.deleteNotice(id)
    message.success('공지사항을 삭제했습니다.')
    await loadNotices()
  } catch (err) {
    message.error(err.response?.data?.detail || '공지사항 삭제에 실패했습니다.')
  }
}

onMounted(loadNotices)
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.stat-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue { border-left-color: #1677ff; }
.stat-green { border-left-color: #52c41a; }
.stat-orange { border-left-color: #fa8c16; }
.stat-inner { display: flex; align-items: center; gap: 14px; }
.stat-label { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value { font-size: 24px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit { font-size: 13px; font-weight: 400; margin-left: 3px; color: #8c8c8c; }
.table-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size: 15px; font-weight: 600; color: #1a2535; }
.ellipsis-text { display: inline-block; max-width: 230px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: middle; }
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
