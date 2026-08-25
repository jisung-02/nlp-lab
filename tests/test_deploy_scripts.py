from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEPLOY_SCRIPT = ROOT_DIR / "scripts" / "deploy.sh"
ROLLBACK_SCRIPT = ROOT_DIR / "scripts" / "rollback.sh"
BASH_BIN = "/bin/bash"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    path.chmod(0o755)


def _make_project(tmp_path: Path) -> Path:
    """A throwaway copy of the scripts so state files never touch the repo."""

    project = tmp_path / "project"
    (project / "scripts").mkdir(parents=True)
    for name in ("deploy.sh", "rollback.sh", "load_env.sh", "nlp-lab.service.template"):
        (project / "scripts" / name).write_bytes((ROOT_DIR / "scripts" / name).read_bytes())
    _write_executable(
        project / "scripts" / "ensure_https_cert.sh",
        """#!/usr/bin/env bash
        echo "ensure_https_cert" >> "$CALL_LOG"
        """,
    )
    return project


def _install_fakes(tmp_path: Path, *, curl_status: str = "200", uv_fail_on: str = "") -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.log"
    _write_executable(
        bin_dir / "uv",
        f"""#!/usr/bin/env bash
        echo "uv $*" >> "$CALL_LOG"
        if [ -n "{uv_fail_on}" ] && [[ "$*" == *"{uv_fail_on}"* ]]; then exit 1; fi
        if [[ "$*" == *"maintenance backup"* ]]; then echo "/srv/backups/nlp_lab-1.db"; fi
        if [[ "$*" == *"legacy-stamp-revision"* ]]; then echo "${{LEGACY_REVISION:-}}"; fi
        exit 0
        """,
    )
    _write_executable(
        bin_dir / "git",
        """#!/usr/bin/env bash
        echo "git $*" >> "$CALL_LOG"
        case "$1" in
          rev-parse)
            if [ "$2" = "--is-inside-work-tree" ]; then exit 0; fi
            if [ "$2" = "--abbrev-ref" ]; then echo "main"; exit 0; fi
            echo "abc1234"
            ;;
          symbolic-ref) [ "${GIT_DETACHED:-0}" = "1" ] && exit 1 || exit 0 ;;
          status) echo "${GIT_DIRTY:-}" ;;
          log) echo "some commit" ;;
        esac
        exit 0
        """,
    )
    _write_executable(
        bin_dir / "sudo",
        """#!/usr/bin/env bash
        if [ "$1" = "-n" ]; then shift; fi
        if [ "$1" = "true" ]; then exit 0; fi
        echo "sudo $*" >> "$CALL_LOG"
        if [ "$1" = "tee" ]; then cat > /dev/null; fi
        exit 0
        """,
    )
    _write_executable(
        bin_dir / "systemctl",
        """#!/usr/bin/env bash
        echo "systemctl $*" >> "$CALL_LOG"
        exit 0
        """,
    )
    _write_executable(
        bin_dir / "curl",
        f"""#!/usr/bin/env bash
        echo "curl" >> "$CALL_LOG"
        printf "{curl_status}"
        """,
    )
    return log


def _build_env(tmp_path: Path, log: Path, **overrides: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{tmp_path / 'bin'}:{env['PATH']}",
            "CALL_LOG": str(log),
            "APP_ENV": "production",
            "APP_PORT": "443",
            "SYSTEMD_UNIT_DIR": str(tmp_path / "systemd"),
            "RENEWAL_HOOK_DIR": str(tmp_path / "renewal-hooks"),
            "HEALTHCHECK_RETRIES": "1",
        }
    )
    env.update(overrides)
    return env


def _run(script: Path, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [BASH_BIN, str(script)], cwd=cwd, env=env, text=True, capture_output=True, check=False
    )


def _calls(log: Path) -> list[str]:
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def test_deploy_runs_steps_in_safe_order_and_installs_service(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    log = _install_fakes(tmp_path)
    env = _build_env(tmp_path, log)

    result = _run(project / "scripts" / "deploy.sh", project, env)

    assert result.returncode == 0, result.stdout + result.stderr
    calls = _calls(log)
    order = [
        "git pull --ff-only",
        "uv sync",
        "uv run python -m app.db.maintenance backup",
        "uv run python -m app.db.maintenance legacy-stamp-revision",
        "uv run alembic upgrade head",
        "uv run poe init-admin",
        "ensure_https_cert",
        "sudo systemctl daemon-reload",
        "sudo systemctl enable nlp-lab.service",
        "sudo systemctl restart nlp-lab.service",
        "curl",
    ]
    positions = [next(i for i, call in enumerate(calls) if call.startswith(item)) for item in order]
    assert positions == sorted(positions)
    assert "uv run alembic stamp" not in "\n".join(calls)
    assert any(call.startswith("sudo tee") and call.endswith("nlp-lab.service") for call in calls)
    assert (project / ".deploy" / "previous_commit").read_text().strip() == "abc1234"
    assert (project / ".deploy" / "last_backup").read_text().strip() == "/srv/backups/nlp_lab-1.db"
    assert "배포 완료" in result.stdout


def test_deploy_reads_dotenv_values_with_spaces_and_quotes(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    log = _install_fakes(tmp_path)
    env = _build_env(tmp_path, log)
    for key in ("APP_ENV", "APP_PORT"):
        env.pop(key)
    (project / ".env").write_text(
        "# comment\n"
        "APP_ENV=production\n"
        "APP_PORT=8443\n"
        "CONTACT_ADDRESS=Seoul, Republic of Korea\n"
        'SECRET_KEY="quoted value"\n'
        "export APP_DOMAIN=lab.example.test\n",
        encoding="utf-8",
    )

    result = _run(project / "scripts" / "deploy.sh", project, env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "command not found" not in result.stderr
    assert "sudo systemctl restart nlp-lab.service" in _calls(log)


def test_load_env_lets_real_environment_win_over_dotenv(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("APP_PORT=8443\nCONTACT_ADDRESS=Seoul, Republic of Korea\n")
    script = tmp_path / "probe.sh"
    script.write_text(
        f'. "{ROOT_DIR / "scripts" / "load_env.sh"}"\n'
        f'load_dotenv "{tmp_path / ".env"}"\n'
        'printf "%s|%s" "$APP_PORT" "$CONTACT_ADDRESS"\n'
    )

    result = subprocess.run(
        [BASH_BIN, str(script)],
        env={**os.environ, "APP_PORT": "9000"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "9000|Seoul, Republic of Korea"


def test_deploy_stamps_legacy_database_before_upgrading(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    log = _install_fakes(tmp_path)
    env = _build_env(tmp_path, log, LEGACY_REVISION="ce87631b7c22")

    result = _run(project / "scripts" / "deploy.sh", project, env)

    assert result.returncode == 0, result.stdout + result.stderr
    calls = _calls(log)
    stamp_index = calls.index("uv run alembic stamp ce87631b7c22")
    assert stamp_index < calls.index("uv run alembic upgrade head")
    assert calls.index("uv run python -m app.db.maintenance backup") < stamp_index


def test_deploy_skips_service_steps_outside_production(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    log = _install_fakes(tmp_path)
    env = _build_env(tmp_path, log, APP_ENV="development")

    result = _run(project / "scripts" / "deploy.sh", project, env)

    assert result.returncode == 0, result.stdout + result.stderr
    joined = "\n".join(_calls(log))
    assert "uv run alembic upgrade head" in joined
    assert "ensure_https_cert" not in joined
    assert "systemctl" not in joined


def test_deploy_stops_before_touching_database_when_sync_fails(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    log = _install_fakes(tmp_path, uv_fail_on="sync")
    env = _build_env(tmp_path, log)

    result = _run(project / "scripts" / "deploy.sh", project, env)

    assert result.returncode != 0
    joined = "\n".join(_calls(log))
    assert "alembic" not in joined
    assert "systemctl restart" not in joined
    assert "uv run poe rollback" in result.stderr


def test_deploy_refuses_to_pull_over_local_edits(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    log = _install_fakes(tmp_path)
    env = _build_env(tmp_path, log, GIT_DIRTY=" M app/main.py")

    result = _run(project / "scripts" / "deploy.sh", project, env)

    assert result.returncode != 0
    assert "git stash" in result.stderr
    assert "git pull" not in "\n".join(_calls(log))


def test_deploy_explains_detached_head_instead_of_failing_on_pull(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    log = _install_fakes(tmp_path)
    env = _build_env(tmp_path, log, GIT_DETACHED="1")

    result = _run(project / "scripts" / "deploy.sh", project, env)

    assert result.returncode != 0
    assert "git checkout main" in result.stderr
    assert "git pull" not in "\n".join(_calls(log))


def test_deploy_fails_when_healthcheck_does_not_return_200(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    log = _install_fakes(tmp_path, curl_status="502")
    env = _build_env(tmp_path, log)

    result = _run(project / "scripts" / "deploy.sh", project, env)

    assert result.returncode != 0
    assert "journalctl" in result.stderr


def test_rollback_restores_previous_commit_and_backup(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    log = _install_fakes(tmp_path)
    env = _build_env(tmp_path, log)
    (project / ".deploy").mkdir()
    (project / ".deploy" / "previous_commit").write_text("abc1234\n")
    (project / ".deploy" / "branch").write_text("main\n")
    (project / ".deploy" / "last_backup").write_text(str(tmp_path / "backup.db") + "\n")
    (tmp_path / "backup.db").write_bytes(b"")

    result = _run(project / "scripts" / "rollback.sh", project, env)

    assert result.returncode == 0, result.stdout + result.stderr
    calls = _calls(log)
    order = [
        "sudo systemctl stop nlp-lab.service",
        "git checkout --force main",
        "git reset --hard abc1234",
        f"uv run python -m app.db.maintenance restore {tmp_path / 'backup.db'}",
        "uv sync",
        "sudo systemctl start nlp-lab.service",
        "curl",
    ]
    positions = [next(i for i, call in enumerate(calls) if call.startswith(item)) for item in order]
    assert positions == sorted(positions)
    assert "롤백 완료" in result.stdout


def test_rollback_requires_a_previous_deploy(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    log = _install_fakes(tmp_path)
    env = _build_env(tmp_path, log)

    result = _run(project / "scripts" / "rollback.sh", project, env)

    assert result.returncode != 0
    assert "previous_commit" in result.stderr
    assert _calls(log) == []
