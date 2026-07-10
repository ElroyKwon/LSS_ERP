<template>
  <div class="page-wrap">
    <a-row :gutter="16">
      <a-col :span="8">
        <a-card :bordered="false" class="stat-card stat-blue">
          <div class="stat-inner">
            <MessageOutlined class="stat-icon icon-blue" />
            <div>
              <div class="stat-label">전체 의견</div>
              <div class="stat-value">{{ opinions.length }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card :bordered="false" class="stat-card stat-orange">
          <div class="stat-inner">
            <ClockCircleOutlined class="stat-icon icon-orange" />
            <div>
              <div class="stat-label">답변 대기</div>
              <div class="stat-value">{{ waitingCount }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card :bordered="false" class="stat-card stat-green">
          <div class="stat-inner">
            <CheckCircleOutlined class="stat-icon icon-green" />
            <div>
              <div class="stat-label">답변 완료</div>
              <div class="stat-value">{{ answeredCount }}<span class="stat-unit">건</span></div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-card :bordered="false" class="table-card">
      <template #title><span class="card-title">의견 청취</span></template>
      <template #extra>
        <a-space wrap>
          <a-select v-model:value="filters.status" allow-clear placeholder="상태" style="width:120px" @change="load">
            <a-select-option value="waiting">답변 대기</a-select-option>
            <a-select-option value="answered">답변 완료</a-select-option>
          </a-select>
          <a-input-search v-model:value="filters.search" allow-clear placeholder="제목/내용 검색" style="width:220px" @search="load" />
          <a-button type="primary" @click="openCreate">
            <template #icon><PlusOutlined /></template>
            등록
          </a-button>
        </a-space>
      </template>

      <a-table
        :columns="visibleColumns"
        :data-source="opinions"
        :loading="loading"
        :pagination="{ pageSize: 20, showSizeChanger: true }"
        :scroll="{ x: 1120 }"
        :sticky="{ offsetHeader: 56 }"
        row-key="id"
        size="middle"
        :custom-row="opinionRowEvents"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'title'">
            <a-button type="link" class="title-link" @click.stop="openDetail(record)">{{ record.title }}</a-button>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="record.status === 'answered' ? 'green' : 'orange'">
              {{ record.status === 'answered' ? '답변 완료' : '답변 대기' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'attachments'">
            <a-tag v-if="record.attachments?.length" color="blue">{{ record.attachments.length }}개</a-tag>
            <span v-else>-</span>
          </template>
          <template v-else-if="false">
            <a-space>
              <a-button size="small" @click.stop="openEdit(record)">
                <template #icon><EditOutlined /></template>
                수정
              </a-button>
              <a-popconfirm title="의견 글을 삭제하시겠습니까?" @confirm="removeOpinion(record.id)">
                <a-button size="small" danger @click.stop>
                  <template #icon><DeleteOutlined /></template>
                  삭제
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-modal
      v-model:open="editorOpen"
      :title="editingId ? '의견 수정' : '의견 등록'"
      width="760px"
      wrap-class-name="opinion-editor-modal"
      :confirm-loading="saving"
      ok-text="저장"
      cancel-text="취소"
      destroy-on-close
      @ok="saveOpinion"
      @cancel="resetEditor"
    >
      <a-form layout="vertical">
        <a-form-item label="제목" required>
          <a-input v-model:value="form.title" />
        </a-form-item>
        <a-form-item label="내용" required>
          <a-textarea v-model:value="form.content" :rows="8" />
        </a-form-item>
        <a-form-item label="첨부파일">
          <a-upload
            multiple
            :file-list="pendingFiles"
            :before-upload="beforeUpload"
            @remove="removePendingFile"
          >
            <a-button><template #icon><UploadOutlined /></template>파일 선택</a-button>
          </a-upload>
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="detailOpen"
      title="의견 상세"
      width="760"
      wrap-class-name="opinion-detail-modal"
      destroy-on-close
      centered>
      <template v-if="selected">
        <div class="detail-title">{{ selected.title }}</div>
        <div class="detail-meta">
          {{ selected.creator_name || '-' }} · {{ selected.created_at || '-' }}
          <a-tag :color="selected.status === 'answered' ? 'green' : 'orange'">
            {{ selected.status === 'answered' ? '답변 완료' : '답변 대기' }}
          </a-tag>
        </div>
        <a-divider />
        <div class="detail-content">{{ selected.content }}</div>

        <a-divider orientation="left">첨부파일</a-divider>
        <a-empty v-if="!selected.attachments?.length" description="첨부파일 없음" />
        <a-list v-else class="attachment-list" :data-source="selected.attachments" size="small">
          <template #renderItem="{ item }">
            <a-list-item>
              <a-button type="link" class="attachment-link" @click="openAttachment(item)">
                {{ item.original_name }}
              </a-button>
              <template #actions>
                <a-button type="link" size="small" @click="downloadAttachment(item)">다운로드</a-button>
                <a-popconfirm title="첨부파일을 삭제하시겠습니까?" @confirm="deleteAttachment(item.id)">
                  <a-button type="link" danger size="small">삭제</a-button>
                </a-popconfirm>
              </template>
            </a-list-item>
          </template>
        </a-list>

        <a-divider orientation="left">답변</a-divider>
        <div v-if="selected.answer" class="answer-box">
          <div class="detail-meta">{{ selected.answerer_name || '-' }} · {{ selected.answered_at || '-' }}</div>
          <div class="detail-content">{{ selected.answer }}</div>
        </div>
        <a-empty v-else description="답변 없음" />

        <template v-if="auth.isAdmin">
          <a-divider orientation="left">관리자 답변</a-divider>
          <a-textarea v-model:value="answerText" :rows="6" />
          <div class="drawer-footer">
            <a-button type="primary" :loading="answerSaving" @click="saveAnswer">답변 저장</a-button>
          </div>
        </template>
      </template>
      <template #footer>
        <div class="detail-footer">
          <a-space>
            <a-button @click="detailOpen = false">닫기</a-button>
            <a-button v-if="selected" @click="openEditFromDetail">
              <template #icon><EditOutlined /></template>
              수정
            </a-button>
            <a-popconfirm
              v-if="selected"
              title="의견 글을 삭제하시겠습니까?"
              ok-text="삭제"
              ok-type="danger"
              cancel-text="취소"
              @confirm="removeSelectedOpinion"
            >
              <a-button danger>
                <template #icon><DeleteOutlined /></template>
                삭제
              </a-button>
            </a-popconfirm>
            <a-button
              v-if="auth.isAdmin && selected"
              type="primary"
              :loading="answerSaving"
              @click="saveAnswer"
            >
              답변 저장
            </a-button>
          </a-space>
        </div>
      </template>
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
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  MessageOutlined,
  PlusOutlined,
  UploadOutlined,
} from '@ant-design/icons-vue'
import { opinionApi } from '@/api'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const opinions = ref([])
const loading = ref(false)
const saving = ref(false)
const answerSaving = ref(false)
const editorOpen = ref(false)
const detailOpen = ref(false)
const editingId = ref(null)
const selected = ref(null)
const pendingFiles = ref([])
const answerText = ref('')
const pdfPreviewOpen = ref(false)
const pdfPreviewUrl = ref('')
const pdfPreviewTitle = ref('')
const pdfPreviewWidth = ref(1100)
const pdfPreviewHeight = ref(720)
const filters = reactive({ search: '', status: undefined })
const form = reactive({ title: '', content: '' })
let stopPdfResize = null

const columns = [
  { title: '상태', key: 'status', width: 110, align: 'center' },
  { title: '제목', key: 'title', dataIndex: 'title', width: 360, align: 'center', ellipsis: true },
  { title: '등록자', dataIndex: 'creator_name', width: 130, align: 'center' },
  { title: '등록일', dataIndex: 'created_at', width: 160, align: 'center' },
  { title: '첨부', key: 'attachments', width: 90, align: 'center' },
  { title: '답변자', dataIndex: 'answerer_name', width: 130, align: 'center' },
  { title: '답변일', dataIndex: 'answered_at', width: 160, align: 'center' },
  { title: '관리', key: 'action', width: 160, align: 'center', fixed: 'right' },
]

const visibleColumns = computed(() => columns.filter(column => column.key !== 'action'))
const waitingCount = computed(() => opinions.value.filter(row => row.status !== 'answered').length)
const answeredCount = computed(() => opinions.value.filter(row => row.status === 'answered').length)

async function load() {
  loading.value = true
  try {
    const res = await opinionApi.getOpinions({
      search: filters.search || undefined,
      status: filters.status || undefined,
    })
    opinions.value = res.data || []
  } catch (error) {
    message.error(error.response?.data?.detail || '의견 목록을 불러오지 못했습니다.')
  } finally {
    loading.value = false
  }
}

function resetEditor() {
  editingId.value = null
  form.title = ''
  form.content = ''
  pendingFiles.value = []
}

function openCreate() {
  resetEditor()
  editorOpen.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.title = row.title || ''
  form.content = row.content || ''
  pendingFiles.value = []
  editorOpen.value = true
}

function openEditFromDetail() {
  if (!selected.value) return
  openEdit(selected.value)
  detailOpen.value = false
}

async function openDetail(row) {
  try {
    const res = await opinionApi.getOpinion(row.id)
    selected.value = res.data
    answerText.value = res.data.answer || ''
    detailOpen.value = true
  } catch (error) {
    message.error(error.response?.data?.detail || '의견 상세를 불러오지 못했습니다.')
  }
}

function opinionRowEvents(record) {
  return {
    onClick: () => openDetail(record),
    onDblclick: () => openDetail(record),
  }
}

function beforeUpload(file) {
  pendingFiles.value = [...pendingFiles.value, file]
  return false
}

function removePendingFile(file) {
  pendingFiles.value = pendingFiles.value.filter(item => item.uid !== file.uid)
}

async function uploadPendingFiles(opinionId) {
  for (const file of pendingFiles.value) {
    const formData = new FormData()
    formData.append('file', file)
    await opinionApi.uploadAttachment(opinionId, formData)
  }
}

async function saveOpinion() {
  if (!form.title.trim()) {
    message.warning('제목을 입력하세요.')
    return
  }
  if (!form.content.trim()) {
    message.warning('내용을 입력하세요.')
    return
  }
  saving.value = true
  try {
    const payload = { title: form.title.trim(), content: form.content.trim() }
    const res = editingId.value
      ? await opinionApi.updateOpinion(editingId.value, payload)
      : await opinionApi.createOpinion(payload)
    await uploadPendingFiles(res.data.id)
    message.success(editingId.value ? '의견이 수정되었습니다.' : '의견이 등록되었습니다.')
    editorOpen.value = false
    resetEditor()
    await load()
  } catch (error) {
    message.error(error.response?.data?.detail || '의견 저장에 실패했습니다.')
  } finally {
    saving.value = false
  }
}

async function removeOpinion(id) {
  try {
    await opinionApi.deleteOpinion(id)
    message.success('의견이 삭제되었습니다.')
    if (selected.value?.id === id) {
      selected.value = null
      detailOpen.value = false
    }
    await load()
  } catch (error) {
    message.error(error.response?.data?.detail || '의견 삭제에 실패했습니다.')
  }
}

async function removeSelectedOpinion() {
  if (!selected.value) return
  await removeOpinion(selected.value.id)
}

async function saveAnswer() {
  if (!selected.value) return
  if (!answerText.value.trim()) {
    message.warning('답변을 입력하세요.')
    return
  }
  answerSaving.value = true
  try {
    const res = await opinionApi.answerOpinion(selected.value.id, { answer: answerText.value.trim() })
    selected.value = res.data
    answerText.value = res.data.answer || ''
    message.success('답변이 저장되었습니다.')
    await load()
  } catch (error) {
    message.error(error.response?.data?.detail || '답변 저장에 실패했습니다.')
  } finally {
    answerSaving.value = false
  }
}

async function deleteAttachment(id) {
  try {
    await opinionApi.deleteAttachment(id)
    message.success('첨부파일이 삭제되었습니다.')
    if (selected.value) await openDetail(selected.value)
    await load()
  } catch (error) {
    message.error(error.response?.data?.detail || '첨부파일 삭제에 실패했습니다.')
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

function revokePdfPreviewUrl() {
  if (pdfPreviewUrl.value) {
    URL.revokeObjectURL(pdfPreviewUrl.value)
    pdfPreviewUrl.value = ''
  }
}

function closePdfPreview() {
  stopPdfResizeTracking()
  revokePdfPreviewUrl()
  pdfPreviewOpen.value = false
  pdfPreviewTitle.value = ''
}

function clampSize(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

function resetPdfPreviewSize() {
  const viewportWidth = window.innerWidth || 1280
  const viewportHeight = window.innerHeight || 900
  pdfPreviewWidth.value = clampSize(Math.floor(viewportWidth * 0.8), 720, Math.floor(viewportWidth * 0.96))
  pdfPreviewHeight.value = clampSize(Math.floor(viewportHeight * 0.74), 480, Math.floor(viewportHeight * 0.86))
}

function stopPdfResizeTracking() {
  if (stopPdfResize) {
    stopPdfResize()
    stopPdfResize = null
  }
}

function startPdfResize(event) {
  event.preventDefault()
  event.stopPropagation()
  stopPdfResizeTracking()

  const startX = event.clientX
  const startY = event.clientY
  const startWidth = pdfPreviewWidth.value
  const startHeight = pdfPreviewHeight.value

  const handleMove = (moveEvent) => {
    const maxWidth = Math.floor((window.innerWidth || 1280) * 0.96)
    const maxHeight = Math.floor((window.innerHeight || 900) * 0.86)
    pdfPreviewWidth.value = clampSize(startWidth + moveEvent.clientX - startX, 640, maxWidth)
    pdfPreviewHeight.value = clampSize(startHeight + moveEvent.clientY - startY, 420, maxHeight)
  }

  const handleUp = () => stopPdfResizeTracking()
  window.addEventListener('pointermove', handleMove)
  window.addEventListener('pointerup', handleUp, { once: true })
  stopPdfResize = () => {
    window.removeEventListener('pointermove', handleMove)
    window.removeEventListener('pointerup', handleUp)
  }
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

async function openAttachment(attachment) {
  try {
    const res = await opinionApi.downloadAttachment(attachment.id)
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
    const res = await opinionApi.downloadAttachment(attachment.id)
    const blob = new Blob([res.data], {
      type: res.headers?.['content-type'] || attachment.content_type || 'application/octet-stream',
    })
    downloadBlob(blob, attachmentFileName(attachment))
  } catch (error) {
    message.error(error.response?.data?.detail || '첨부파일을 다운로드할 수 없습니다.')
  }
}

onMounted(load)
onBeforeUnmount(() => {
  closePdfPreview()
  stopPdfResizeTracking()
})
</script>

<style scoped>
.page-wrap { display: flex; flex-direction: column; gap: 16px; }
.stat-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue { border-left-color: #1677ff; }
.stat-orange { border-left-color: #fa8c16; }
.stat-green { border-left-color: #52c41a; }
.stat-inner { display: flex; align-items: center; gap: 14px; }
.stat-icon { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; }
.icon-blue { background: #e6f4ff; color: #1677ff; }
.icon-orange { background: #fff7e6; color: #fa8c16; }
.icon-green { background: #f6ffed; color: #52c41a; }
.stat-label { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value { font-size: 24px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit { font-size: 13px; font-weight: 400; margin-left: 3px; color: #8c8c8c; }
.table-card { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title { font-size: 15px; font-weight: 600; color: #1a2535; }
.title-link { padding: 0; height: auto; max-width: 330px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.table-card :deep(.ant-table-row) { cursor: pointer; }
.detail-title { font-size: 20px; font-weight: 700; color: #1a2535; margin-bottom: 8px; }
.detail-meta { display: flex; align-items: center; gap: 8px; color: #8c8c8c; font-size: 12px; }
.detail-content { white-space: pre-wrap; line-height: 1.7; color: #1a2535; }
.answer-box { padding: 12px; background: #fafafa; border: 1px solid #f0f0f0; border-radius: 8px; }
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
.drawer-footer { display: none; }
.detail-footer { display: flex; justify-content: flex-end; }
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
</style>
