# LSS ERP PC Responsive UI Guide

이 문서는 LSS ERP의 PC 반응형 화면 규칙을 정리한 기준 문서입니다. 신규 메뉴 개발 또는 기존 메뉴 수정 시 이 규칙을 우선 적용합니다.

## 적용 범위

PC 반응형 기준 해상도는 아래 구간을 기본으로 합니다.

| 구간 | 기준 |
| --- | --- |
| 일반 PC | `1920x1080` |
| 사내 표준 노트북 | `1600x900`, `1440x900` |
| 최소 PC 기준 | `1366x768` |

모바일/태블릿 전용 UX는 별도 작업 범위입니다. 이 문서는 PC 화면에서 메뉴가 깨지지 않고 사용할 수 있도록 하는 기준입니다.

## 기본 레이아웃 규칙

- 페이지 최상위 래퍼는 가능한 `page-wrap`을 사용합니다.
- 주요 목록/그리드는 `table-card` 또는 `grid-card` 안에 배치합니다.
- 콘텐츠 영역은 화면 너비를 넘기지 않도록 `min-width: 0`, `max-width: 100%` 흐름을 유지합니다.
- 페이지 전체에 불필요한 가로 스크롤이 생기면 안 됩니다.
- 큰 테이블만 카드 내부에서 가로 스크롤을 허용합니다.

권장 구조:

```vue
<template>
  <div class="page-wrap">
    <a-card :bordered="false" class="table-card">
      ...
    </a-card>
  </div>
</template>
```

## 카드/필터/툴바 규칙

- 카드 상단 버튼, 검색, 필터는 한 줄에 고정하지 않습니다.
- 해상도가 좁아질 때 줄바꿈이 가능해야 합니다.
- 공통 클래스는 `title-row`, `filter-row`, `toolbar-row`, `action-row` 중 문맥에 맞게 사용합니다.
- 검색창, 셀렉트, 날짜 선택은 `max-width: 100%` 안에서 동작해야 합니다.

금지:

```vue
<a-space style="width: 1200px">
```

권장:

```vue
<a-space class="toolbar-row" wrap>
```

## Ant Table 규칙

### 기본 규칙

- Ant Table은 반드시 `scroll.x`를 지정합니다.
- 많은 컬럼을 억지로 화면 안에 압축하지 않습니다.
- 텍스트/금액/입력 필드가 겹치면 컬럼 폭을 늘리고 가로 스크롤을 허용합니다.
- 테이블 셀은 기본적으로 줄바꿈하지 않습니다.
- 금액 컬럼은 `1,000,000,000` 수준까지 한 줄로 보이도록 폭을 잡습니다.

권장:

```vue
<a-table
  :columns="columns"
  :data-source="rows"
  :scroll="{ x: 1200 }"
  :pagination="clientPagination"
  :sticky="{ offsetHeader: 56 }"
/>
```

### Sticky Header

- Ant Table의 헤더 고정은 Ant Table의 `sticky` prop으로 처리합니다.
- 앱 상단 헤더 높이는 `56px`이므로 `offsetHeader: 56`을 사용합니다.
- 카드 내부에서 짧은 테이블이거나 첫 행이 가려지는 경우에는 sticky를 제거합니다.
- 직접 CSS로 `.ant-table-thead`에 `position: sticky`를 지정하지 않습니다.

권장:

```vue
:sticky="{ offsetHeader: 56 }"
```

금지:

```css
.ant-table-thead {
  position: sticky;
}
```

### 입력형 테이블

- 테이블 안의 `a-input`, `a-input-number`, `a-select`, `a-date-picker`는 셀 폭 안에서 `width: 100%`로 맞춥니다.
- 입력창의 실제 폭이 헤더/셀 폭보다 커져 겹치면 안 됩니다.
- 월별 금액 입력처럼 동일 입력칸이 반복되는 테이블은 컬럼 폭과 입력창 폭을 같이 관리합니다.

## 일반 HTML Table 규칙

타임시트처럼 직접 `<table>`을 사용하는 화면은 Ant Table 규칙과 다릅니다.

- 직접 만든 table은 wrapper에 `overflow: auto`를 둡니다.
- sticky 처리는 `thead`가 아니라 `th`에 적용합니다.
- `thead` 자체를 sticky 처리하면 브라우저별로 헤더 행 위치가 틀어지거나 첫 행을 덮을 수 있습니다.

권장:

```css
.custom-table-wrap {
  overflow: auto;
}

.custom-table thead th {
  position: sticky;
  top: 0;
  z-index: 8;
  background: #fafafa;
}
```

금지:

```css
.custom-table thead {
  position: sticky;
}
```

## 컬럼 폭 규칙

- 관리/삭제/수정 컬럼은 필요한 버튼이 잘리지 않을 만큼 최소 폭을 확보합니다.
- 프로젝트명, 거래처명, 품명처럼 긴 텍스트는 `ellipsis` 또는 tooltip을 적용합니다.
- 금액/수량/월별 값은 우측 정렬을 기본으로 합니다.
- 사용자가 자주 비교하는 핵심 컬럼은 필요 시 리사이즈 기능을 제공합니다.

권장 컬럼 폭 기준:

| 컬럼 유형 | 권장 폭 |
| --- | --- |
| 상태/구분 | `80~120px` |
| 날짜 | `110~140px` |
| 이름/담당자 | `110~140px` |
| 프로젝트명/거래처명 | `220px` 이상 |
| 금액 | `130px` 이상 |
| 월별 금액 | `110px` 이상 |
| 관리 버튼 | `120px` 이상 |

## 페이지네이션 규칙

- 목록성 테이블은 페이지네이션을 기본 적용합니다.
- `showSizeChanger`가 있는 경우 페이지당 개수 변경이 실제 데이터 표시 개수에 반영되어야 합니다.
- 서버 페이지네이션 화면은 `current`, `pageSize`, `total`을 API 요청과 동기화합니다.
- 클라이언트 페이지네이션 화면은 공통 `clientPagination` 또는 동일한 옵션 구조를 사용합니다.

권장 옵션:

```js
{
  defaultPageSize: 20,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100']
}
```

## 모달/팝업 규칙

### 기본 규칙

- 사이드 드로어 대신 중앙 모달을 기본으로 사용합니다.
- 모달은 화면을 꽉 채우지 않습니다.
- PC 기준 모달 최대 폭은 `calc(100vw - 48px)` 안에 들어와야 합니다.
- 모달 본문은 스크롤 가능해야 하고, 하단 버튼은 항상 보여야 합니다.
- 등록/수정 모달은 `mask-closable="false"`를 기본으로 합니다.

### 모달 크기 기준

| 유형 | 기본 폭 |
| --- | --- |
| 단순 등록/수정 | `440~580px` |
| 일반 업무 등록 | `720~840px` |
| 프로젝트/견적/청구 | `840~960px` |
| 설계의뢰 등 넓은 양식 | `1120px` |
| 거래처/자재처럼 ERP 원장형 | 화면 높이 기준 스크롤 모달 |

공통 CSS는 `frontend/src/assets/main.css`에서 관리합니다.

신규 모달이 별도 폭이 필요하면 `wrap-class-name`을 지정하고 `main.css`에 추가합니다.

```vue
<a-modal
  v-model:open="modalOpen"
  wrap-class-name="sample-editor-modal"
  :mask-closable="false"
>
```

```css
.ant-modal-root .sample-editor-modal .ant-modal {
  width: min(840px, calc(100vw - 48px)) !important;
  max-width: calc(100vw - 48px);
}
```

### 닫기 동작

- 우측 상단 `X`는 닫기입니다.
- 빈 폼은 바로 닫혀야 합니다.
- 사용자가 입력한 내용이 있을 때만 작성 취소 확인 팝업을 표시합니다.
- 공지 팝업, 상세 조회 팝업, 파일 미리보기 팝업은 작성 취소 확인 대상에서 제외합니다.

### 상세 조회 뷰어

- 목록 테이블의 등록된 행을 클릭하면 상세 조회가 가능해야 합니다.
- 상세 조회는 등록/수정 입력 폼을 그대로 재사용하지 않습니다.
- 상세 조회는 읽기 전용 문서 뷰어 형태를 기본으로 합니다.
- 사용자가 내용을 자연스럽게 훑어볼 수 있도록 섹션, 라벨, 값 구조를 명확히 분리합니다.
- 수정/삭제 권한이 있는 화면은 상세 뷰어 하단에 `수정`, `삭제`, `닫기` 버튼을 배치합니다.
- `수정`을 누를 때만 등록/수정 입력 폼으로 전환합니다.
- 단순 조회 팝업은 작성 취소 확인 팝업 대상이 아닙니다.

권장 흐름:

```text
테이블 행 클릭 -> 상세 뷰어 열기 -> 수정 버튼 -> 수정 폼 열기
```

## 해상도별 규칙

### `1440px` 이하

- 카드 padding을 줄입니다.
- 테이블 셀 padding을 줄입니다.
- 모달 본문 최대 높이를 줄여 하단 버튼이 보이게 합니다.

### `1366px` 이하

- 카드 라운드/여백을 줄여 정보 밀도를 높입니다.
- 모달은 `calc(100vw - 24px)` 범위 안으로 제한합니다.
- 테이블은 컬럼을 무리하게 줄이지 말고 가로 스크롤을 유지합니다.

## 신규 메뉴 개발 체크리스트

신규 메뉴 또는 기존 메뉴 대폭 수정 시 아래 항목을 확인합니다.

- [ ] 최상위 래퍼에 `page-wrap` 또는 동일한 폭 제한 규칙이 있는가?
- [ ] 목록 영역은 `table-card` 또는 `grid-card` 안에 있는가?
- [ ] Ant Table에 `scroll.x`가 지정되어 있는가?
- [ ] 긴 텍스트 컬럼에 `ellipsis` 또는 tooltip이 있는가?
- [ ] 금액/수량 컬럼이 한 줄로 보이는가?
- [ ] 페이지당 개수 변경이 실제 목록에 반영되는가?
- [ ] 모달 하단 버튼이 `1366x768`에서 잘리지 않는가?
- [ ] 테이블 헤더가 첫 행을 덮지 않는가?
- [ ] 직접 만든 table은 `thead`가 아니라 `th`에 sticky가 적용되어 있는가?
- [ ] 등록/수정/삭제 버튼이 잘리지 않는가?
- [ ] `npm.cmd run build`가 성공하는가?

## 검증 기준

PC 반응형 변경 후 최소 아래 해상도에서 확인합니다.

| 해상도 | 확인 목적 |
| --- | --- |
| `1920x1080` | 일반 데스크톱 기준 |
| `1600x900` | 넓은 노트북 기준 |
| `1440x900` | 사내 노트북 기준 |
| `1366x768` | 최소 PC 기준 |

검증 명령:

```powershell
cd D:\5.솔루션기술팀\97.개발\LSS_ERP\frontend
npm.cmd run build
```

## 유지보수 원칙

- 화면별 임시 CSS보다 공통 CSS를 우선 사용합니다.
- `main.css`에 이미 있는 모달/테이블 규칙을 중복 작성하지 않습니다.
- sticky header 문제는 전역 CSS로 강제 해결하지 말고 해당 테이블의 구조를 먼저 확인합니다.
- Ant Table과 일반 HTML Table의 규칙을 섞지 않습니다.
- 새 화면을 만들 때 기존 메뉴 중 가장 유사한 화면의 구조를 먼저 참고합니다.
