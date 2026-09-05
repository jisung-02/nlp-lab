# 시스템 구조

NLP Lab은 FastAPI가 요청을 받고 Jinja2 템플릿으로 HTML을 렌더링하는 서버 렌더링 웹사이트다. 데이터 접근은 SQLModel과 SQLAlchemy 2.x를 사용하고, 스키마 변경은 Alembic으로 관리한다. 의존성의 정확한 버전 범위는 중복해서 복사하지 않고 [pyproject.toml](../pyproject.toml)을 기준으로 한다.

## 요청 흐름과 라우터

`app/main.py`가 애플리케이션, 세션 미들웨어, GZip, 정적 파일, 템플릿 환경을 구성한 뒤 라우터를 등록한다.

- `app/routers/public.py`: 홈, 구성원, 프로젝트 목록·상세, 논문, Contact, `robots.txt`, `llms.txt`, `sitemap.xml`, favicon, 검색엔진 검증 파일을 제공한다. 실제 경로와 SEO/레거시 301 리다이렉트 목록은 이 파일을 기준으로 한다.
- `app/routers/admin_auth.py`: 관리자 로그인·로그아웃과 대시보드 진입을 처리한다.
- `app/routers/admin_member.py`: 구성원 CRUD와 프로필 이미지 업로드를 처리한다.
- `app/routers/admin_project.py`: 프로젝트 CRUD를 처리한다.
- `app/routers/admin_publication.py`: 논문 CRUD와 프로젝트 연결을 처리한다.
- `app/routers/admin_post.py`: 게시글 CRUD와 홈 Hero 이미지 관리를 처리한다.

모든 관리자 화면과 관리자 CRUD 라우트는 `/admin` 아래에 있다. 관리자 페이지의 정확한 URL과 HTTP 메서드는 각 라우터 소스에서 확인한다. 오래된 공개 URL은 `public.py`의 `LEGACY_PUBLIC_REDIRECTS`에서 현재 URL로 301 리다이렉트한다.

## 데이터 모델과 관계

모델은 `app/models/`에 있다. 콘텐츠와 관리자 계정은 정수 기본 키와 UTC 타임스탬프를 사용하며, 관리자 세션은 토큰 해시를 기본 키로 사용한다.

- `AdminUser`: 고유 사용자명과 bcrypt 비밀번호 해시를 보관한다.
- `AdminSession`: `token_hash`를 기본 키로 하며 관리자, 만료 시각, 로그인 당시 `credential_hash`를 보관한다. `AdminUser` 하나가 여러 세션을 가질 수 있다.
- `Member`: 역할 enum, 고유 이메일, 표시 순서를 보관한다.
- `Project`: 고유 slug, 상태 enum, 시작일과 종료일을 보관한다.
- `Publication`: 연도와 선택적인 `related_project_id`를 보관한다.
- `Post`: 고유 slug, 본문, 공개 여부를 보관한다.

`Project`와 `Publication`은 1:N 관계다. 프로젝트 상세의 연관 논문은 `Publication.related_project_id == Project.id`로 조회한다. 모델을 변경할 때는 Alembic 마이그레이션을 함께 추가한다.

## 인증과 CSRF

관리자 인증은 서명된 세션 쿠키와 DB의 `AdminSession`을 함께 사용한다. 쿠키에는 세션 토큰과 관리자 식별자가 들어가고, 서버는 토큰 해시·관리자 ID·만료 시각·credential hash를 DB에서 확인한다. 비밀번호가 변경되면 저장된 비밀번호 해시에서 다시 계산한 credential hash가 달라져 기존 세션이 거부된다. 로그아웃은 해당 DB 세션을 삭제한 뒤 브라우저 세션을 비운다.

관리자 POST 요청은 폼의 CSRF 토큰을 세션 값과 상수 시간 비교로 검증한다. 검증에 실패하면 403을 반환한다. 세션 쿠키는 `HttpOnly`와 `SameSite=Lax`를 사용하고, `APP_ENV=production`일 때 `Secure`를 사용한다. 인증되지 않은 `/admin` 요청은 `/admin/login`으로 303 리다이렉트된다. 비밀번호는 bcrypt 해시만 저장한다.

## 정적 파일과 업로드

`/static`은 `CachedStaticFiles`가 제공한다. 저장소에 포함된 CSS, JavaScript, 아이콘은 `static_url()`이 콘텐츠 해시를 `v` 쿼리로 붙여 1년간 immutable 캐시할 수 있다. 관리자 업로드 이미지처럼 URL이 재사용될 수 있는 파일은 해시 URL을 쓰지 않으므로 1시간 캐시와 재검증을 사용한다.

구성원 사진과 홈 Hero 이미지는 `app/static/images/members/`, `app/static/images/hero/`에 저장된다. 허용 확장자와 최대 업로드 크기(8MiB), 이미지 디코딩 시 최대 2,500만 픽셀, 리사이즈·최적화 동작은 각 관리자 라우터와 `app/services/image_service.py`가 실제 기준이다. 업로드 파일은 저장소에서 관리하지 않으며, 기본 Hero 이미지처럼 추적되는 예외가 있을 수 있다. 파일명과 업로드 경로를 변경할 때는 캐시와 기존 데이터의 URL 호환성을 함께 검토한다.

## 변경 시 참고 문서

개발·마이그레이션 명령은 [development.md](development.md), 운영 서버 절차는 [operations.md](operations.md), 성능 측정과 해석은 [performance.md](performance.md), 프로젝트 소개와 주요 기능는 [README](../README.md), 저장소의 유지보수 기준은 [AGENTS.md](../AGENTS.md)를 기준으로 한다.
