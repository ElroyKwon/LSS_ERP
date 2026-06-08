import { message } from 'ant-design-vue'

// API 에러에서 사용자 친화적 메시지 추출
export function getErrorMsg(e, fallback = '오류가 발생했습니다.') {
  if (e?.response?.data?.detail) return e.response.data.detail
  if (e?.response?.data?.message) return e.response.data.message
  if (e?.message) return e.message
  return fallback
}

// API 에러 토스트 표시
export function showError(e, fallback) {
  message.error(getErrorMsg(e, fallback))
}
