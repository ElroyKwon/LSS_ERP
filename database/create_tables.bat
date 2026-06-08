@echo off
chcp 65001 > nul
set PSQL=C:\Program Files\PostgreSQL\18\bin\psql.exe

echo ============================================
echo   LSS_ERP 데이터베이스 - 테이블 생성
echo ============================================
echo.

set /p PGPASS=postgres 관리자 비밀번호 입력:
set PGPASSWORD=%PGPASS%

echo.
echo [1/2] LSS_ERP 데이터베이스에 테이블 생성 중...
"%PSQL%" -U postgres -d LSS_ERP -f "%~dp0init.sql" 2>&1
set ERR=%ERRORLEVEL%

if %ERR% NEQ 0 (
    echo.
    echo [재시도] 소문자(lss_erp)로 재시도 중...
    "%PSQL%" -U postgres -d lss_erp -f "%~dp0init.sql" 2>&1
    set ERR=%ERRORLEVEL%
)

if %ERR% NEQ 0 (
    echo.
    echo [ERROR] 테이블 생성 실패. 위 오류 메시지를 확인하세요.
    pause & exit /b 1
)

echo.
echo [2/2] 완료!
echo ============================================
echo  테이블 생성 완료
echo  이제 backend\.env 에서 DB 접속 정보를 설정하세요
echo ============================================
pause
