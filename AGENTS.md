# LSS ERP 개발 가이드라인

## 기술 스택
- **Frontend**: Vue 3 (Composition API) + Ant Design Vue + Vite
- **Backend**: FastAPI + SQLAlchemy + SQLite
- **상태관리**: Pinia (`useAuthStore`)
- **라우터**: Vue Router (`frontend/src/router/index.js`)
- **API**: `frontend/src/api/index.js` (axios)

---

## 테이블 UI 표준 ★ 필수 준수

### 1. 컬럼 정의 규칙

> **모든 컬럼에 반드시 명시적 `width` 를 지정한다.**  
> width 없는 컬럼이 하나라도 있으면 해당 컬럼이 나머지 공간을 전부 차지해 레이아웃이 깨진다.

```js
const columns = [
  // ✅ 모든 컬럼에 width + align 명시
  { title: '코드',   dataIndex: 'code',    width: 130, align: 'center' },
  { title: '이름',   dataIndex: 'name',    width: 200, align: 'center', ellipsis: true },
  { title: '날짜',   dataIndex: 'date',    width: 110, align: 'center' },
  { title: '금액',   key: 'amount',        width: 140, align: 'right' },
  { title: '상태',   key: 'status',        width: 90,  align: 'center' },
  { title: '관리',   key: 'action',        width: 110, align: 'center', fixed: 'right' },

  // ❌ 금지 — width 없는 컬럼
  // { title: '이름', dataIndex: 'name', ellipsis: true },
]
```

### 2. 데이터 유형별 align 규칙

| 유형 | align | 권장 width |
|------|-------|-----------|
| 코드 / 번호 | `center` | 130~150 |
| 날짜 (YYYY-MM-DD) | `center` | 110 |
| 날짜시간 (YYYY-MM-DD HH:mm) | `center` | 150~160 |
| 짧은 텍스트 (상태, 유형, 구분) | `center` | 80~110 |
| 이름 / 제목 / 내용 (말줄임) | `center` + `ellipsis: true` | 180~220 |
| 금액 / 수량 / 숫자 | `right` | 130~150 |
| 비율 (%) | `center` | 90~110 |
| 관리 버튼 | `center` + `fixed: 'right'` | 90~130 |

### Amount display format

- Amount values must use accounting-style comma grouping without a leading currency symbol: `000,000,000`.
- Do not prefix amount values with `₩`, `KRW`, or other currency marks unless the user explicitly asks.
- For inputs, use the same comma formatter/parser pattern so typed amounts display consistently.

### 3. 헤더 가운데 정렬 CSS

CrudTable 을 사용하는 뷰는 자동 적용됨.  
`a-table` 을 직접 사용하는 뷰는 `<style scoped>` 에 반드시 추가:

```css
:deep(.ant-table-thead > tr > th) { text-align: center !important; background: #fafafa; }
:deep(.ant-card-head) { border-bottom: 1px solid #f0f0f0; min-height: 52px; }
```

### 4. scroll 설정

컬럼 width 합산이 화면보다 클 경우 반드시 `:scroll` 설정:

```html
<a-table :scroll="{ x: 900 }" ... />
```

---

## 날짜 / 시간 표준 ★ 필수 준수

### 기본 원칙
- DB 저장: **UTC** (SQLAlchemy 기본값 유지)
- 화면 표시: **KST (UTC+9)** — 한국 표준시
- 날짜만 있는 필드 (`Date` 타입): 시간대 변환 불필요

### 백엔드 — KST 변환 유틸리티

```python
# backend/app/utils/__init__.py 에 정의됨
from ..utils import to_kst, to_kst_date

# DateTime 컬럼 → "YYYY-MM-DD HH:mm" (KST)
"created_at": to_kst(record.created_at)

# Date 컬럼 → "YYYY-MM-DD"
"request_date": to_kst_date(record.request_date)
```

커스텀 응답 dict를 만드는 경우 반드시 위 함수 사용.  
FastAPI가 ORM 객체를 직접 반환하는 경우 → 프론트엔드에서 `formatKST()` 로 처리.

### 프론트엔드 — KST 표시 유틸리티

```js
// frontend/src/utils/format.js 에 정의됨
import { formatKST, todayKST } from '@/utils/format'

// 테이블 셀에서 datetime 표시
formatKST(record.created_at)   // "2026-05-19 14:30"
formatKST(record.request_date) // "2026-05-19" (날짜만이면 그대로)

// 오늘 날짜 KST 기준
todayKST()  // "2026-05-19"
```

### DatePicker 사용 시

```html
<!-- 날짜 입력 (Date 타입) -->
<a-date-picker value-format="YYYY-MM-DD" />

<!-- 날짜+시간 입력 (DateTime 타입) -->
<a-date-picker show-time value-format="YYYY-MM-DD HH:mm:ss" />
```

### 테이블 컬럼에서 datetime 표시 예시

```html
<template #bodyCell="{ column, record }">
  <template v-if="column.key === 'created_at'">
    {{ formatKST(record.created_at) }}
  </template>
</template>
```

---

## 화면 레이아웃 표준

### 목록 페이지 구성
```
1. 상단 통계 카드 행 (a-row :gutter="16")
2. 테이블 카드 (a-card :bordered="false" class="table-card")
   - #title 슬롯: 페이지명
   - #extra 슬롯: 필터 + 신규 등록 버튼
   - a-table (size="middle", :scroll="{ x: N }")
```

### 통계 카드 패턴

```html
<a-card :bordered="false" class="stat-card stat-blue">
  <div class="stat-inner">
    <div class="stat-icon icon-blue"><SomeOutlined /></div>
    <div>
      <div class="stat-label">레이블</div>
      <div class="stat-value" style="color:#1677ff">N<span class="stat-unit">건</span></div>
    </div>
  </div>
</a-card>
```

공통 stat CSS (각 뷰의 `<style scoped>`에 포함):
```css
.page-wrap   { display: flex; flex-direction: column; gap: 16px; }
.stat-card   { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-left: 4px solid #e0e0e0; }
.stat-blue   { border-left-color: #1677ff; }
.stat-green  { border-left-color: #52c41a; }
.stat-orange { border-left-color: #fa8c16; }
.stat-purple { border-left-color: #722ed1; }
.stat-red    { border-left-color: #f5222d; }
.stat-inner  { display: flex; align-items: center; gap: 14px; }
.stat-icon   { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.icon-blue   { background: #e6f4ff; color: #1677ff; }
.icon-green  { background: #f6ffed; color: #52c41a; }
.icon-orange { background: #fff7e6; color: #fa8c16; }
.icon-purple { background: #f9f0ff; color: #722ed1; }
.icon-gray   { background: #f0f2f5; color: #595959; }
.icon-red    { background: #fff1f0; color: #f5222d; }
.stat-label  { font-size: 12px; color: #8c8c8c; margin-bottom: 2px; }
.stat-value  { font-size: 24px; font-weight: 700; color: #1a2535; line-height: 1.2; }
.stat-unit   { font-size: 13px; font-weight: 400; margin-left: 3px; color: #8c8c8c; }
.table-card  { border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
.card-title  { font-size: 15px; font-weight: 600; color: #1a2535; }
```

### 등록/수정 폼 선택 기준
- 필드 **6개 이하** → `a-modal` (width: 440~560px)
- 필드 **7개 이상** → `a-drawer` (width: 480~560px, footer 슬롯에 저장/취소 버튼)
- 관련 필드는 `a-divider`로 섹션 구분
- 삭제는 항상 `a-popconfirm` 사용

---

## 메뉴 구조 (`AppLayout.vue`)

```
기초           → /master/*
영업           → /sales/*
실행           → /execution/*
경영           → /management/*
타임시트       → /timesheet
손익계산서     → /profit-loss
시스템(관리자) → /system/*
```

---

## API 패턴

새 엔드포인트 추가 시:
1. `backend/app/models/` 에 모델 추가
2. `backend/app/models/__init__.py` 에 import 및 `__all__` 등록
3. 해당 `backend/app/routers/*.py` 에 엔드포인트 추가
4. `frontend/src/api/index.js` 에 함수 추가

라우터 prefix: `router = APIRouter(prefix="/api", tags=[...])`

### 응답 직렬화 시 날짜 처리

```python
from ..utils import to_kst, to_kst_date

def _my_dict(obj):
    return {
        "id":         obj.id,
        "name":       obj.name,
        "date_field": to_kst_date(obj.date_field),   # Date 타입
        "created_at": to_kst(obj.created_at),         # DateTime 타입
    }
```

---

## 상태 태그 색상 규칙

| 상태 | Ant Design color |
|------|-----------------|
| 대기 / 접수 / 작성중 | `orange` |
| 진행중 / 제출 | `blue` |
| 완료 / 승인 / 활성 | `green` |
| 거절 / 취소 / 비활성 | `red` |
| 기타 / 복합 | `purple` |
---

## Codex ??? ?? ?? ??

? ???? Claude? ??? ??? ?? ???? Codex?? ??? ????. Codex? ? `AGENTS.md`? ??? ???? ???? ????, `CLAUDE.md`? Claude ??? ?? ???? ????.

### ?? ??
- ???? ?? ??, ??, ?? ??, API ??? ???? ???? ??? ?? ?? ???? ????.
- ?? ?? ??? ??, ?? ??? ???? ????.
- ? ??? `frontend/src/views`, API ??? `frontend/src/api/index.js`, ??? ??/???? `backend/app/models`, `backend/app/routers`? ????.
- ???? ???? `backend/app/main.py`? include ??? ????.
- ?? SQLAlchemy ??? ???? `backend/app/models/__init__.py`? import ? `__all__` ?? ??? ????.

### ?? ??
- ????? ?? ??? ???? ?? ?? ?? ??? ??? ????.
- ??? ??/??? ?? ??? ??? ?? ??? ?? API ??? ????.
- ??? ???? ?? ??, ?? ??? ??? ??? ??? ???.

### UI ?? ??
- ??? ??? ?? ??? `width`? `align`? ????.
- ? ??? ??? `width + ellipsis: true`? ?? ????.
- ??/??/??/?? ??? ??? ??, ??/??? ??? ????.
- ??/?? ??? 7? ???? `a-drawer`, 6? ??? `a-modal`? ???? ??.
- ??? ?? ?? ?? + ?? + ??? ?? ??? ?? ????.

### ??/?? ??
- DB ??? UTC ??? ????.
- ?? ??? ?? ???? KST(Asia/Seoul) ???? ????.
- ??? dict ??? `backend/app/utils/__init__.py`? `to_kst`, `to_kst_date`? ????.
- ?????? `frontend/src/utils/format.js`? `formatKST`, `todayKST`? ????.

### Claude ??
- `CLAUDE.md`? Claude?? ?? ???? ??? ?? ?? ?? ???.
- Codex ?? ? ? ??? ??? ?? `AGENTS.md`? ????, ?? ? `CLAUDE.md`?? ?? ??? ?????.

