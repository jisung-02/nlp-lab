#!/usr/bin/env python3
"""Small repeatable HTTP benchmark for the NLP Lab public pages.

Only the Python standard library is used by the driver.  Each run gets a
temporary SQLite database and server process, so it never touches the local
development database or uploads.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROUTES = ("/", "/members", "/projects", "/publications", "/contact", "/projects/project-0")


def seed_database(path: Path, rows: int) -> None:
    """Insert realistic synthetic rows into an already migrated database."""
    with sqlite3.connect(path) as db:
        # Some repository migrations may provision an initial admin/member row;
        # the benchmark database is disposable, so synthetic data starts clean.
        for table in ("member", "project", "publication", "post", "admin_user"):
            db.execute(f"DELETE FROM {table}")
        now = "2026-01-01 00:00:00"
        bio = "Researches language technology, information retrieval, and machine learning. " * 20
        description = (
            "This project studies robust natural language processing methods "
            "in real-world settings. " * 45
        )
        content = (
            "The lab develops reproducible datasets and evaluation methods for language systems. "
            * 45
        )
        for i in range(rows):
            db.execute(
                "INSERT INTO member (id, name, name_en, role, email, bio, bio_en, "
                "display_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    i + 1,
                    f"Member {i}",
                    f"Member EN {i}",
                    "master",
                    f"member-{i}@example.test",
                    bio,
                    bio,
                    i,
                    now,
                    now,
                ),
            )
            db.execute(
                "INSERT INTO project (id, title, title_en, slug, summary, summary_en, "
                "description, description_en, status, start_date, end_date, created_at, "
                "updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    i + 1,
                    f"Project {i}",
                    f"Project EN {i}",
                    f"project-{i}",
                    "summary",
                    "summary",
                    description,
                    description,
                    "ongoing",
                    "2024-01-01",
                    None,
                    now,
                    now,
                ),
            )
            db.execute(
                "INSERT INTO publication (id, title, title_en, authors, authors_en, venue, "
                "venue_en, year, link, related_project_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    i + 1,
                    f"Publication {i}",
                    f"Publication EN {i}",
                    "Author",
                    "Author",
                    "Venue",
                    "Venue",
                    2026 - (i % 10),
                    "https://example.test",
                    i + 1,
                    now,
                ),
            )
            db.execute(
                "INSERT INTO post (id, title, title_en, slug, content, content_en, "
                "is_published, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (i + 1, f"Post {i}", f"Post EN {i}", f"post-{i}", content, content, now, now),
            )
        db.commit()


def get_rss(pid: int) -> float | None:
    """Return resident memory in MiB; ps reports RSS in KiB on macOS/Linux."""
    try:
        out = subprocess.check_output(["ps", "-o", "rss=", "-p", str(pid)], text=True)
        return int(out.strip()) / 1024
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def request(url: str) -> tuple[int, float]:
    started = time.perf_counter()
    with urllib.request.urlopen(url, timeout=5) as response:
        response.read()
        status = response.status
    return status, (time.perf_counter() - started) * 1000


def run_target(target: Path, rows: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="nlp-lab-bench-") as temp:
        database = Path(temp) / "bench.sqlite3"
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        env = os.environ.copy()
        env.update(
            {
                "DATABASE_URL": f"sqlite:///{database}",
                "APP_ENV": "production",
                "SECRET_KEY": "benchmark-secret-key-0123456789abcdef",
                "ADMIN_PASSWORD": "benchmark-password-012345",
                "PYTHONPATH": str(target),
            }
        )
        migration = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=target,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if migration.returncode:
            raise RuntimeError(f"alembic upgrade failed:\n{migration.stdout}\n{migration.stderr}")
        seed_database(database, rows)
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "error",
            ],
            cwd=target,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        base = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + 10
            while True:
                try:
                    request(base + "/")
                    break
                except (OSError, urllib.error.URLError):
                    if time.monotonic() > deadline:
                        proc.terminate()
                        _, stderr = proc.communicate(timeout=3)
                        raise RuntimeError(stderr) from None
                    time.sleep(0.03)
            for route in ROUTES:
                request(base + route)
            samples: dict[str, list[float]] = {route: [] for route in ROUTES}
            rss: list[float] = []
            # 20 requests per route = 120 warm requests, sampling RSS each pass.
            for _ in range(20):
                for route in ROUTES:
                    status, elapsed = request(base + route)
                    if status != 200:
                        raise RuntimeError(f"{route}: HTTP {status}")
                    samples[route].append(elapsed)
                value = get_rss(proc.pid)
                if value is not None:
                    rss.append(value)
            latency = {
                route: {
                    "median_ms": round(statistics.median(values), 3),
                    "p95_ms": round(sorted(values)[-max(1, (len(values) + 19) // 20)], 3),
                }
                for route, values in samples.items()
            }
            return {
                "rows": rows,
                "latency": latency,
                "rss_mib_min": round(min(rss), 2),
                "rss_mib_max": round(max(rss), 2),
                "rss_mib_delta": round(max(rss) - min(rss), 2),
                "requests": len(ROUTES) * 20,
            }
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=Path.cwd())
    parser.add_argument("--rows", type=int, nargs="+", default=[10, 500])
    parser.add_argument(
        "--compare-head", action="store_true", help="also benchmark a temporary git archive of HEAD"
    )
    parser.add_argument(
        "--baseline-ref",
        default="HEAD",
        help="commit/ref to compare against when --compare-head is set",
    )
    parser.add_argument("--json-out", type=Path, help="write benchmark results to this JSON file")
    args = parser.parse_args()
    targets = [("working-tree", args.target.resolve())]
    with tempfile.TemporaryDirectory(prefix="nlp-lab-head-") as archive_dir:
        if args.compare_head:
            baseline_commit = subprocess.check_output(
                [
                    "git",
                    "rev-parse",
                    "--verify",
                    "--end-of-options",
                    f"{args.baseline_ref}^{{commit}}",
                ],
                cwd=args.target,
                text=True,
            ).strip()
            archive = Path(archive_dir) / "head.tar"
            subprocess.run(
                ["git", "archive", "--format=tar", baseline_commit, "-o", str(archive)],
                cwd=args.target,
                check=True,
            )
            head = Path(archive_dir) / "src"
            head.mkdir()
            subprocess.run(["tar", "-xf", str(archive), "-C", str(head)], check=True)
            targets.append((f"baseline:{baseline_commit}", head))
        results = {name: [run_target(path, rows) for rows in args.rows] for name, path in targets}
        rendered = json.dumps(results, indent=2) + "\n"
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(rendered)
        print(rendered, end="")


if __name__ == "__main__":
    main()
