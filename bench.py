"""Benchmark every repo in a directory of clones. Writes results.json.

Usage: python bench.py <repos_dir>
Needs: flask flask-sqlalchemy flask-socketio PyJWT requests joblib numpy xgboost scikit-learn, g++, node.
"""
import json, os, pathlib, statistics, subprocess, sys, tempfile, time

EXT = {".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
       ".ts": "TypeScript", ".tsx": "TypeScript", ".html": "HTML", ".css": "CSS",
       ".cpp": "C++", ".h": "C++", ".ino": "C++", ".sql": "SQL"}
SKIP = ("node_modules", "dist/", "extracted/", ".min.")  # vendored, built, or duplicated code


def sh(cmd, cwd=None, **kw):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, **kw)


def pct(xs, p):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(len(xs) * p))], 3)


def timed(fn, n):
    """Run fn n times (after 20 warmups); return latency stats in ms."""
    for _ in range(20):
        fn()
    ts = []
    for _ in range(n):
        t = time.perf_counter(); fn(); ts.append((time.perf_counter() - t) * 1000)
    return {"n": n, "p50_ms": pct(ts, .5), "p95_ms": pct(ts, .95), "p99_ms": pct(ts, .99),
            "mean_ms": round(statistics.mean(ts), 3), "ops_per_s": round(1000 / statistics.mean(ts))}


def repo_stats(d):
    files = sh(["git", "ls-files"], d).stdout.split()
    loc = {}
    for f in files:
        lang = EXT.get(pathlib.Path(f).suffix)
        if not lang or any(s in f for s in SKIP):
            continue
        try:
            n = sum(1 for l in open(d / f, errors="ignore") if l.strip())
        except OSError:
            continue
        loc[lang] = loc.get(lang, 0) + n
    dates = sh(["git", "log", "--format=%as"], d).stdout.split()
    return {"commits": len(dates), "first_commit": dates[-1] if dates else None,
            "last_commit": dates[0] if dates else None, "tracked_files": len(files),
            "loc": dict(sorted(loc.items(), key=lambda kv: -kv[1])), "loc_total": sum(loc.values())}


# --- per-repo benchmarks. Each runs in a subprocess (both Flask apps are named app.py).

def bench_course(root):
    sys.path.insert(0, str(root / "backend")); os.chdir(root / "backend")
    import app as m
    c = m.app.test_client()
    tok = {}
    for u, p in [("admin", "admin123"), ("cnorris", "student123"), ("ahepworth", "teacher123")]:
        tok[u] = {"Authorization": "Bearer " + c.post("/api/login", json={"username": u, "password": p}).get_json()["token"]}
    login = lambda: c.post("/api/login", json={"username": "cnorris", "password": "student123"})
    assert login().status_code == 200
    # RBAC check: a student must be rejected from admin endpoints
    rbac = [c.get(p, headers=tok["cnorris"]).status_code for p in ("/api/admin/users", "/api/admin/courses", "/api/admin/enrollments")]
    return {
        "endpoints": 20,
        "rbac_student_blocked_from_admin": all(s in (401, 403) for s in rbac),
        "login (password hash verify + JWT)": timed(login, 50),
        "GET /api/me (JWT decode)": timed(lambda: c.get("/api/me", headers=tok["cnorris"]), 1000),
        "GET /api/student/my-courses": timed(lambda: c.get("/api/student/my-courses", headers=tok["cnorris"]), 1000),
        "GET /api/admin/enrollments": timed(lambda: c.get("/api/admin/enrollments", headers=tok["admin"]), 1000),
        "GET /api/teacher/courses": timed(lambda: c.get("/api/teacher/courses", headers=tok["ahepworth"]), 1000),
    }


def bench_betting(root):
    os.environ["APP_DB"] = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    sys.path.insert(0, str(root)); os.chdir(root)
    t = time.perf_counter()
    tests = sh([sys.executable, "test_settle.py"], root)
    test_ms = round((time.perf_counter() - t) * 1000)
    import app as m
    m.app.config["TESTING"] = True
    c = m.app.test_client()
    with m.app.app_context():
        m.ensure_schema()
    c.post("/api/signup", json={"username": "bench", "password": "p"})
    c.post("/api/deposit", json={"amount": 1e9})
    bet = lambda: c.post("/api/bet", json={"team": "Brazil", "amount": 1, "odds": 2.0})
    out = {"settlement_test": "pass" if tests.returncode == 0 else "FAIL", "settlement_test_ms": test_ms,
           "POST /api/bet (write)": timed(bet, 1000),
           "GET /api/me": timed(lambda: c.get("/api/me"), 1000),
           "GET /api/mybets (1k+ bets)": timed(lambda: c.get("/api/mybets"), 200)}
    # settlement throughput: settle every open bet in one pass
    for _ in range(4000):
        bet()
    with m.app.app_context():
        n_open = m.Bet.query.filter_by(status="pending").count()
    m.GAMES = [{"id": "1", "home_team": "Brazil", "away_team": "Serbia", "completed": True,
                "commence_time": "2999-01-01T00:00:00Z",
                "scores": [{"name": "Brazil", "score": "2"}, {"name": "Serbia", "score": "0"}]}]
    with m.app.app_context():
        t = time.perf_counter(); m.settle_bets(); dt = time.perf_counter() - t
    out["settle_bets"] = {"bets": n_open, "seconds": round(dt, 3), "bets_per_s": round(n_open / dt)}
    return out


def bench_grocery(root):
    sys.path.insert(0, str(root)); os.chdir(root)
    import predict as p
    import numpy as np
    exp = json.load(open("experiments.json"))["summary"]
    X = np.random.default_rng(0).random((10000, 3), dtype=np.float32)
    t = time.perf_counter(); p._model.predict_proba(X); batch = time.perf_counter() - t
    out = {"test_accuracy_pct": exp["best_overall_acc"], "random_baseline_pct": exp["random_baseline"],
           "lift_over_baseline_x": round(exp["best_overall_acc"] / exp["random_baseline"], 1),
           "dataset_rows": exp["n_total"], "classes": exp["n_categories"],
           "predict() single-item latency": timed(lambda: p.predict(450, is_liquid=True), 2000),
           "batch inference": {"rows": len(X), "seconds": round(batch, 4), "rows_per_s": round(len(X) / batch)}}
    # RISC-V CPU simulator (C++): compile and time both sample programs, both modes
    exe = pathlib.Path(tempfile.mkdtemp()) / "sim"
    r = sh(["g++", "-std=c++17", "-O2", "Alston-Bravo.cpp", "-o", str(exe)])
    if r.returncode == 0:
        sim = {}
        for prog in ("sample_part1.txt", "sample_part2.txt"):
            for mode, name in (("1", "single-cycle"), ("2", "pipelined")):
                run = lambda: sh([str(exe)], input=f"{mode}\n{prog}\n")
                res = run()
                cycles = [l for l in res.stdout.splitlines() if "total execution time" in l]
                sim[f"{prog} {name}"] = {"cycles": cycles[0].split()[-2] if cycles else None,
                                         "wall_ms_p50": timed(run, 30)["p50_ms"]}
        out["riscv_simulator"] = sim
    return out


def bench_patreon(root):
    if not (root / "node_modules").exists():
        sh(["npm", "install", "--ignore-scripts", "--no-audit", "--no-fund"], root)
    t = time.perf_counter()
    r = sh(["node", "--test", *map(str, root.glob("lib/*.test.mjs"))], root)
    ms = round((time.perf_counter() - t) * 1000)
    get = lambda k: next((int(l.split()[-1]) for l in r.stdout.splitlines() if l.lstrip("ℹ# ").startswith(f"{k} ")), None)
    return {"unit_tests_pass": get("pass"), "unit_tests_fail": get("fail"), "suite_ms": ms,
            "api_routes": len(list((root / "app/api").glob("*/route.js"))),
            "pages": len(list((root / "app").glob("**/page.jsx")))}


BENCH = {"course-enrollment-system": bench_course, "betting-dashboard": bench_betting,
         "Grocery-ML": bench_grocery, "patreon-clone": bench_patreon}


if __name__ == "__main__":
    if sys.argv[1] == "--one":  # child process: run one repo's bench, print JSON
        root = pathlib.Path(sys.argv[3]).resolve()
        out = BENCH[sys.argv[2]](root)
        print("@@" + json.dumps(out))
        sys.exit()
    repos = pathlib.Path(sys.argv[1]).resolve()
    results = {"generated": time.strftime("%Y-%m-%d"), "machine": sh(["uname", "-msr"]).stdout.strip(),
               "python": sys.version.split()[0], "repos": {}}
    for d in sorted(p for p in repos.iterdir() if (p / ".git").exists()):
        print("==", d.name, flush=True)
        entry = repo_stats(d)
        if d.name in BENCH:
            r = sh([sys.executable, __file__, "--one", d.name, str(d)], timeout=900)
            line = next((l for l in r.stdout.splitlines() if l.startswith("@@")), None)
            entry["bench"] = json.loads(line[2:]) if line else {"error": r.stderr[-2000:]}
        results["repos"][d.name] = entry
    tot = {}
    for e in results["repos"].values():
        for k, v in e["loc"].items():
            tot[k] = tot.get(k, 0) + v
    results["totals"] = {"repos": len(results["repos"]), "commits": sum(e["commits"] for e in results["repos"].values()),
                         "loc": dict(sorted(tot.items(), key=lambda kv: -kv[1])), "loc_total": sum(tot.values())}
    json.dump(results, open(pathlib.Path(__file__).parent / "results.json", "w"), indent=2)
    print(json.dumps(results["totals"], indent=2))
