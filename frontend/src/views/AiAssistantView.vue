<template>
  <div class="assistant-page">
    <div class="assistant-sidebar">
      <div class="assistant-brand">
        <div class="assistant-mark">AI</div>
        <div>
          <div class="assistant-title">AI 업무비서</div>
          <div class="assistant-subtitle">MCP 기반 ERP 조회 도우미</div>
        </div>
      </div>

      <a-divider style="margin: 14px 0" />

      <div class="side-section-title">업무 바로가기</div>
      <button
        v-for="preset in presets"
        :key="preset.key"
        class="preset-btn"
        @click="sendPreset(preset.prompt)"
      >
        <component :is="preset.icon" />
        <span>{{ preset.label }}</span>
      </button>

      <a-divider style="margin: 14px 0" />

      <div class="side-section-title">연결된 MCP Tools</div>
      <div class="tool-list">
        <div v-for="tool in tools" :key="tool.name" class="tool-item">
          <div class="tool-name">{{ tool.title || tool.name }}</div>
          <div class="tool-desc">{{ tool.description }}</div>
        </div>
      </div>
    </div>

    <div class="assistant-main">
      <div class="chat-header">
        <div>
          <div class="chat-heading">ERP 운영 업무비서</div>
          <div class="chat-copy">
            타임시트, 프로젝트, 의견 청취 데이터를 현재 로그인 권한 기준으로 조회합니다.
          </div>
        </div>
        <a-space>
          <a-tag color="blue">조회 전용</a-tag>
          <a-button @click="resetChat">새 대화</a-button>
        </a-space>
      </div>

      <div class="chat-body" ref="chatBodyRef">
        <div class="welcome-card" v-if="messages.length === 1">
          <div class="welcome-title">무엇을 확인할까요?</div>
          <div class="welcome-grid">
            <button v-for="preset in presets" :key="preset.key" @click="sendPreset(preset.prompt)">
              <strong>{{ preset.label }}</strong>
              <span>{{ preset.prompt }}</span>
            </button>
          </div>
        </div>

        <div v-for="message in messages" :key="message.id" :class="['message-row', message.role]">
          <div class="message-bubble">
            <div class="message-text">{{ message.content }}</div>

            <div v-if="message.cards?.length" class="result-grid">
              <div v-for="card in message.cards" :key="card.title" class="result-card">
                <div class="result-card-head">
                  <span>{{ card.title }}</span>
                  <strong>{{ card.metric }}</strong>
                </div>
                <div class="result-card-desc">{{ card.description }}</div>
                <div v-if="card.items?.length" class="result-items">
                  <div v-for="(item, index) in card.items" :key="index" class="result-item">
                    {{ itemTitle(item) }}
                    <span>{{ itemSub(item) }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="message.suggestions?.length" class="suggestion-row">
              <button v-for="suggestion in message.suggestions" :key="suggestion" @click="sendPreset(suggestion)">
                {{ suggestion }}
              </button>
            </div>
          </div>
        </div>

        <div v-if="loading" class="message-row assistant">
          <div class="message-bubble loading-bubble">
            <a-spin size="small" />
            <span>ERP 데이터를 조회하고 있습니다.</span>
          </div>
        </div>
      </div>

      <div class="chat-composer">
        <a-input
          v-model:value="draft"
          size="large"
          placeholder="예: 이번 주 미제출 타임시트 직원 알려줘"
          @pressEnter="sendMessage"
        />
        <a-button type="primary" size="large" :loading="loading" @click="sendMessage">
          <template #icon><SendOutlined /></template>
          전송
        </a-button>
      </div>
    </div>

    <div class="assistant-context">
      <div class="context-card">
        <div class="context-title">동작 방식</div>
        <ol>
          <li>사용자 질문을 채팅 API로 전송</li>
          <li>백엔드가 MCP tool을 선택</li>
          <li>기존 ERP DB/API를 권한 기준으로 조회</li>
          <li>결과를 카드와 답변으로 반환</li>
        </ol>
      </div>
      <div class="context-card">
        <div class="context-title">쓰기 작업 정책</div>
        <p>현재 1차 구현은 조회 전용입니다. 등록, 수정, 승인, 알림 발송은 추후 승인형 액션 UI로 분리해 추가합니다.</p>
      </div>
      <div class="context-card">
        <div class="context-title">현재 컨텍스트</div>
        <div class="context-row"><span>사용자</span><strong>{{ auth.user?.name || '-' }}</strong></div>
        <div class="context-row"><span>권한</span><strong>{{ auth.user?.role || '-' }}</strong></div>
        <div class="context-row"><span>화면</span><strong>/ai-assistant</strong></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'
import {
  BarChartOutlined,
  ClockCircleOutlined,
  FolderOpenOutlined,
  MessageOutlined,
  SendOutlined,
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { aiApi } from '@/api'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const chatBodyRef = ref(null)
const draft = ref('')
const loading = ref(false)
const tools = ref([])
let messageSeq = 1

const presets = [
  { key: 'summary', label: '운영 요약', prompt: '이번 주 ERP 운영 요약해줘', icon: BarChartOutlined },
  { key: 'timesheet', label: '타임시트 미제출', prompt: '이번 주 미제출 타임시트 직원 알려줘', icon: ClockCircleOutlined },
  { key: 'opinion', label: '의견 답변 대기', prompt: '답변 대기 의견 청취 목록 보여줘', icon: MessageOutlined },
  { key: 'project', label: '프로젝트 검색', prompt: '최근 프로젝트 현황 검색해줘', icon: FolderOpenOutlined },
]

const messages = ref([
  {
    id: messageSeq++,
    role: 'assistant',
    content: 'AI 업무비서입니다. 현재는 조회 전용 MCP tool로 ERP 데이터를 확인할 수 있습니다.',
  },
])

function resetChat() {
  messageSeq = 1
  messages.value = [{
    id: messageSeq++,
    role: 'assistant',
    content: '새 대화를 시작합니다. 확인할 ERP 업무를 입력하세요.',
  }]
}

function scrollToBottom() {
  nextTick(() => {
    if (chatBodyRef.value) chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
  })
}

function itemTitle(item) {
  return item.employee_name || item.title || item.project_name || item.project_no || '항목'
}

function formatAmount(value) {
  return Number(value || 0).toLocaleString()
}

function itemSub(item) {
  if (item.employee_name || item.total_hours !== undefined) return `${item.status || '-'} · ${item.total_hours || 0}h`
  if (item.project_name || item.project_no) {
    return `${item.status || '-'} · ${item.client_name || '-'} · PM ${item.pm_name || '-'} · ${formatAmount(item.contract_amount)}`
  }
  if (item.creator_name) {
    const status = item.status === 'answered' ? '답변 완료' : '답변 대기'
    return `${status} · ${item.creator_name} · 첨부 ${item.attachment_count || 0}개`
  }
  return ''
}

async function sendPreset(prompt) {
  draft.value = prompt
  await sendMessage()
}

async function sendMessage() {
  const text = draft.value.trim()
  if (!text || loading.value) return
  draft.value = ''
  messages.value.push({ id: messageSeq++, role: 'user', content: text })
  loading.value = true
  scrollToBottom()

  try {
    const res = await aiApi.chat({
      message: text,
      context: {
        route: '/ai-assistant',
        menu: 'AI 업무비서',
        filters: {},
      },
      history: messages.value.map(row => ({ role: row.role === 'user' ? 'user' : 'assistant', content: row.content })),
    })
    messages.value.push({
      id: messageSeq++,
      role: 'assistant',
      content: res.data.answer,
      cards: res.data.cards || [],
      suggestions: res.data.suggestions || [],
    })
  } catch (error) {
    message.error(error.response?.data?.detail || 'AI 업무비서 응답을 가져오지 못했습니다.')
    messages.value.push({
      id: messageSeq++,
      role: 'assistant',
      content: '요청 처리 중 오류가 발생했습니다. 잠시 후 다시 시도하세요.',
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

async function loadTools() {
  try {
    const res = await aiApi.getTools()
    tools.value = res.data.tools || []
  } catch {
    tools.value = []
  }
}

onMounted(loadTools)
</script>

<style scoped>
.assistant-page {
  height: calc(100vh - 96px);
  min-height: 720px;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr) 300px;
  gap: 16px;
}
.assistant-sidebar,
.assistant-main,
.assistant-context {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07);
  min-height: 0;
}
.assistant-sidebar { padding: 16px; overflow: auto; }
.assistant-brand { display: flex; align-items: center; gap: 12px; }
.assistant-mark {
  width: 38px; height: 38px; border-radius: 8px; display: flex; align-items: center; justify-content: center;
  background: #e6f4ff; color: #1677ff; font-weight: 800;
}
.assistant-title { font-size: 16px; font-weight: 700; color: #1a2535; }
.assistant-subtitle { font-size: 12px; color: #8c8c8c; margin-top: 2px; }
.side-section-title { font-size: 12px; font-weight: 700; color: #595959; margin-bottom: 8px; }
.preset-btn {
  width: 100%; height: 38px; border: 1px solid #eef1f5; border-radius: 7px; background: #fff;
  display: flex; align-items: center; gap: 8px; padding: 0 10px; margin-bottom: 8px; color: #1a2535;
}
.preset-btn:hover { border-color: #1677ff; color: #1677ff; background: #f5f9ff; }
.tool-list { display: flex; flex-direction: column; gap: 8px; }
.tool-item { border: 1px solid #eef1f5; border-radius: 7px; padding: 9px; }
.tool-name { font-size: 12px; font-weight: 700; color: #1a2535; }
.tool-desc { font-size: 11px; color: #8c8c8c; line-height: 1.45; margin-top: 4px; }

.assistant-main { display: flex; flex-direction: column; overflow: hidden; }
.chat-header {
  height: 70px; flex-shrink: 0; border-bottom: 1px solid #f0f0f0; display: flex;
  align-items: center; justify-content: space-between; padding: 0 18px;
}
.chat-heading { font-size: 16px; font-weight: 700; color: #1a2535; }
.chat-copy { font-size: 12px; color: #8c8c8c; margin-top: 3px; }
.chat-body {
  flex: 1; overflow: auto; padding: 18px; background: #f5f7fb; display: flex; flex-direction: column; gap: 14px;
}
.welcome-card { background: #fff; border: 1px solid #e6edf7; border-radius: 8px; padding: 16px; }
.welcome-title { font-size: 15px; font-weight: 700; margin-bottom: 12px; color: #1a2535; }
.welcome-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.welcome-grid button {
  border: 1px solid #eef1f5; border-radius: 7px; background: #fff; padding: 12px; text-align: left;
}
.welcome-grid strong { display: block; color: #1a2535; margin-bottom: 5px; }
.welcome-grid span { font-size: 12px; color: #8c8c8c; }
.message-row { display: flex; }
.message-row.user { justify-content: flex-end; }
.message-row.assistant { justify-content: flex-start; }
.message-bubble {
  max-width: 82%; border-radius: 8px; padding: 12px; background: #fff; border: 1px solid #e8edf5;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.message-row.user .message-bubble { background: #1677ff; color: #fff; border-color: #1677ff; }
.message-text { white-space: pre-wrap; line-height: 1.6; font-size: 13px; }
.loading-bubble { display: inline-flex; align-items: center; gap: 8px; color: #595959; }
.result-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; margin-top: 10px; }
.result-card { border: 1px solid #eef1f5; border-radius: 8px; background: #fff; overflow: hidden; color: #1a2535; }
.result-card-head { display: flex; align-items: center; justify-content: space-between; padding: 10px; border-bottom: 1px solid #f0f0f0; }
.result-card-head span { font-size: 12px; font-weight: 700; }
.result-card-head strong { color: #1677ff; }
.result-card-desc { padding: 8px 10px; font-size: 12px; color: #8c8c8c; }
.result-items { border-top: 1px solid #f5f5f5; max-height: 360px; overflow-y: auto; }
.result-item { padding: 7px 10px; font-size: 12px; border-bottom: 1px solid #f7f7f7; }
.result-item span { display: block; color: #8c8c8c; margin-top: 2px; }
.suggestion-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.suggestion-row button {
  border: 1px solid #d9e7ff; background: #f5f9ff; color: #0958d9; border-radius: 999px;
  height: 28px; padding: 0 10px; font-size: 12px;
}
.chat-composer {
  flex-shrink: 0; border-top: 1px solid #f0f0f0; padding: 12px; display: grid; grid-template-columns: minmax(0, 1fr) 96px; gap: 8px;
}

.assistant-context { padding: 16px; overflow: auto; }
.context-card { border: 1px solid #eef1f5; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
.context-title { font-size: 13px; font-weight: 700; color: #1a2535; margin-bottom: 8px; }
.context-card ol { margin: 0; padding-left: 18px; color: #595959; font-size: 12px; line-height: 1.8; }
.context-card p { margin: 0; color: #595959; font-size: 12px; line-height: 1.6; }
.context-row { display: flex; align-items: center; justify-content: space-between; font-size: 12px; margin-top: 7px; }
.context-row span { color: #8c8c8c; }
.context-row strong { color: #1a2535; }

@media (max-width: 1280px) {
  .assistant-page { grid-template-columns: 230px minmax(0, 1fr); }
  .assistant-context { display: none; }
}
</style>
