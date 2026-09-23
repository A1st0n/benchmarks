# benchmarks

Measured stats across my GitHub repos. Raw numbers in [`results.json`](results.json); reproduce with [`bench.py`](bench.py).

Run 2026-09-22 · Intel Mac (Darwin 24.6.0 x86_64) · Python 3.14 · Node 24.
API latencies are in-process (Flask test client, SQLite), so they measure handler + DB time and leave out network time.

## Totals

| Repos | Commits | Lines of code* | JavaScript | Python | CSS | C++ | HTML | SQL |
|---|---|---|---|---|---|---|---|---|
| 11 | 81 | **16,279** | 6,121 | 3,559 | 3,217 | 2,421 | 721 | 240 |

\*Non-blank lines in tracked source files. Excludes `node_modules`, build output (`dist/`), minified files, and duplicated code. Forks and scratch repos are not counted.

## Per project

### Grocery-ML: weight-based grocery classifier + RISC-V CPU simulator
| Metric | Result |
|---|---|
| Test accuracy (10 classes, 2,078 real items) | **37.0%** vs 10% random, a **3.7× lift** |
| `predict()` single-item latency | p50 **1.29 ms**, p99 1.91 ms (~760 predictions/s) |
| Batch inference (XGBoost) | **~80,700 rows/s** (10k rows in 0.12 s) |
| RISC-V sim (C++), 6-instruction program | 6 cycles single-cycle / 16 cycles pipelined (5-stage) |
| Code | 8,136 LOC: Python 2,650 · C++ 2,421 · JS 1,550 |

### betting-dashboard: Flask + Socket.IO live props, automatic settlement
| Metric | Result |
|---|---|
| Settlement correctness test (money path) | ✅ pass |
| Bet settlement throughput | **~25,000 bets/s** (5,020 bets in 0.20 s) |
| `POST /api/bet` (write) | p50 5.9 ms · p95 10.8 ms |
| `GET /api/me` | p50 **0.80 ms** · p95 1.03 ms (~1,200 req/s) |
| `GET /api/mybets` (5k+ bets history) | p50 12.2 ms |

### course-enrollment-system: React 19 + Flask REST API, JWT role-based auth
| Metric | Result |
|---|---|
| REST endpoints | 20 (student / teacher / admin) |
| RBAC: student blocked from all admin routes | ✅ verified |
| `GET /api/me` (JWT decode + lookup) | p50 **0.75 ms** · p95 0.98 ms (~1,270 req/s) |
| Role-scoped reads (my-courses, teacher, admin) | p50 **3.1–3.7 ms** · p95 < 4.5 ms |
| Login | p50 210 ms. The delay is deliberate: salted password hashing slows brute-force attempts |

### patreon-clone: Next.js 14 + Supabase + Stripe
| Metric | Result |
|---|---|
| Unit tests (tier gating, pricing, MRR, sessions) | **6/6 pass** in 0.3 s |
| Surface | 11 pages · 4 API routes (checkout, webhook, membership, notify) |
| Code | 2,924 LOC |

### Smaller repos
| Repo | Commits | LOC |
|---|---|---|
| html-practice | 2 | 1,205 |
| portfolio | 2 | 219 |
| tpch (SQL schema) | 3 | 77 |
| DermBuddy | 2 | 26 |

## Resume-ready bullets

- Built a Flask/Socket.IO sports-betting dashboard with automatic bet settlement that processes **~25k bets/s**. It serves authenticated reads in **<1 ms p50**, and a test covers the money path.
- Built a full-stack course enrollment platform (React 19, Flask, SQLAlchemy, Docker) with **20 REST endpoints** and JWT role-based access control. Role-scoped queries return in **<4.5 ms p95**.
- Trained an XGBoost classifier on 2,078 real grocery items. It reaches **3.7× the random-baseline accuracy**, predicts one item in **~1.3 ms**, and runs batches at **80k rows/s**. It connects to an Arduino load cell over serial.
- Wrote a RISC-V CPU simulator in C++ with single-cycle and 5-stage pipelined modes, including a control unit and JAL/JALR support.
- Shipped a Next.js 14 creator-subscription platform with Supabase auth and Stripe billing. Unit tests cover tier gating and MRR.
- **16k+ lines of code** across JavaScript, Python, C++, and SQL.

## Reproduce

```bash
pip install flask flask-sqlalchemy flask-socketio simple-websocket requests PyJWT joblib numpy xgboost scikit-learn
python bench.py path/to/dir-of-clones
```
