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
        :scroll="{ x: 1120 }"
        row-key="id"
        size="middle"
        :sticky="{ offsetHeader: 56 }"
      >
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
          <template v-else-if="column.key === 'attachments'">
            <a-tag v-if="record.attachments?.length" color="blue">{{ record.attachments.length }}개</a-tag>
            <span v-else>-</span>
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
      v-model:open="modalOpen"
      :mask-closable="false"
      :title="editingId ? '공지사항 수정' : '공지사항 등록'"
      width="680px"
      destroy-on-close
      :confirm-loading="saving"
      wrap-class-name="notice-center-modal"
      ok-text="저장"
      cancel-text="취소"
      @ok="saveNotice"
      @cancel="closeModal"
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
        <a-form-item label="첨부파일">
          <a-upload
            :file-list="pendingFiles"
            :before-upload="beforeUpload"
            :remove="removePendingFile"
            multiple
          >
            <a-button>
              <template #icon><UploadOutlined /></template>
              파일 선택
            </a-button>
          </a-upload>
        </a-form-item>
        <a-form-item v-if="editingId && currentAttachments.length" label="등록된 첨부파일">
          <a-list class="attachment-list" :data-source="currentAttachments" size="small">
            <template #renderItem="{ item }">
              <a-list-item>
                <a-button type="link" class="attachment-link" @click="openAttachment(item)">
                  {{ attachmentFileName(item) }}
                </a-button>
                <template #actions>
                  <a-button type="link" size="small" @click="downloadAttachment(item)">다운로드</a-button>
                  <a-popconfirm title="첨부파일을 삭제할까요?" @confirm="deleteAttachment(item.id)">
                    <a-button type="link" danger size="small">삭제</a-button>
                  </a-popconfirm>
                </template>
              </a-list-item>
            </template>
          </a-list>
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="pdfPreviewOpen"
      :title="pdfPreviewTitle"
      :width="pdfPreviewWidth"
      :body-style="{ padding: '12px' }"
      :footer="null"
      destroy-on-close
      @cancel="closePdfPreview"
    >
      <div class="pdf-preview-shell" :style="{ height: `${pdfPreviewHeight}px` }">
        <iframe v-if="pdfPreviewUrl" class="pdf-preview-frame" :src="pdfPreviewUrl" />
        <div class="pdf-preview-resizer" title="크기 조절" @pointerdown="startPdfResize" />
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { UploadOutlined } from '@ant-design/icons-vue'
import { masterApi } from '@/api'

const notices = ref([])
const loading = ref(false)
const saving = ref(false)
const modalOpen = ref(false)
const editingId = ref(null)
const keyword = ref('')
const pendingFiles = ref([])
const currentAttachments = ref([])
const pdfPreviewOpen = ref(false)
const pdfPreviewUrl = ref('')
const pdfPreviewTitle = ref('')
const pdfPreviewWidth = ref(900)
const pdfPreviewHeight = ref(620)
let stopPdfResize = null

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
  { title: '첨부', key: 'attachments', width: 90, align: 'center' },
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
  pendingFiles.value = []
  currentAttachments.value = []
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
  modalOpen.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.title = row.title || ''
  form.content = row.content || ''
  form.period = [row.start_date, row.end_date].filter(Boolean)
  form.is_active = !!row.is_active
  pendingFiles.value = []
  currentAttachments.value = [...(row.attachments || [])]
  modalOpen.value = true
}

function closeModal() {
  modalOpen.value = false
  resetForm()
}

function validateForm() {
  if (!form.title.trim()) return '제목을 입력하세요.'
  if (!form.period || form.period.length !== 2) return '게시 기간을 선택하세요.'
  if (!form.content.trim()) return '내용을 입력하세요.'
  return ''
}

function beforeUpload(file) {
  pendingFiles.value = [...pendingFiles.value, file]
  return false
}

function removePendingFile(file) {
  pendingFiles.value = pendingFiles.value.filter(item => item.uid !== file.uid)
  return true
}

async function uploadPendingFiles(noticeId) {
  for (const file of pendingFiles.value) {
    const formData = new FormData()
    formData.append('file', file.originFileObj || file)
    await masterApi.uploadNoticeAttachment(noticeId, formData)
  }
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
    const res = editingId.value
      ? await masterApi.updateNotice(editingId.value, payload)
      : await masterApi.createNotice(payload)
    const noticeId = res.data?.id || editingId.value
    if (noticeId && pendingFiles.value.length) {
      await uploadPendingFiles(noticeId)
    }
    message.success(editingId.value ? '공지사항을 수정했습니다.' : '공지사항을 등록했습니다.')
    modalOpen.value = false
    resetForm()
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

function attachmentFileName(attachment) {
  return attachment?.original_name || attachment?.filename || 'attachment'
}

function isPdfAttachment(attachment, blob) {
  const contentType = String(blob?.type || attachment?.content_type || '').toLowerCase()
  const fileName = attachmentFileName(attachment).toLowerCase()
  return contentType.includes('pdf') || fileName.endsWith('.pdf')
}

function downloadBlob(blob, fileName) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function revokePdfPreviewUrl() {
  if (pdfPreviewUrl.value) {
    URL.revokeObjectURL(pdfPreviewUrl.value)
    pdfPreviewUrl.value = ''
  }
}

function resetPdfPreviewSize() {
  pdfPreviewWidth.value = 900
  pdfPreviewHeight.value = 620
}

function closePdfPreview() {
  pdfPreviewOpen.value = false
  revokePdfPreviewUrl()
}

function stopPdfResizeTracking() {
  if (stopPdfResize) {
    stopPdfResize()
    stopPdfResize = null
  }
}

function startPdfResize(event) {
  event.preventDefault()
  stopPdfResizeTracking()
  const startX = event.clientX
  const startY = event.clientY
  const startWidth = pdfPreviewWidth.value
  const startHeight = pdfPreviewHeight.value
  const handleMove = (moveEvent) => {
    pdfPreviewWidth.value = Math.max(640, Math.min(1400, startWidth + moveEvent.clientX - startX))
    pdfPreviewHeight.value = Math.max(420, Math.min(900, startHeight + moveEvent.clientY - startY))
  }
  const handleUp = () => stopPdfResizeTracking()
  window.addEventListener('pointermove', handleMove)
  window.addEventListener('pointerup', handleUp, { once: true })
  stopPdfResize = () => {
    window.removeEventListener('pointermove', handleMove)
    window.removeEventListener('pointerup', handleUp)
  }
}

async function openAttachment(attachment) {
  try {
    const res = await masterApi.downloadNoticeAttachment(attachment.id)
    const blob = new Blob([res.data], {
      type: res.headers?.['content-type'] || attachment.content_type || 'application/octet-stream',
    })
    const fileName = attachmentFileName(attachment)
    if (isPdfAttachment(attachment, blob)) {
      revokePdfPreviewUrl()
      resetPdfPreviewSize()
      pdfPreviewUrl.value = URL.createObjectURL(blob)
      pdfPreviewTitle.value = fileName
      pdfPreviewOpen.value = true
      return
    }
    message.info('PDF 파일만 미리보기가 가능합니다. 다운로드 버튼을 사용하세요.')
  } catch (error) {
    message.error(error.response?.data?.detail || '첨부파일을 열 수 없습니다.')
  }
}

async function downloadAttachment(attachment) {
  try {
    const res = await masterApi.downloadNoticeAttachment(attachment.id)
    const blob = new Blob([res.data], {
      type: res.headers?.['content-type'] || attachment.content_type || 'application/octet-stream',
    })
    downloadBlob(blob, attachmentFileName(attachment))
  } catch (error) {
    message.error(error.response?.data?.detail || '첨부파일을 다운로드할 수 없습니다.')
  }
}

async function deleteAttachment(id) {
  try {
    await masterApi.deleteNoticeAttachment(id)
    currentAttachments.value = currentAttachments.value.filter(item => item.id !== id)
    notices.value = notices.value.map(row => (
      row.id === editingId.value
        ? { ...row, attachments: currentAttachments.value }
        : row
    ))
    message.success('첨부파일을 삭제했습니다.')
  } catch (error) {
    message.error(error.response?.data?.detail || '첨부파일 삭제에 실패했습니다.')
  }
}

onMounted(loadNotices)
onBeforeUnmount(() => {
  closePdfPreview()
  stopPdfResizeTracking()
})
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
.attachment-list { border: 1px solid #f0f0f0; border-radius: 8px; }
.attachment-link { height: auto; padding: 0; text-align: left; white-space: normal; }
.pdf-preview-shell { position: relative; width: 100%; min-width: 0; min-height: 420px; overflow: hidden; }
.pdf-preview-frame { width: 100%; height: 100%; border: 0; display: block; }
.pdf-preview-resizer {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 18px;
  height: 18px;
  cursor: nwse-resize;
  background: linear-gradient(135deg, transparent 45%, #bfbfbf 45%, #bfbfbf 55%, transparent 55%),
    linear-gradient(135deg, transparent 62%, #8c8c8c 62%, #8c8c8c 72%, transparent 72%);
}
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
