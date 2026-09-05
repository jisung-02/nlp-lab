# Performance check

Measured 2026-09-05 on macOS with the repository `.venv` Python, one local uvicorn worker, sequential standard-library HTTP requests, and temporary SQLite databases. Each database was created with `alembic upgrade head` for the target revision and populated with the same synthetic data (10 or 500 rows, with realistic 1–4 KB text fields). The benchmark made 120 warm requests per scenario (20 per public route), and reported route latency as milliseconds and process RSS as MiB. The historical comparison baseline is commit `acbfc454885319f90d6b6796157266d470c4974e`; the measured implementation was committed as `bfe1b37`.

The complete three-repetition output is in [performance-final.json](performance-final.json). The initial exploratory comparison is in [performance-baseline.json](performance-baseline.json). Values below are arithmetic means of the three repetitions; route medians and p95 values are the benchmark’s per-route statistics.

| Dataset | Revision | `/members` median / p95 | `/projects` median / p95 | `/publications` median / p95 | RSS max |
| --- | --- | ---: | ---: | ---: | ---: |
| 10 rows | working tree | 1.46 / 3.09 ms | 1.44 / 2.33 ms | 1.47 / 4.00 ms | 77.73 MiB |
| 10 rows | `acbfc45` baseline | 1.39 / 2.05 ms | 1.35 / 1.81 ms | 1.41 / 2.16 ms | 78.44 MiB |
| 500 rows | working tree | 10.30 / 24.20 ms | 7.73 / 22.59 ms | 6.85 / 20.56 ms | 88.89 MiB |
| 500 rows | `acbfc45` baseline | 10.07 / 23.39 ms | 8.52 / 22.66 ms | 6.64 / 18.43 ms | 98.56 MiB |

The index and deferred-column changes do not produce a reliable latency win in this small sequential run: the 500-row medians are within run-to-run noise, with `/projects` improving by about 9% and `/publications` worsening by about 3%. The working tree’s lower RSS at 500 rows is consistent with the deferred large text columns, but startup and allocator variation make this a directional observation rather than a memory guarantee. The detail route remained about 1.5 ms median in both revisions. To compare the current checkout against the same baseline, run `uv run python scripts/benchmark.py --compare-head --baseline-ref acbfc45`.

## Image processing check

Using the same generated 6000×4000 JPEG (24 MP) in separate subprocesses, `optimize_image_bytes` produced JPEGs with the same dimensions (1600×1067) and encoded size (10,577 bytes). The working tree completed in 99.2 ms with 70.98 MiB maximum RSS; archived `acbfc45` took 274.7 ms and reached 244.20 MiB RSS. This isolates the optimizer path and is one sample per revision, so it is evidence of the large-image memory improvement rather than a throughput or leak proof.

All results are from a single-worker, sequential localhost workload. They do not represent concurrent throughput, production storage, network latency, or long-term memory behavior.
