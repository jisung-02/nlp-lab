# NLP Lab Website

FastAPI + Jinja2 + SQLModel + Alembic 기반의 연구실 웹사이트입니다.

이 README는 아래 3가지 문서를 하나로 합친 운영 문서입니다.
1. Quickstart: 로컬 실행/검증
2. Architecture Guide: 코드 구성과 기술 선택 이유
3. Maintenance Playbook: 변경 작업 절차와 체크리스트

## 목차

- [1. 빠른 시작](#1-빠른-시작)
- [2. 프로젝트가 해결하는 문제](#2-프로젝트가-해결하는-문제)
- [3. 기술 스택과 선택 이유](#3-기술-스택과-선택-이유)
- [4. 아키텍처 기본 원리](#4-아키텍처-기본-원리)
- [5. 코드 구성 방식](#5-코드-구성-방식)
- [6. 요청 처리 흐름 예시](#6-요청-처리-흐름-예시)
- [7. 데이터 모델 개념](#7-데이터-모델-개념)
- [8. 인증/보안 개념](#8-인증보안-개념)
- [9. 실행/관리 방법 (poe task)](#9-실행관리-방법-poe-task)
- [10. 변경 작업 플레이북](#10-변경-작업-플레이북)
- [11. 테스트 전략과 완료 기준](#11-테스트-전략과-완료-기준)
- [12. 트러블슈팅](#12-트러블슈팅)
- [13. 학습 경로 (AI/신규 기여자)](#13-학습-경로-ai신규-기여자)

## 1. 빠른 시작

### 요구사항

- Python `3.12.x`
- `uv`

### 설치

```bash
uv venv
uv sync
cp .env.example .env
```

### 환경 변수

필수로 확인할 값:

- `SECRET_KEY`: 세션 서명 키
- `DATABASE_URL`: DB 연결 문자열
- `ADMIN_USERNAME`: 초기 관리자 ID
- `ADMIN_PASSWORD`: 초기 관리자 비밀번호

운영 시 자주 조정하는 값:

- `APP_ENV`: `development` | `test` | `production`
- `APP_DEBUG`: 디버그 모드
- `CONTACT_EMAIL`, `CONTACT_ADDRESS`, `CONTACT_MAP_URL`: 연락처 페이지 정보

참고:
- `.env.example`의 `APP_HOST`, `APP_PORT`는 현재 설정 모델에서 사용하지 않으며 무시됩니다.

### DB 반영 및 초기 관리자 생성

```bash
uv run poe migrate
uv run poe init-admin
```

### 실행

```bash
uv run poe serve
```

### 화면 경로

Public:
- `GET /`
- `GET /members`
- `GET /projects`
- `GET /projects/{slug}`
- `GET /publications`
- `GET /contact`

Admin:
- `GET /admin/login`
- `POST /admin/login`
- `POST /admin/logout`
- `GET /admin`
- `GET /admin/members`
- `GET /admin/projects`
- `GET /admin/publications`
- `GET /admin/posts`

Admin CRUD (POST):
- `POST /admin/members`, `POST /admin/members/{id}/update`, `POST /admin/members/{id}/delete`
- `POST /admin/projects`, `POST /admin/projects/{id}/update`, `POST /admin/projects/{id}/delete`
- `POST /admin/publications`, `POST /admin/publications/{id}/update`, `POST /admin/publications/{id}/delete`
- `POST /admin/posts`, `POST /admin/posts/{id}/update`, `POST /admin/posts/{id}/delete`

## 2. 프로젝트가 해결하는 문제

이 프로젝트는 "연구실 소개/성과 공개"와 "관리자 콘텐츠 관리"를 분리해 제공합니다.

- Public: 방문자가 멤버, 프로젝트, 논문, 연락처를 조회
- Admin: 운영자가 Member/Project/Publication/Post를 CRUD
- 보안: 관리자 인증 + CSRF 방어 + 세션 쿠키 보호 옵션

즉, 정적 페이지 수준의 단순함을 유지하면서도 운영자가 데이터를 즉시 수정할 수 있는 SSR 관리형 웹입니다.

## 3. 기술 스택과 선택 이유

### Runtime

- FastAPI: 라우팅/DI/폼 처리/응답을 단순하게 유지하면서 Python 타입 기반 개발 가능
- Jinja2: 서버 렌더링 템플릿으로 학습 난이도가 낮고, SEO/초기 로딩에 유리
- SQLModel + SQLAlchemy: Pydantic 타입과 ORM 모델을 같은 언어로 다루기 쉬움
- Alembic: DB 스키마 변경 이력을 코드로 관리 가능
- passlib[bcrypt]/bcrypt: 관리자 비밀번호를 평문이 아닌 해시로 저장
- pydantic-settings: `.env` 기반 환경 설정 일관화

### Dev Tooling

- uv + uv.lock: 로컬/CI 의존성 재현성 확보
- ruff: lint/format 빠른 피드백
- ty: 타입 검증
- pytest: 라우트/인증/CRUD 회귀 테스트
- poethepoet: 실행 명령을 `poe task`로 표준화

## 4. 아키텍처 기본 원리

### 4.1 SSR(Server-Side Rendering)

브라우저 요청 시 서버가 HTML을 렌더링해 응답합니다.

- 장점: 구조 단순, SEO 우호적, 초기 로딩 시 데이터 포함
- 이 프로젝트 적합성: 연구실 소개 사이트 + 관리자 폼 기반 CRUD

### 4.2 레이어 분리 원리

이 프로젝트는 "관리자 CRUD"에 대해 계층 분리를 적용합니다.

- Router: HTTP 입력/응답, 상태 코드, 템플릿 렌더링
- Service: 비즈니스 규칙(중복 검증, 삭제 가능 여부 등)
- Repository: DB 질의/저장
- Model/Schema: 영속 모델과 입력 스키마 분리

의존 방향:
- `router -> service -> repository -> db`
- 역방향 참조 금지

주의:
- Public 조회 라우트는 단순 읽기 특성상 일부 쿼리를 Router에서 직접 수행합니다.
- Admin CRUD는 Service/Repository를 경유합니다.

### 4.3 마이그레이션 원리

- `SQLModel.metadata.create_all()`은 초기 개발/테스트 편의용
- 운영 스키마 변경은 Alembic 마이그레이션이 기준
- 모델 필드 변경 시 반드시 새 마이그레이션 생성/적용 필요

## 5. 코드 구성 방식

```text
app/
  main.py                    # 앱 팩토리, 미들웨어, 라우터 등록
  core/
    config.py                # 환경 변수 설정
    security.py              # 비밀번호 해시/검증
    constants.py             # Enum, 공통 상수/UTC 헬퍼
  db/
    session.py               # 엔진/세션
    init_db.py               # 초기 테이블/관리자 생성
  models/                    # SQLModel ORM 모델
  schemas/                   # 입력 검증 스키마
  repositories/              # DB 접근 계층
  services/                  # 비즈니스 규칙 계층
  routers/                   # Public/Admin 라우트
  templates/                 # Jinja2 템플릿
  static/                    # CSS/JS/이미지
alembic/                     # 마이그레이션
tests/                       # 통합/라우트 회귀 테스트
```

파일을 수정할 때는 아래 기준을 우선 적용합니다.

- 입력값 검증 규칙 변경: `app/schemas/*`
- CRUD 정책/업무 규칙 변경: `app/services/*`
- 정렬/조회 쿼리 변경: `app/repositories/*` 또는 Public Router 조회부
- 라우트/응답 형식 변경: `app/routers/*`
- 템플릿 출력 변경: `app/templates/*`
- 필드 변경: `app/models/*` + `alembic/versions/*`

## 6. 요청 처리 흐름 예시

### 예시 A: Public `GET /projects/{slug}`

1. `app/routers/public.py`의 `project_detail_page`가 요청 수신
2. `Project.slug`로 프로젝트 조회
3. `Publication.related_project_id == project.id` 조건으로 관련 논문 조회
4. `public/project_detail.html` 템플릿 렌더링 반환

핵심: 공개 조회는 단순 읽기 경로라 Router에서 직접 조회합니다.

### 예시 B: Admin `POST /admin/projects/{id}/update`

1. `app/routers/admin_project.py`가 폼/CSRF 검증
2. `project_service.parse_project_update_input`으로 입력 스키마 검증
3. `project_service.update_project`에서 비즈니스 검증(존재/slug 중복)
4. `project_repo.update_project`에서 DB 커밋
5. 성공 시 `/admin/projects`로 303 리다이렉트

핵심: 관리자 쓰기 경로는 Service/Repository를 통과해 규칙을 집중 관리합니다.

## 7. 데이터 모델 개념

### 공통 규칙

- PK: `id: int`
- 시각: `created_at`, `updated_at` (UTC)
- 문자열은 길이 제한 명시
- 삭제 정책: v1은 hard delete

### 모델 요약

- `AdminUser`: 관리자 계정(유니크 `username`, `password_hash`)
- `Member`: 연구실 구성원(역할 enum, 유니크 `email`, 정렬용 `display_order`)
- `Project`: 프로젝트(`slug` 유니크, 진행상태 enum, 기간)
- `Publication`: 논문(`year` 인덱스, 선택적 `related_project_id`)
- `Post`: 소식 글(`slug` 유니크, 공개 여부)

### 관계

- `Project (1) - Publication (N)`
- 연결 키: `Publication.related_project_id`

## 8. 인증/보안 개념

### 비밀번호

- `app/core/security.py`에서 bcrypt 해시 저장/검증
- 평문 저장 금지

### 세션 쿠키

- `app/main.py` 미들웨어에서 서명 쿠키 decode/encode
- 옵션:
  - `HttpOnly=True`
  - `SameSite=Lax`
  - `Secure=True` (production)

### 관리자 보호

- `/admin/*` 요청은 로그인 필요
- 미인증 사용자는 `/admin/login`으로 303 리다이렉트

### CSRF

- 서버가 세션에 토큰 발급
- 모든 Admin POST는 토큰 검증
- 불일치 시 `403`

## 9. 실행/관리 방법 (poe task)

### 주요 태스크

- `uv run poe serve`: 개발 서버 실행
- `uv run poe migrate`: DB 최신 마이그레이션 적용
- `uv run poe migration --MSG "message"`: 마이그레이션 생성
- `uv run poe init-admin`: 초기 관리자 생성
- `uv run poe lint`: Ruff lint
- `uv run poe format`: Ruff format
- `uv run poe typecheck`: Ty check
- `uv run poe test`: Pytest
- `uv run poe check`: lint + typecheck + test

### 일상 운영 루틴

```bash
uv run poe migrate
uv run poe check
uv run poe serve
```

## 10. 변경 작업 플레이북

### 10.1 Public 화면/조회 변경

수정 대상(일반):
- `app/routers/public.py`
- `app/templates/public/*`
- 필요 시 `app/static/css/public.css`

검증:
- `uv run poe test`
- `tests/test_public_routes.py` 관련 케이스 확인

### 10.2 Admin CRUD 정책 변경

수정 대상(일반):
- Router: `app/routers/admin_*.py`
- Service: `app/services/*_service.py`
- Repository: `app/repositories/*_repo.py`
- Template: `app/templates/admin/*.html`

검증:
- `uv run poe test`
- `tests/test_admin_auth.py`, `tests/test_member_crud.py`, `tests/test_admin_content_crud.py`

### 10.3 모델 필드 추가/수정

순서:
1. `app/models/*.py` 수정
2. `uv run poe migration --MSG "..."`
3. 생성된 `alembic/versions/*.py` 수동 검토
4. `uv run poe migrate`
5. 관련 Service/Schema/Template/Tests 동기화

주의:
- 모델 변경 후 마이그레이션 누락은 릴리스 차단 이슈

## 11. 테스트 전략과 완료 기준

### 테스트 파일 역할

- `tests/test_public_routes.py`: Public 렌더링/정렬/필터
- `tests/test_admin_auth.py`: 관리자 인증/보호 경로/CSRF
- `tests/test_member_crud.py`: Member CRUD + CSRF
- `tests/test_admin_content_crud.py`: Project/Publication/Post CRUD + CSRF

### 품질 게이트

```bash
uv run poe lint
uv run poe typecheck
uv run poe test
```

또는 한 번에:

```bash
uv run poe check
```

### 릴리스 전 스모크 체크리스트

1. `uv run poe migrate`
2. Public 6개 화면 렌더링 확인
3. Admin 로그인/로그아웃 및 5개 관리 화면 확인
4. 관리자 CRUD(Member/Project/Publication/Post) 기본 동작 확인
5. `uv run poe check` 통과

## 12. 트러블슈팅

### `alembic upgrade head` 실패

점검:
- `DATABASE_URL`이 기대 DB를 가리키는지
- 마이그레이션 파일 충돌/누락 여부

조치:
- 최신 마이그레이션 재확인 후 `uv run poe migrate` 재시도

### 로그인 후 다시 `/admin/login`으로 돌아감

점검:
- `SECRET_KEY`가 실행 중 변경되었는지
- 쿠키가 브라우저에서 차단되는지

조치:
- `SECRET_KEY` 고정
- 개발 환경에서 동일 도메인/프로토콜 사용

### CSRF 403 발생

점검:
- 폼의 `csrf_token` hidden input 존재 여부
- 페이지 렌더 후 오래된 탭 재사용 여부

조치:
- 페이지 새로고침 후 재시도
- Admin 템플릿의 CSRF 필드 누락 여부 확인

### 스타일/템플릿 변경이 안 보임

점검:
- 서버 재시작 여부
- 브라우저 캐시

조치:
- 강력 새로고침 후 확인

## 13. 학습 경로 (AI/신규 기여자)

### 13.1 최소 학습 순서

1. `app/main.py`: 앱 생성, 미들웨어, 라우터 등록
2. `app/routers/public.py`, `app/routers/admin_*.py`: 요청 진입점
3. `app/services/*`: 비즈니스 규칙
4. `app/repositories/*`: DB 접근 패턴
5. `app/models/*`, `app/schemas/*`: 데이터 모델/입력 계약
6. `tests/*`: 실제 동작 기준(회귀 방지)

### 13.2 작업 전/후 체크

작업 전:
- 어떤 레이어를 수정해야 하는지 먼저 결정
- 모델 변경인지(=마이그레이션 필요) 먼저 판단

작업 후:
- `uv run poe check`
- 변경한 기능과 연결된 라우트/폼 직접 확인
- README와 코드 동기화 확인

### 13.3 AI 에이전트용 유지보수 원칙

- 코드베이스의 기존 레이어 경계를 유지
- Public 단순 조회는 과한 추상화 지양
- Admin 쓰기 경로는 Service/Repository를 통해 일관 규칙 유지
- 모델 변경 시 마이그레이션/테스트를 항상 같이 갱신

이 원칙을 지키면 구조를 단순하게 유지하면서도 회귀를 줄일 수 있습니다.
