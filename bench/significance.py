"""lean-forge 2.0 (arm G) vs existing harness results, same tasks, same case. No re-runs of existing arms.

Each task is one cluster (its hidden tests are not independent; Miller 2024, arXiv:2411.00640). For pass rate, time and
cost: per-task means (reps averaged), paired differences G - other, their mean with a 95% t-interval, and a sign test.
ponytail: stdlib only; small-sample t-interval and exact sign test, no effect-size modelling.
"""
import glob, json, math, re, statistics, sys

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262}

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


def sign_test(diffs):
    d = [x for x in diffs if abs(x) > 1e-9]
    if not d:
        return 1.0, 0, 0
    pos = sum(x > 0 for x in d); n = len(d); k = min(pos, n - pos)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)
    return p, pos, n - pos


def compare(case, other, tasks):
    tasks = [t for t in tasks if runs(case, "G", t) and runs(case, other, t)]
    if len(tasks) < 2:
        return {"tasks": len(tasks)}
    out = {"tasks": len(tasks)}
    for i, key in ((0, "pass"), (1, "min"), (2, "cost")):
        mean = lambda rs, t: sum((r[i] / N[t] if i == 0 else r[i]) for r in rs) / len(rs)
        g = [mean(runs(case, "G", t), t) for t in tasks]; o = [mean(runs(case, other, t), t) for t in tasks]
        d = [a - b for a, b in zip(g, o)]
        m = sum(d) / len(d); h = T95.get(len(d) - 1, 1.96) * statistics.stdev(d) / math.sqrt(len(d))
        out[key] = (sum(g) / len(g), sum(o) / len(o), m, m - h, m + h, sign_test(d)[0])
    return out


if __name__ == "__main__":
    for case in "12":
        print(f"== 케이스 {case}")
        for other in "ABCDEF":
            if not any(runs(case, other, t) for t in N):
                continue
            r = compare(case, other, list(N))
            if r["tasks"] < 2:
                continue
            cells = [f"{k} G {v[0]:.2f} vs {v[1]:.2f}, 차이 {v[2]:+.2f} (95% {v[3]:+.2f}~{v[4]:+.2f}) p={v[5]:.3f}"
                     for k, v in ((k, r[k]) for k in ("pass", "min", "cost"))]
            print(f"  vs {NAMES[other]:16} 과제 {r['tasks']} | " + " | ".join(cells))
