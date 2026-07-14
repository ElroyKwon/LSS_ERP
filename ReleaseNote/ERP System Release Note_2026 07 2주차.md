# ERP System Release Note_2026 07 2주차

## 기간

2026-07-06 ~ 2026-07-10

## 요약

- 타임시트 화면과 API에 직원/부서 권한 범위가 반영되고, 주간/월간 입력 화면의 프로젝트 검색, 작업유형, 총 시간 표시가 보완되었다.
- 의견 청취 첨부파일 처리에서 다운로드 API 사용 방식과 PDF 미리보기 UI가 개선되었다.
- 전사일정 메뉴가 추가되고 Google Calendar 및 공공데이터포털 공휴일 API 연동 기반이 구현되었다.
- 작성 중인 모달/드로어를 닫을 때 실제 변경 여부를 기준으로 확인 팝업을 띄우도록 공통 팝업 닫기 처리가 개선되었다.
- 현재 작업트리에 Google Calendar 설정 관련 미커밋 변경 및 인증 파일이 남아 있어 배포 전 검토가 필요하다.

## 메뉴별 변경 사항

### 타임시트

#### 기능 수정 사항

- 타임시트 조회/저장/통계/팀 현황 API에 사용자 권한 범위가 적용되었다.
  - 시스템 관리자는 전체 직원 타임시트를 조회할 수 있다.
  - 부서 관리자 역할은 본인 부서 및 하위 부서 직원 범위로 제한된다.
  - 일반 사용자는 본인 타임시트만 접근하도록 제한된다.
- 타임시트 직원 목록 조회 API가 추가되어 화면에서 접근 가능한 직원만 선택할 수 있게 되었다.
- 프로젝트 자동완성 검색이 프로젝트 번호와 프로젝트명을 함께 기준으로 검색되도록 개선되었다.
- 작업유형 기본값 및 기존 데이터 표시가 `공통 > 기타` 형태의 계층형 값으로 보정되었다.
- SPG 선택값에 `공통`이 추가되었다.
- 주간 입력 화면의 일별 합계 표시가 입력값이 있는 날을 강조하도록 조정되었다.
- 작업유형 선택 영역 폭과 드롭다운 표시가 보완되어 긴 작업유형명을 더 안정적으로 볼 수 있게 되었다.
- 타임시트 저장 로직에서 Pydantic v2 방식인 `model_dump()`를 사용하도록 수정되어 저장 호환성이 개선되었다.

#### 기술적인 내용

- `backend/app/routers/timesheet.py`
  - `Department`, 권한 유틸을 사용해 현재 사용자의 부서 및 역할 기준 접근 가능 직원 ID를 계산한다.
  - `/api/timesheets/employees` 엔드포인트가 추가되었다.
  - `/api/timesheets`, `/api/timesheets/week`, `/api/timesheets`, `/api/timesheets/team-status`, `/api/timesheets/stats`에 직원 접근 권한 검증이 추가되었다.
  - 저장 시 Entry 스키마 직렬화가 `dict()`에서 `model_dump()`로 변경되었다.
- `frontend/src/views/TimesheetView.vue`
  - 프로젝트 자동완성 옵션에 `project_no`, `project_name`, 검색용 텍스트를 함께 구성한다.
  - 작업유형 기본값 정규화 및 월간 집계 키 구성에 작업유형 보정이 반영되었다.
  - 작업유형 컬럼 폭과 선택 트리 UI 스타일이 조정되었다.
- `frontend/src/api/index.js`
  - 타임시트 관련 API 호출 항목이 보강되었다.

### 의견 청취

#### 기능 수정 사항

- 첨부파일 클릭 시 PDF 파일은 화면 안에서 미리보기로 열 수 있게 되었다.
- PDF 미리보기 모달은 화면 크기에 맞춰 기본 크기를 계산하고, 사용자가 크기를 조절할 수 있다.
- PDF가 아닌 첨부파일은 미리보기 대신 다운로드 버튼을 사용하도록 안내한다.
- 첨부파일 다운로드 버튼이 별도로 추가되었다.
- 한글/특수문자 파일명 다운로드 처리를 개선해 파일명 인코딩 안정성을 높였다.

#### 기술적인 내용

- `backend/app/routers/opinion.py`
  - `Content-Disposition` 헤더의 파일명 인코딩에서 `quote(..., safe='')`를 사용하도록 수정되었다.
- `frontend/src/api/index.js`
  - `opinionApi.downloadAttachment()`가 추가되어 blob 다운로드를 API 모듈을 통해 수행한다.
- `frontend/src/views/OpinionListeningView.vue`
  - 첨부파일 blob을 받아 PDF 여부를 판별하고, PDF는 Object URL 기반 iframe 미리보기로 표시한다.
  - 미리보기 URL 해제, 모달 닫기, 컴포넌트 해제 시 리소스 정리 로직이 추가되었다.
  - 미리보기 모달의 width/height 조절 로직과 pointer 이벤트 기반 resize 처리가 추가되었다.

### 전사일정

#### 기능 수정 사항

- 사이드바에 `전사일정` 단독 메뉴가 추가되었다.
- 전사 월간 일정과 전사 휴가 일정을 탭으로 나누어 조회/등록할 수 있는 캘린더 화면이 추가되었다.
- 캘린더에서 일자별 일정 목록을 표시하고, 날짜 클릭 시 상세 목록을 확인할 수 있다.
- 일정 등록 시 등록자 이름을 포함해 Google Calendar에 일정을 생성하도록 구성되었다.
- 공공데이터포털 공휴일 API를 통해 공휴일을 조회하고, 주말/공휴일을 달력에서 붉은 날짜로 표시한다.

#### 기술적인 내용

- `backend/app/routers/schedule.py`
  - `/api/schedules` GET/POST API가 추가되었다.
  - Google Calendar service account 인증 파일과 캘린더 ID를 환경 변수에서 읽어 회사 일정 및 휴가 일정 캘린더를 분기한다.
  - Google Calendar 이벤트 summary의 `[사용자] 내용` 형식을 파싱해 `user_name`, `content`, `date`, `type` 응답으로 변환한다.
  - 일정 생성 시 Asia/Seoul 기준의 종일 일정으로 Google Calendar 이벤트를 등록한다.
- `backend/app/routers/holiday.py`
  - `/api/holiday?year=YYYY` API가 추가되었다.
  - 공공데이터포털 특일정보 API에서 공휴일 날짜를 `YYYY-MM-DD` 배열로 반환한다.
- `backend/app/main.py`
  - `holiday`, `schedule` 라우터가 FastAPI 앱에 등록되었다.
- `backend/app/config.py`, `backend/.env.example`
  - Google Calendar 및 공공데이터포털 연동용 환경 변수 항목이 추가되었다.
- `backend/requirements.txt`
  - `google-auth`, `google-auth-oauthlib`, `google-api-python-client` 의존성이 추가되었다.
- `frontend/src/views/CalendarView.vue`
  - Ant Design Vue Calendar 기반의 전사 월간 일정/전사 휴가 일정 탭 화면이 추가되었다.
- `frontend/src/router/index.js`, `frontend/src/components/AppLayout.vue`, `frontend/src/utils/permissions.js`
  - 전사일정 라우트, 메뉴, 권한 접근 경로가 추가되었다.

### UI 공통 처리

#### 기능 수정 사항

- 작성 중인 모달/드로어 닫기 확인 팝업이 실제 입력값 변경 여부를 기준으로 동작하도록 개선되었다.
- 값이 변경되지 않은 팝업은 확인 없이 닫히고, 변경된 팝업에서만 “작성을 취소하시겠습니까?” 확인이 표시된다.
- input, textarea, select 외에도 Ant Design Vue select, date picker, input number, upload, contenteditable 요소의 변경 감지가 보강되었다.
- ESC 키, 모달 닫기 버튼, 드로어 마스크 클릭 등 닫기 경로별 처리가 정리되었다.
- 공지 팝업 등 예외 팝업은 기존처럼 닫기 확인 대상에서 제외된다.

#### 기술적인 내용

- `frontend/src/utils/confirmPopupClose.js`
  - WeakMap/WeakSet 기반으로 팝업별 초기 입력 스냅샷과 dirty 상태를 관리한다.
  - `pointerdown`, `focusin`, `input`, `change`, `click`, `keydown` 이벤트를 통해 변경 감지와 닫기 확인을 분리한다.
  - close 버튼/마스크/ESC 동작에서 dirty 여부에 따라 확인 또는 즉시 닫기를 수행한다.

## 미커밋 변경사항

- `backend/app/config.py`
  - `typing` import에 `Optional`이 추가되어 Google Calendar 설정 필드 타입 선언에서 필요한 import 누락을 보완하고 있다.
- `backend/credentials/lss-refresh.json`, `backend/credentials/lss-work.json`
  - Google Calendar service account 인증 파일로 보이는 미추적 파일이 존재한다. 민감정보 가능성이 있어 내용은 확인하지 않았다.
- `backend/google_calendar.env`
  - Google Calendar 연동용 환경 변수 파일로 보이는 미추적 파일이 존재한다. 민감정보 가능성이 있어 내용은 확인하지 않았다.

## 배포/운영 참고사항

- Google Calendar 연동 기능 배포 전 아래 환경 변수와 인증 파일 경로가 서버에 준비되어야 한다.
  - `GOOGLE_CUSTOM_CREDENTIALS_DIR`
  - `GOOGLE_CUSTOM_KEY_WORK_NAME`
  - `GOOGLE_CUSTOM_CALENDAR_COMPANY_ID`
  - `GOOGLE_CUSTOM_KEY_REFRESH_NAME`
  - `GOOGLE_CUSTOM_CALENDAR_REFRESH_ID`
  - 공공데이터포털 공휴일 API 인증키 항목
- 인증 JSON 및 `google_calendar.env`는 저장소 커밋 대상에서 제외해야 한다.
- `backend/app/config.py`의 `Optional` import 보완은 현재 미커밋 상태이므로, 배포 전 커밋 포함 여부를 확인해야 한다.
- 신규 Python 의존성이 추가되었으므로 배포 환경에서 `backend/requirements.txt` 기준 패키지 설치가 필요하다.
- 전사일정 메뉴는 커밋 기준으로 사이드바에서 권한 조건 없이 노출된다. 운영 권한 정책에 맞는지 확인이 필요하다.
- 공휴일 환경 변수명은 코드와 `.env.example` 간 표기가 일치하는지 확인이 필요하다. 확인 결과 불일치 가능성이 있어 추정 사항으로 표시한다.

## 검증 또는 확인 사항

- git log 기준 확인 기간: `2026-07-06 00:00:00 +0900` ~ `2026-07-10 17:00:00 +0900`
- 확인한 커밋:
  - `dfa89cb` Modify timesheet save
  - `363069c` Modify timesheet work Type and Total time
  - `b17f9d5` Modify Timesheet total time
  - `9c69eb9` Modify file download
  - `96cf85c` Modify file befoer view
  - `1549252` Modify Popup
  - `a9b1f53` Modify WorkType
  - `3ca1c40` Modify timesheet
  - `3a5186a` google calendar api 연동추가
  - `6387e78` calendar_누락패치 업데이트
- 현재 작업트리 확인 결과 미커밋 변경사항이 존재한다.
- 이번 작업에서는 릴리즈노트 문서 생성만 수행했으며, 애플리케이션 빌드/테스트는 실행하지 않았다.
