# LSS ERP 배포 문서

## 운영 환경

- 운영 대상은 Ubuntu 서버입니다.
- 운영 도메인은 `https://erp.sauter.co.kr` 입니다.
- 현재 구조에서는 FastAPI가 빌드된 Vue SPA(`frontend/dist`)를 함께 제공합니다.
- 운영 비밀값은 `backend/.env`에만 보관하고 Git에 커밋하지 않습니다.

## 운영 환경변수

Ubuntu 서버의 `backend/.env`에 아래 값을 설정합니다.

```env
DATABASE_URL=postgresql+pg8000://<user>:<password>@<host>:5432/<database>
SECRET_KEY=<strong-random-secret-at-least-32-chars>
ENVIRONMENT=production
DEBUG=false
API_DOCS_ENABLED=false
AUTO_CREATE_SCHEMA=false
ALLOWED_ORIGINS=https://erp.sauter.co.kr
ALLOWED_HOSTS=erp.sauter.co.kr,localhost,127.0.0.1
NTS_BUSINESS_STATUS_SERVICE_KEY=<data-go-kr-key>
POSTAL_SERVICE_KEY=<epost-key>
```

운영 서버에서 로컬 Vite 개발 접속도 함께 허용해야 한다면 로컬 origin을 같이 포함합니다.

```env
ALLOWED_ORIGINS=https://erp.sauter.co.kr,http://localhost:5173,http://localhost:3000
ALLOWED_HOSTS=erp.sauter.co.kr,localhost,127.0.0.1
```

## 배포 체크리스트

1. Python, Node.js LTS, PostgreSQL, Nginx 같은 리버스 프록시를 설치합니다.
2. PostgreSQL 운영 DB와 운영 DB 사용자를 생성합니다.
3. 서버에 운영 값이 반영된 `backend/.env`를 배치합니다.
4. `backend` 디렉터리에서 `alembic upgrade head`를 실행해 DB 마이그레이션을 적용합니다.
5. `frontend` 디렉터리에서 `npm run build`로 프론트엔드를 빌드합니다.
6. systemd와 Uvicorn으로 FastAPI를 실행합니다.
7. Uvicorn 앞단에 Nginx를 두고 Nginx에서 HTTPS를 종료합니다.
8. `erp.sauter.co.kr` DNS를 Ubuntu 서버로 연결합니다.
9. 공개 API 문서가 꼭 필요한 경우가 아니라면 `API_DOCS_ENABLED=false`로 설정합니다.
10. 배포 후 로그인, 업체 등록, 국세청 사업자 상태 조회, 우편번호 조회를 테스트합니다.

## Ubuntu 스크립트 배포

저장소의 `scripts/` 디렉터리에 Ubuntu 배포 보조 스크립트가 있습니다.

서버 최초 설정:

```bash
cd /opt/lss-erp
cp backend/.env.example backend/.env
nano backend/.env
chmod +x scripts/*.sh
SKIP_PULL=1 SKIP_SERVICE_RESTART=1 ./scripts/deploy-ubuntu.sh
./scripts/install-ubuntu-service.sh
./scripts/check-ubuntu-deploy.sh
```

코드 반영 후 일반 배포:

```bash
cd /opt/lss-erp
BRANCH=main SERVICE_NAME=lss-erp ./scripts/deploy-ubuntu.sh
```

자주 쓰는 옵션:

```bash
SKIP_PULL=1 ./scripts/deploy-ubuntu.sh          # 서버의 현재 체크아웃 상태로 배포
SKIP_MIGRATIONS=1 ./scripts/deploy-ubuntu.sh    # Alembic 마이그레이션 생략
ALLOW_DIRTY=1 ./scripts/deploy-ubuntu.sh        # 서버의 미커밋 변경 허용
PORT=8000 ./scripts/install-ubuntu-service.sh   # 지정 포트로 서비스 설치
```

## `erp.sauter.co.kr` Nginx 및 HTTPS 설정

프론트엔드는 API 기본 경로로 상대 경로 `/api`를 사용합니다. 따라서 운영 도메인용 프론트엔드 빌드 환경변수를 별도로 지정할 필요가 없습니다. 운영에서는 Nginx가 `erp.sauter.co.kr`의 HTTPS를 처리하고 모든 요청을 Uvicorn으로 프록시합니다.

Nginx 최초 설정 예시:

```bash
sudo cp scripts/nginx-lss-erp.conf /etc/nginx/sites-available/lss-erp
sudo ln -sfn /etc/nginx/sites-available/lss-erp /etc/nginx/sites-enabled/lss-erp
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d erp.sauter.co.kr
```

DNS와 HTTPS 설정이 완료되면 아래 명령으로 확인합니다.

```bash
curl -I https://erp.sauter.co.kr/
curl -fsS https://erp.sauter.co.kr/api/openapi.json
```

`API_DOCS_ENABLED=false`인 경우 OpenAPI 확인 명령은 404를 반환하는 것이 정상입니다. 이 경우 로그인 또는 인증이 필요한 다른 API로 스모크 테스트를 진행합니다.

배포 스크립트는 아래 작업을 수행합니다.

1. `git pull --ff-only`
2. Python 가상환경 및 패키지 설치
3. `alembic upgrade head`
4. 프론트엔드 `npm ci` 및 `npm run build`
5. `systemctl restart lss-erp`
6. HTTP 응답 확인

서비스 재시작 후 배포가 실패하면 아래 로그를 확인합니다.

```bash
sudo journalctl -u lss-erp -n 100 --no-pager
sudo journalctl -u lss-erp -f
```

## DB 마이그레이션

DB 스키마 이력은 `backend/alembic`의 Alembic으로 관리합니다.

`backend` 디렉터리에서 자주 사용하는 명령:

```bash
alembic current
alembic upgrade head
alembic revision --autogenerate -m "describe schema change"
```

로컬 개발에서는 편의를 위해 `AUTO_CREATE_SCHEMA=true`를 유지할 수 있습니다. 운영에서는 스키마 변경이 명시적인 Alembic 마이그레이션을 통해서만 적용되도록 `AUTO_CREATE_SCHEMA=false`를 사용합니다.

## 외부 API 참고

- 국세청 사업자 상태 조회는 `https://api.odcloud.kr/api/nts-businessman/v1/status`를 사용합니다.
- 우편번호 조회는 `retrieveNewAdressAreaCdSearchAllService/getNewAddressListAreaCdSearchAll`를 사용합니다.
- 외부 서비스 키가 없거나 만료되었거나 거부되면 프론트엔드에서 전용 팝업을 표시합니다.
- 관리자 사용자는 해당 팝업에서 외부 API 키를 갱신할 수 있으며, 백엔드는 새 값을 `backend/.env`에 기록하고 실행 중인 설정에도 반영합니다.

## 현재 운영 제약

- 로컬 개발 호환성을 위해 `AUTO_CREATE_SCHEMA=true`일 때 `Base.metadata.create_all()` 및 `ensure_master_columns()` 계열 보정 로직이 동작합니다. 운영에서 마이그레이션을 사용한 이후에는 비활성화해야 합니다.
- 현재는 FastAPI가 `frontend/dist`를 제공합니다. 트래픽이 증가하면 정적 파일은 Nginx에서 직접 제공하는 구성이 더 적합합니다.
