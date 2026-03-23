from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ENSURE_SCRIPT = ROOT_DIR / "scripts" / "ensure_https_cert.sh"
SERVE_SCRIPT = ROOT_DIR / "scripts" / "serve_https.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    path.chmod(0o755)


def _run_script(script: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script)],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _build_env(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "APP_DOMAIN": "lab.example.test",
            "TLS_ADMIN_EMAIL": "admin@example.com",
            "APP_ENV": "production",
            "APP_HOST": "0.0.0.0",
            "APP_PORT": "443",
            "LETSENCRYPT_LIVE_DIR": str(tmp_path / "letsencrypt" / "live"),
            "CERTBOT_BIN": "certbot",
        }
    )
    return env


def _create_valid_certificate(cert_path: Path, key_path: Path) -> None:
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-nodes",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-days",
            "365",
            "-subj",
            "/CN=lab.example.test",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_ensure_https_cert_requires_domain_and_email(tmp_path: Path) -> None:
    env = _build_env(tmp_path)
    del env["APP_DOMAIN"]
    del env["TLS_ADMIN_EMAIL"]

    result = _run_script(ENSURE_SCRIPT, env)

    assert result.returncode != 0
    assert "Missing required environment variable: APP_DOMAIN" in result.stderr


def test_ensure_https_cert_skips_certbot_when_existing_certificate_is_valid(tmp_path: Path) -> None:
    env = _build_env(tmp_path)
    cert_dir = Path(env["LETSENCRYPT_LIVE_DIR"]) / env["APP_DOMAIN"]
    cert_path = cert_dir / "fullchain.pem"
    key_path = cert_dir / "privkey.pem"
    _create_valid_certificate(cert_path, key_path)

    log_path = tmp_path / "certbot.log"
    _write_executable(
        tmp_path / "bin" / "certbot",
        f"""#!/usr/bin/env bash
        echo "certbot-called" >> "{log_path}"
        exit 0
        """,
    )

    result = _run_script(ENSURE_SCRIPT, env)

    assert result.returncode == 0
    assert "Using existing TLS certificate" in result.stdout
    assert not log_path.exists()


def test_ensure_https_cert_requests_certificate_when_missing(tmp_path: Path) -> None:
    env = _build_env(tmp_path)
    cert_dir = Path(env["LETSENCRYPT_LIVE_DIR"]) / env["APP_DOMAIN"]
    cert_path = cert_dir / "fullchain.pem"
    key_path = cert_dir / "privkey.pem"
    log_path = tmp_path / "certbot.log"

    _write_executable(
        tmp_path / "bin" / "certbot",
        f"""#!/usr/bin/env bash
        echo "$@" > "{log_path}"
        mkdir -p "{cert_dir}"
        printf 'fake-cert' > "{cert_path}"
        printf 'fake-key' > "{key_path}"
        """,
    )

    result = _run_script(ENSURE_SCRIPT, env)

    assert result.returncode == 0
    assert "TLS certificate is ready" in result.stdout
    assert cert_path.read_text(encoding="utf-8") == "fake-cert"
    assert "--keep-until-expiring" in log_path.read_text(encoding="utf-8")


def test_ensure_https_cert_bootstraps_certbot_on_ubuntu(tmp_path: Path) -> None:
    env = _build_env(tmp_path)
    cert_dir = Path(env["LETSENCRYPT_LIVE_DIR"]) / env["APP_DOMAIN"]
    cert_path = cert_dir / "fullchain.pem"
    key_path = cert_dir / "privkey.pem"
    log_path = tmp_path / "bootstrap.log"
    os_release_path = tmp_path / "os-release"
    snap_certbot_bin = tmp_path / "snap" / "bin" / "certbot"
    local_certbot_link = tmp_path / "usr" / "local" / "bin" / "certbot"

    os_release_path.write_text('ID="ubuntu"\n', encoding="utf-8")
    env.update(
        {
            "OS_RELEASE_FILE": str(os_release_path),
            "SNAP_CERTBOT_BIN": str(snap_certbot_bin),
            "LOCAL_CERTBOT_LINK": str(local_certbot_link),
        }
    )

    _write_executable(
        tmp_path / "bin" / "sudo",
        """#!/usr/bin/env bash
        if [ "$1" = "-n" ] && [ "$2" = "true" ]; then
          exit 0
        fi
        "$@"
        """,
    )
    _write_executable(
        tmp_path / "bin" / "apt-get",
        f"""#!/usr/bin/env bash
        echo "apt-get $@" >> "{log_path}"
        """,
    )
    _write_executable(
        tmp_path / "bin" / "snap",
        f"""#!/usr/bin/env bash
        echo "snap $@" >> "{log_path}"
        if [ "$1" = "install" ] && [ "$2" = "--classic" ] && [ "$3" = "certbot" ]; then
          mkdir -p "{snap_certbot_bin.parent}"
          cat > "{snap_certbot_bin}" <<'EOF'
#!/usr/bin/env bash
echo "certbot $@" >> "{log_path}"
mkdir -p "{cert_dir}"
printf 'fake-cert' > "{cert_path}"
printf 'fake-key' > "{key_path}"
EOF
          chmod +x "{snap_certbot_bin}"
        fi
        """,
    )

    result = _run_script(ENSURE_SCRIPT, env)

    assert result.returncode == 0
    assert cert_path.read_text(encoding="utf-8") == "fake-cert"
    bootstrap_log = log_path.read_text(encoding="utf-8")
    assert "snap install --classic certbot" in bootstrap_log
    assert "certbot certonly --standalone" in bootstrap_log


def test_ensure_https_cert_reports_missing_privileges_for_ubuntu_bootstrap(tmp_path: Path) -> None:
    env = _build_env(tmp_path)
    os_release_path = tmp_path / "os-release"
    os_release_path.write_text('ID="ubuntu"\n', encoding="utf-8")
    env["OS_RELEASE_FILE"] = str(os_release_path)
    env["CERTBOT_BIN"] = "missing-certbot"

    result = _run_script(ENSURE_SCRIPT, env)

    assert result.returncode != 0
    assert "automatic Ubuntu installation requires root or passwordless sudo" in result.stderr


def test_serve_https_requires_production_env(tmp_path: Path) -> None:
    env = _build_env(tmp_path)
    env["APP_ENV"] = "development"
    _write_executable(
        tmp_path / "bin" / "certbot",
        """#!/usr/bin/env bash
        exit 0
        """,
    )

    result = _run_script(SERVE_SCRIPT, env)

    assert result.returncode != 0
    assert "APP_ENV must be set to production" in result.stderr


def test_serve_https_starts_uvicorn_with_tls_paths(tmp_path: Path) -> None:
    env = _build_env(tmp_path)
    cert_dir = Path(env["LETSENCRYPT_LIVE_DIR"]) / env["APP_DOMAIN"]
    cert_path = cert_dir / "fullchain.pem"
    key_path = cert_dir / "privkey.pem"
    _create_valid_certificate(cert_path, key_path)

    uv_log_path = tmp_path / "uv.log"
    _write_executable(
        tmp_path / "bin" / "certbot",
        """#!/usr/bin/env bash
        exit 0
        """,
    )
    _write_executable(
        tmp_path / "bin" / "uv",
        f"""#!/usr/bin/env bash
        echo "$@" > "{uv_log_path}"
        exit 0
        """,
    )

    result = _run_script(SERVE_SCRIPT, env)

    assert result.returncode == 0
    uv_args = uv_log_path.read_text(encoding="utf-8")
    assert "run uvicorn app.main:app" in uv_args
    assert f"--ssl-certfile {cert_path}" in uv_args
    assert f"--ssl-keyfile {key_path}" in uv_args
    assert "--host 0.0.0.0" in uv_args
    assert "--port 443" in uv_args
