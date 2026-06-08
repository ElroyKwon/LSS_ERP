// ── 날짜/시간 (KST = UTC+9) ──────────────────────────────
/**
 * 백엔드 UTC datetime 문자열 → KST "YYYY-MM-DD HH:mm" 표시
 * 날짜만 있는 문자열(YYYY-MM-DD)은 그대로 반환
 */
export function formatKST(val) {
  if (!val) return '-'
  const s = String(val)
  // 날짜만 있는 경우 그대로 반환
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s
  // 이미 KST로 변환된 경우(백엔드 to_kst 사용)
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(s)) return s
  // ISO 문자열이면 UTC→KST 변환
  const d = new Date(s)
  if (isNaN(d.getTime())) return s
  const kst = new Date(d.getTime() + 9 * 60 * 60 * 1000)
  return kst.toISOString().slice(0, 16).replace('T', ' ')
}

/** 오늘 날짜를 KST 기준 "YYYY-MM-DD" 로 반환 */
export function todayKST() {
  return formatKST(new Date().toISOString()).slice(0, 10)
}

export const currency = (v) =>
  v == null ? '-' : Number(v).toLocaleString('ko-KR') + '원'

export const number = (v) =>
  v == null ? '-' : Number(v).toLocaleString('ko-KR')

export const percent = (v) =>
  v == null ? '-' : Number(v).toFixed(1) + '%'

export const statusLabel = (status, map) => map[status] || status

export const CONTRACT_TYPE = { lump_sum: '총액', unit_price: '단가', actual_cost: '실비' }
export const SITE_STATUS = { active: '진행중', completed: '완료', suspended: '중단' }
export const BILLING_STATUS = { draft: '작성중', submitted: '제출', approved: '승인', invoiced: '세금계산서발행' }
export const ORDER_STATUS = { draft: '작성중', confirmed: '확정', partial: '부분입고', completed: '완료', cancelled: '취소' }
export const COMPANY_TYPE = { client: '발주처', vendor: '협력사', both: '발주처/협력사' }
export const EMP_TYPE = { regular: '정규직', daily: '일용직', contract: '계약직' }
