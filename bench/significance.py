"""lean-forge 2.0 (arm G) vs existing harness results, same tasks, same case. No re-runs of existing arms.

Pass rate: Fisher exact test (two-sided) on hidden-test counts, pooled over the tasks both arms ran.
Time/cost: paired sign test over tasks (G averaged over its reps); ties dropped.
ponytail: stdlib only; small-sample exact tests, no effect-size modelling.
"""
import glob, json, math, re, sys

N = {'t1': 5, 't2': 5, 't3': 1, 't4': 5, 't5': 5, 't6': 5, 't7': 5, 't8': 5}
NAMES = {'A': 'dryforge', 'B': 'Castra+Ponytail', 'C': 'v0.3', 'D': 'v0.4 조합', 'E': 'intent-gate 단독',
         'F': 'lean-forge 1.0', 'G': 'lean-forge 2.0'}


def runs(case, arm, task):
    out = []
    for f in sorted(glob.glob(f"results/c{case}-{arm}-{task}-r[0-9].json")):
        if f.endswith("-r0.json"):
            continue
        d = json.load(open(f)); h = d["grade"]["hidden"]
        p = N[task] - (0 if h == "OK" else sum(int(x) for x in re.findall(r"=(\d+)", h)))
        out.append((p, d["wall_total"] / 60, d["cost_usd"]))
    return out


def fisher(a_pass, a_n, b_pass, b_n):
    """Two-sided Fisher exact p for [[a_pass, a_fail], [b_pass, b_fail]]."""
    k, n, K = a_pass, a_n + b_n, a_pass + b_pass
    def pmf(x):
        return math.comb(K, x) * math.comb(n - K, a_n - x) / math.comb(n, a_n)
    lo, hi = max(0, a_n - (n - K)), min(a_n, K)
    obs = pmf(k)
    return min(1.0, sum(pmf(x) for x in range(lo, hi + 1) if pmf(x) <= obs * (1 + 1e-9)))


def sign_test(diffs):
    d = [x for x in diffs if abs(x) > 1e-9]
    if not d:
        return 1.0, 0, 0
    pos = sum(x > 0 for x in d); n = len(d); k = min(pos, n - pos)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)
    return p, pos, n - pos


def compare(case, other, tasks):
    tasks = [t for t in tasks if runs(case, "G", t) and runs(case, other, t)]
    if not tasks:
        return {"tasks": 0}
    g ={t: runs(case, "G", t) for t in tasks}; o = {t: runs(case, other, t) for t in tasks}
    gp = sum(p for t in tasks for p, _, _ in g[t]); gn = sum(N[t] * len(g[t]) for t in tasks)
    op = sum(p for t in tasks for p, _, _ in o[t]); on = sum(N[t] * len(o[t]) for t in tasks)
    avg = lambda rs, i: sum(r[i] for r in rs) / len(rs)
    pt, gf, of = sign_test([avg(g[t], 1) - avg(o[t], 1) for t in tasks])
    pc, _, _ = sign_test([avg(g[t], 2) - avg(o[t], 2) for t in tasks])
    gt = sum(avg(g[t], 1) for t in tasks); ot = sum(avg(o[t], 1) for t in tasks)
    gc = sum(avg(g[t], 2) for t in tasks); oc = sum(avg(o[t], 2) for t in tasks)
    return {"tasks": len(tasks), "g": f"{gp}/{gn} ({gp/gn:.0%})", "o": f"{op}/{on} ({op/on:.0%})",
            "p_pass": fisher(gp, gn, op, on), "time": f"{gt:.1f} vs {ot:.1f}분", "p_time": pt,
            "slower_tasks": f"{gf}/{gf+of}", "cost": f"${gc:.2f} vs ${oc:.2f}", "p_cost": pc}


if __name__ == "__main__":
    for case in "12":
        print(f"== 케이스 {case}")
        for other in "ABCDEF":
            if not any(runs(case, other, t) for t in N):
                continue
            r = compare(case, other, list(N))
            if not r["tasks"]:
                continue
            print(f"  vs {NAMES[other]:16} 과제 {r['tasks']} | 통과 G {r['g']} vs {r['o']} p={r['p_pass']:.3f} | "
                  f"시간 {r['time']} (G가 느린 과제 {r['slower_tasks']}) p={r['p_time']:.3f} | 비용 {r['cost']} p={r['p_cost']:.3f}")
