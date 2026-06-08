@echo off
chcp 65001 > nul
setlocal

:: ── PostgreSQL 경로 (버전에 따라 자동 탐색) ─────────────────
set PSQL=
for /d %%v in ("C:\Program Files\PostgreSQL\*") do (
    if exist "%%v\bin\psql.exe" set PSQL=%%v\bin\psql.exe
)
if "%PSQL%"=="" (
    echo [ERROR] PostgreSQL psql.exe를 찾을 수 없습니다.
    echo         C:\Program Files\PostgreSQL\버전\bin\psql.exe 위치를 확인하세요.
    pause & exit /b 1
)
echo [INFO] psql 경로: %PSQL%

:: ── 설명 ──────────────────────────────────────────────────────
echo.
echo ============================================================
echo   LSS ERP - PostgreSQL 데이터베이스 초기화
echo ============================================================
echo.
echo  [생성 대상]
echo   - 데이터베이스: lss_erp   (신규 생성, 기존 DB와 완전 분리)
echo   - 사용자:       erp_user  (신규 생성)
echo   - 비밀번호:     erp_password
echo.
echo  [기존 데이터에 영향 없음]
echo   - LSS_SHE 또는 다른 기존 DB/스키마는 전혀 건드리지 않습니다.
echo   - 오직 'lss_erp' 데이터베이스만 생성됩니다.
echo.
echo ============================================================
echo.

:: ── 접속 정보 입력 ────────────────────────────────────────────
set /p PGHOST=PostgreSQL 서버 주소 [기본값: localhost]:
if "%PGHOST%"=="" set PGHOST=localhost

set /p PGPORT=PostgreSQL 포트 [기본값: 5432]:
if "%PGPORT%"=="" set PGPORT=5432

set /p PGPASS=postgres 관리자 비밀번호:
if "%PGPASS%"=="" (
    echo [ERROR] 비밀번호를 입력하세요.
    pause & exit /b 1
)
set PGPASSWORD=%PGPASS%

echo.

:: ── 1단계: erp_user 계정 생성 ─────────────────────────────────
echo [1/4] erp_user 계정 생성...
"%PSQL%" -h %PGHOST% -p %PGPORT% -U postgres ^
  -c "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='erp_user') THEN CREATE USER erp_user WITH PASSWORD 'erp_password'; END IF; END $$;"
if errorlevel 1 (
    echo [ERROR] postgres 접속 실패. 비밀번호와 서버 주소를 확인하세요.
    pause & exit /b 1
)

:: ── 2단계: lss_erp 데이터베이스 생성 ─────────────────────────
echo [2/4] lss_erp 데이터베이스 생성...
"%PSQL%" -h %PGHOST% -p %PGPORT% -U postgres ^
  -c "SELECT 1 FROM pg_database WHERE datname='lss_erp'" | findstr /c:"1 row" > nul
if errorlevel 1 (
    "%PSQL%" -h %PGHOST% -p %PGPORT% -U postgres ^
      -c "CREATE DATABASE lss_erp OWNER erp_user ENCODING 'UTF8' TEMPLATE template0;"
) else (
    echo       (lss_erp 이미 존재 - 건너뜀)
)

:: ── 3단계: 권한 부여 ──────────────────────────────────────────
echo [3/4] 권한 부여...
"%PSQL%" -h %PGHOST% -p %PGPORT% -U postgres ^
  -c "GRANT ALL PRIVILEGES ON DATABASE lss_erp TO erp_user;"

:: ── 4단계: 테이블 스키마 생성 ────────────────────────────────
echo [4/4] 테이블 생성 중...
set PGPASSWORD=erp_password
"%PSQL%" -h %PGHOST% -p %PGPORT% -U erp_user -d lss_erp -f "%~dp0init.sql"
if errorlevel 1 (
    echo [ERROR] SQL 스크립트 실행 실패. 에러 메시지를 확인하세요.
    pause & exit /b 1
)

:: ── 완료 ──────────────────────────────────────────────────────
echo.
echo ============================================================
echo   DB 초기화 완료!
echo.
echo   backend\.env 파일의 DATABASE_URL을 아래로 설정하세요:
echo   DATABASE_URL=postgresql+pg8000://erp_user:erp_password@%PGHOST%:%PGPORT%/lss_erp
echo ============================================================
endlocal
pause
