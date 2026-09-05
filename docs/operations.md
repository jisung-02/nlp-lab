# 운영 가이드

이 문서는 `nlp.khu.ac.kr` 운영 서버를 배포하고, 백업·롤백·HTTPS·서비스 상태를 확인하는 절차를 설명합니다. 웹 개발 지식이 없어도 정기 운영을 수행할 수 있도록 평소 사용하는 명령을 앞에 두었습니다. 코드나 DB 구조를 바꿔야 하는 경우에는 현재 상태와 오류 로그를 보존해 개발자에게 전달하세요.

사이트와 기능 소개는 [README](../README.md), 개발 환경과 품질 검사는 [개발 환경과 명령어](development.md), 구조와 운영 경계는 [구조와 유지보수 기준](architecture.md)를 참고합니다.

## 평소 사용하는 명령

운영 서버의 프로젝트 디렉터리에서 실행합니다. 아래 `/srv/nlp-lab`은 설치 위치의 예시이며, 실제 서버의 프로젝트 경로로 바꿔야 합니다.

```bash
cd /srv/nlp-lab
```

필요한 작업에 해당하는 명령을 실행합니다.

| 작업 | 명령 |
| --- | --- |
| 업데이트·백업·마이그레이션·재시작·상태 확인 | `uv run poe deploy` |
| 마지막 배포 직전 코드와 DB로 복원 | `uv run poe rollback` |
| SQLite DB만 백업 | `uv run poe backup-db` |

개발 또는 점검 환경에서는 다음을 사용합니다.

```bash
uv run poe serve         # 백업 → 최신 마이그레이션 → 초기 관리자 확인 → 개발 서버
uv run poe check         # lint + typecheck + test
```

`serve`는 시작 전에 DB 백업과 마이그레이션을 수행합니다. 반면 `uv run poe serve-https`는 운영용 인증서를 확인한 뒤 HTTPS Uvicorn을 실행하는 명령이며 DB 마이그레이션을 자동 적용하지 않습니다. 직접 실행하거나 systemd를 재시작하기 전에 필요한 마이그레이션을 별도로 적용하세요.

```bash
uv run alembic upgrade head
uv run poe serve-https
```

## 배포

운영 서버에서 다음 한 줄을 실행하면 `scripts/deploy.sh`가 아래 순서로 처리합니다.

```bash
uv run poe deploy
```

1. Git 브랜치와 working tree를 확인합니다. 서버에서 직접 수정한 추적 파일이 있거나 detached HEAD이면 중단합니다.
2. **pull 전에** SQLite 온라인 백업을 만들고 `.deploy/rollback-state`에 배포 직전 커밋, 브랜치, 백업 경로를 원자적으로 기록합니다. 파일 기반 SQLite가 아니면 DB 백업은 별도 절차가 필요합니다.
3. `git pull --ff-only`와 `uv sync --locked`를 실행합니다.
4. `alembic upgrade head`를 실행합니다. Alembic 이력이 없는 기존 DB는 알려진 스키마와 일치할 때만 해당 revision을 표시한 뒤 진행하며, 인식하지 못하면 중단합니다. 마이그레이션은 테이블·컬럼·인덱스를 추가할 수 있고, 이후 삭제 작업이 포함될 수도 있으므로 적용 내용을 검토해야 합니다.
5. 설정한 사용자명의 초기 관리자 계정이 없으면 생성하고, 있으면 유지합니다.
6. `APP_ENV=production`일 때 HTTPS 인증서를 확인합니다. 인증서가 없거나 30일 이내 만료 예정이면 Certbot으로 발급·갱신합니다.
7. systemd 유닛이 없으면 설치하고 enable한 뒤 서비스를 재시작합니다.
8. `https://127.0.0.1:<APP_PORT>/`에 최대 30회(요청별 최대 5초, 1초 간격) 요청해 HTTP 200을 확인합니다.

어느 단계에서든 실패하면 스크립트는 즉시 멈춥니다. 출력된 실패 단계와 오류를 확인하고, 복원이 필요하면 `uv run poe rollback`을 사용합니다. 배포 전 상태를 확인하고 백업하는 이유는 코드와 DB를 같은 롤백 지점으로 맞추기 위해서입니다.

최초 설치 또는 기존 서버에 처음 적용할 때에는 프로젝트 경로, `.env`, DNS, 방화벽, Certbot 준비를 먼저 확인합니다. 예시:

```bash
cd /srv/nlp-lab
uv run poe deploy
```

필수 운영 설정은 다음과 같습니다.

```dotenv
APP_ENV=production
APP_DEBUG=false
APP_HOST=0.0.0.0
APP_PORT=443
APP_DOMAIN=nlp.khu.ac.kr
TLS_ADMIN_EMAIL=<인증서 만료 알림을 받을 주소>
SECRET_KEY=<32자 이상 무작위 비밀값>
ADMIN_PASSWORD=<고유한 운영 관리자 비밀번호>
```

`SECRET_KEY`와 `ADMIN_PASSWORD`는 예시값을 그대로 사용하지 않습니다. 무작위 키는 다음처럼 생성할 수 있습니다.

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

로컬 DB `nlp_lab.db`와 업로드 이미지(`app/static/images/hero/*`, `members/`)는 Git이 관리하지 않습니다. 기본 이미지 `app/static/images/hero/hero.jpg`는 저장소에 추적되는 예외입니다. 따라서 `git pull`이 업로드 이미지를 다른 파일로 덮어쓰지는 않지만, DB와 업로드 파일은 별도 백업 대상입니다.

## 백업과 롤백

`backup-db`는 SQLite 온라인 백업 API로 일관된 복사본을 만들고 `backups/`에 최근 10개를 남깁니다.

```bash
uv run poe backup-db
```

`deploy`가 남기는 `.deploy/rollback-state`에는 직전 커밋, 브랜치, 배포 전 DB 백업 경로가 들어 있습니다. 롤백은 이 기록을 사용합니다.

```bash
uv run poe rollback
```

롤백 순서는 서비스 정지, 배포 직전 브랜치와 커밋으로 복원, 백업 DB 복원, `uv sync`, 서비스 시작, HTTPS 상태 확인입니다. DB를 복원하기 전 현재 DB도 `backups/`에 `pre-rollback` 이름으로 보관합니다. 롤백 기록이 없거나 기록에 지정된 백업 파일이 사라졌으면 중단합니다. 배포 당시 백업 대상 DB가 없어 백업 경로가 비어 있었다면 코드만 복원하고 DB는 변경하지 않습니다.

롤백 후 다음 배포에서 최신 코드로 다시 올라갑니다. 롤백 중 문제가 생기면 자동으로 재시도하지 말고 출력된 오류, `git status`, 서비스 로그를 개발자에게 전달하세요. `rollback`은 production이 아니거나 systemd가 없는 환경에서는 서비스 정지·시작을 건너뛰고 코드와 DB 복원까지만 수행합니다.

## HTTPS와 DNS

운영 도메인은 `nlp.khu.ac.kr`입니다. 인증서 발급 전 다음 조건을 확인합니다.

- DNS `A` 레코드가 `nlp.khu.ac.kr`을 서버 공인 IP로 가리켜야 합니다.
- 외부에서 TCP 80과 443 포트에 접근할 수 있어야 합니다.
- Let’s Encrypt HTTP-01 검증을 위해 TCP 80 포트가 특히 필요합니다.
- Ubuntu에서 `certbot`이 없으면 스크립트가 root 또는 비밀번호 없는 sudo로 `snapd`와 Certbot을 bootstrap할 수 있습니다. Ubuntu 이외 환경에서는 Certbot을 미리 설치해야 합니다.

인증서는 저장소가 아닌 `/etc/letsencrypt/live/nlp.khu.ac.kr/`에 저장되며 `fullchain.pem`과 `privkey.pem`을 사용합니다. 개인 키는 서비스 실행 사용자와 인증서 갱신 작업이 읽을 수 있어야 하지만, 일반 사용자에게 읽기 권한을 넓히거나 인증서 디렉터리의 권한을 일괄 변경하지 마세요. `ensure_https_cert.sh`가 파일을 읽지 못하면 인증서 파일과 상위 디렉터리의 소유자·권한을 root 권한으로 점검합니다.

유효한 인증서가 있으면 재발급하지 않고, 만료 30일 이내인 경우에만 `certbot certonly --standalone --keep-until-expiring`으로 갱신합니다. 갱신 중에는 HTTP-01 검증을 위해 80 포트를 사용할 수 있어야 합니다.

```bash
sudo certbot renew --dry-run
```

`deploy`는 갱신 후 서비스 재시작 훅을 `/etc/letsencrypt/renewal-hooks/deploy/` 아래에 설치합니다. 훅과 systemd 유닛을 만들거나 재시작하려면 root 또는 비밀번호 없는 sudo가 필요합니다. Certbot 최초 설치와 인증서 bootstrap은 제한된 systemd 권한만으로 충분하지 않으며 별도 관리자 권한이 필요합니다.

## systemd 서비스

`deploy`가 설치하는 유닛 이름은 기본적으로 `nlp-lab.service`입니다. `NLP_LAB_SERVICE`로 변경할 수 있습니다. 유닛은 저장소의 [서비스 템플릿](../scripts/nlp-lab.service.template)을 바탕으로 프로젝트 경로와 실행 사용자를 채워 만들며, `serve-https`를 실행합니다.

```bash
sudo systemctl status nlp-lab.service
sudo systemctl restart nlp-lab.service
sudo journalctl -u nlp-lab -n 50 --no-pager
```

수동 설치가 필요할 때의 예시 경로는 `/etc/systemd/system/nlp-lab.service`이며, 프로젝트 경로 `/srv/nlp-lab`은 예시입니다. 실제 경로와 서비스 실행 사용자를 서버 설정에 맞춰야 합니다. 서비스 사용자는 프로젝트와 `.env`를 읽고 인증서의 공개 체인과 개인 키를 읽을 수 있어야 합니다. 이를 위해 파일을 누구나 읽을 수 있게 만들지 말고, root가 관리하는 인증서 권한과 서비스 사용자 그룹 구성을 점검합니다.

배포 스크립트가 systemd 유닛을 새로 설치하면 `daemon-reload`와 `enable`을 수행합니다. 이미 유닛이 있으면 내용을 덮어쓰지 않고 재시작합니다.

## 권한과 제한된 sudo

서비스 재시작과 갱신 훅 관리는 root 또는 비밀번호 없는 sudo가 필요합니다. 일반 배포 계정에 권한을 위임해야 한다면 운영자가 실제 설치 경로와 정책을 검토한 뒤 systemd 관련 명령에만 제한적으로 부여합니다. 프로젝트의 기본 흐름은 `systemctl`, `tee`, `mkdir`, `chmod`를 사용합니다. Certbot 설치·bootstrap 권한까지 같은 규칙에 포함시키지 마세요.

## 문제 확인

배포가 실패하면 먼저 화면의 실패 단계와 마지막 오류를 보존합니다.

```bash
git status
sudo systemctl status nlp-lab.service
sudo journalctl -u nlp-lab -n 50 --no-pager
```

다음 항목을 순서대로 확인합니다.

- Git 상태 오류: 서버에서 직접 수정한 추적 파일이나 detached HEAD를 정리한 뒤 다시 배포합니다. 무엇을 지울지 모르면 임의로 `reset`하지 않습니다.
- DB 단계 오류: 백업 파일과 마이그레이션 오류를 보존합니다. 스키마를 수동으로 고치지 말고 개발자 검토를 받습니다.
- 인증서 오류: `APP_DOMAIN=nlp.khu.ac.kr`, `TLS_ADMIN_EMAIL`, DNS, 80/443 방화벽, Certbot 권한을 확인합니다.
- 서비스 재시작 오류: systemd 상태와 journal을 확인하고, 필요하면 `uv run poe rollback`을 사용합니다.
- 상태 확인 오류: `APP_PORT`, 인증서 경로, 서비스 로그를 확인합니다. 배포 스크립트의 내부 health check는 로컬 `https://127.0.0.1:<APP_PORT>/`에 `curl -k`로 요청합니다.

앱이 정상 응답하지 않는 동안 반복 배포하지 말고, 배포 직전 커밋·DB 백업·로그를 함께 보관해 전달하세요. 비밀번호 변경 후에는 기존 관리자 세션이 무효화되므로 관리자가 다시 로그인해야 합니다.

## 운영자가 임의로 하지 않는 변경

모델·스키마 변경에는 Alembic migration이 필요합니다. 라우트, 인증, 보안 설정, systemd 유닛, 인증서 권한, 업로드 파일 보존 정책을 직접 바꾸지 말고 개발자에게 요청하세요. 단순 콘텐츠 편집은 관리자 화면에서 처리할 수 있지만, 삭제는 hard delete이므로 삭제 전 내용을 확인합니다.
