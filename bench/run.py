#!/usr/bin/env python3
"""lean-forge benchmark runner (case 1: no other harness loaded).

usage: run.py <arm: A|B|G> <task: t1..t8> <rep>
  A = dryforge                (env DRYFORGE_PLUGIN = path to dryforge/claude)
  B = Castra + Ponytail       (env CASTRA_SETTINGS = settings JSON holding Castra hooks,
                               env PONYTAIL_PLUGIN = path to the ponytail plugin)
  G = lean-forge              (this repository; env LEAN_FORGE overrides)
A scripted user (claude sonnet) answers every arm from the same intent file (intent/<task>.md).
Hidden tests (hidden/test_<task>.py) grade the result. Results land in results/c1-<arm>-<task>-r<rep>.json.
Other arms in results/ (C..F) are intermediate prototypes kept for the record; they are not runnable here.
"""
import json, os, shutil, subprocess, sys, time

AB = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("BENCH_MODEL", "claude-opus-5")
TURN_TIMEOUT = 45 * 60
ENV = {k: os.environ[k] for k in ("HOME", "PATH", "USER", "TYPESAFE_API_KEY") if k in os.environ}
ENV.update(LANG="en_US.UTF-8", TERM="dumb")

arm, task, rep = sys.argv[1], sys.argv[2], sys.argv[3]
case = "1"
rid = f"c{case}-{arm}-{task}-r{rep}"
wd = f"{AB}/runs/{rid}"
os.makedirs(f"{AB}/results", exist_ok=True)
os.makedirs(f"{AB}/probe", exist_ok=True)  # empty cwd for the simulated user
log_path = f"{AB}/results/{rid}.log"


def log(*a):
    with open(log_path, "a") as f:
        print(time.strftime("%H:%M:%S"), *a, file=f)


def agent_cmd():
    c = ["claude", "-p", "--model", MODEL, "--output-format", "json", "--permission-mode", "bypassPermissions",
         "--setting-sources", "project", "--strict-mcp-config"]
    if arm == "A":
        return c + ["--plugin-dir", os.environ["DRYFORGE_PLUGIN"]]
    if arm == "B":
        return c + ["--settings", os.environ["CASTRA_SETTINGS"], "--plugin-dir", os.environ["PONYTAIL_PLUGIN"]]
    if arm == "G":
        return c + ["--plugin-dir", os.environ.get("LEAN_FORGE", os.path.dirname(AB))]
    raise SystemExit(f"unknown arm {arm}")


def run_agent(prompt, sid):
    # ponytail: server errors (500/529) are retried on the same turn; they are not agent behavior
    for attempt in range(4):
        j = _run_agent_once(prompt, sid)
        if not (j.get("is_error") and "API Error" in str(j.get("result"))):
            break
        log(f"server error, retry {attempt + 1}: {str(j.get('result'))[:80]!r}")
        sid = j.get("session_id", sid)
        time.sleep(60 * (attempt + 1))
    j["api_retries"] = attempt
    return j


def _run_agent_once(prompt, sid):
    c = agent_cmd() + (["--resume", sid] if sid else []) + [prompt]
    t = time.time()
    try:
        p = subprocess.run(c, cwd=wd, env=ENV, capture_output=True, text=True,
                           timeout=TURN_TIMEOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        out = p.stdout
    except subprocess.TimeoutExpired as e:
        return {"error": "timeout", "wall": time.time() - t}
    try:
        j = json.loads(out)
    except Exception:
        return {"error": "badjson", "raw": (out + p.stderr)[-2000:], "wall": time.time() - t}
    j["wall"] = time.time() - t
    return j


SIM_RULES = """너는 이 소프트웨어 작업을 맡긴 사용자다. 네가 원하는 것(의도)은 아래 [의도]와 같다.
개발 에이전트의 마지막 메시지 [메시지]를 읽고 정확히 다음 셋 중 하나로만 출력하라.

1) 에이전트가 작업을 마쳤다고 보고했고 너에게 요청하는 것이 없으면: DONE 한 단어만.
2) 에이전트가 열린 질문 없이 다음 단계 진행·실행 허락만 기다리거나 다음 명령 실행을 안내하면: PROCEED 한 단어만.
3) 에이전트가 질문하거나 승인·선택·확인을 요청하면: 사용자로서 짧게 답한다.
   - [의도]에 있는 내용으로만 답한다. [의도]에 없는 것을 물으면 "그건 알아서 판단해 주세요".
   - 계획·명세 승인을 요청받으면 [의도]와 맞으면 "승인합니다"로 시작해 답하고, 어긋나면 어긋난 점만 고쳐 말한다.
   - 묻지 않은 의도를 먼저 알려 주지 않는다. 코드를 작성하거나 새 요구를 추가하지 않는다.

[가장 먼저 적용할 규칙] [의도]는 결과물에 대한 것이고, 일하는 절차에 대한 것이 아니다.
에이전트가 자기 절차·방식을 물으면(작업 문서·계획 파일·기록 파일을 만들지, 커밋할지, 진행 순서, 테스트를 돌릴지,
프로젝트 설명을 어떻게 기록할지) 절대 줄이거나 막거나 대안을 고르지 말고 그 항목에는 정확히
"원래 하시는 방식대로 진행하세요"라고만 답한다. 예: "계획 파일을 만들어도 될까요, 아니면 바로 고칠까요?" → "원래 하시는 방식대로 진행하세요".
"""


def simulate(msg):
    intent = open(f"{AB}/intent/{task}.md").read()
    prompt = f"{SIM_RULES}\n[의도]\n{intent}\n[메시지]\n{msg[-12000:]}"
    c = ["claude", "-p", "--model", "sonnet", "--setting-sources", "project",
         "--strict-mcp-config", "--disable-slash-commands", "--output-format", "json", prompt]
    p = subprocess.run(c, cwd=f"{AB}/probe", env=ENV, capture_output=True, text=True,
                       timeout=600, stdin=subprocess.DEVNULL, start_new_session=True)
    r = json.loads(p.stdout).get("result", "").strip()
    return r


def sh(cmd):
    return subprocess.run(cmd, cwd=wd, shell=True, capture_output=True, text=True, env=ENV)


def grade():
    g = {}
    shutil.copy(f"{AB}/hidden/test_{task}.py", f"{wd}/tests/_hidden_{task}.py")
    h = sh(f"python3 -m unittest tests._hidden_{task} 2>&1 | tail -3")
    os.remove(f"{wd}/tests/_hidden_{task}.py")
    g["hidden"] = h.stdout.strip().splitlines()[-1] if h.stdout.strip() else "?"
    v = sh("python3 -m unittest discover -s tests 2>&1 | tail -1")
    g["visible"] = v.stdout.strip()
    # diff against the fixture's root commit: agents may commit/merge on their own
    base = sh("git rev-list --max-parents=0 HEAD | tail -1").stdout.strip()
    sh("git add -N invoicer tests README.md 2>/dev/null")
    g["diff_stat"] = sh(f"git diff --shortstat {base} -- invoicer tests README.md").stdout.strip()
    g["changed_files"] = sh(f"git diff --name-only {base} -- invoicer tests README.md").stdout.split()
    g["commits_made"] = int(sh(f"git rev-list --count {base}..HEAD").stdout.strip() or 0)
    g["other_files"] = [f for f in sh("git status --porcelain").stdout.splitlines()
                        if not any(x in f for x in ("invoicer/", "tests/", "README.md", "__pycache__"))]
    return g


def main():
    shutil.rmtree(wd, ignore_errors=True)
    src = f"{AB}/fixture_{task}" if os.path.isdir(f"{AB}/fixture_{task}") else f"{AB}/fixture"
    shutil.copytree(src, wd)
    subprocess.run("git init -q && git add invoicer tests README.md .gitignore && "
                   "git -c user.email=bench@local -c user.name=bench commit -qm baseline",
                   shell=True, cwd=wd, check=True)
    task_text = open(f"{AB}/tasks/{task}.txt").read().strip()
    phase = "ready" if arm == "A" else "work"
    prompt = f"/dryforge:ready {task_text}" if arm == "A" else task_text
    sid, turns, sims = None, [], []
    limits = {"ready": 5, "go": 4, "work": 6}
    count = {"ready": 0, "go": 0, "work": 0}
    t0 = time.time()
    while True:
        count[phase] += 1
        log(f"[{phase} {count[phase]}] >>> {prompt[:200]!r}")
        j = run_agent(prompt, sid)
        sid = j.get("session_id", sid)
        turns.append({"phase": phase, "prompt": prompt, **{k: j.get(k) for k in (
            "error", "api_retries", "wall", "total_cost_usd", "duration_ms", "num_turns", "usage", "is_error", "subtype")},
            "result": (j.get("result") or j.get("raw") or "")[-6000:]})
        log(f"<<< {str(j.get('result') or j.get('error'))[-600:]!r}")
        if j.get("error") or not j.get("result") or j.get("is_error"):
            break
        sim = simulate(j["result"])
        sims.append(sim)
        log(f"SIM: {sim[:300]!r}")
        if sim == "DONE" or sim == "PROCEED":
            if phase == "ready":
                phase, prompt = "go", "/dryforge:go"
            elif sim == "DONE":
                break
            else:
                prompt = "진행해 주세요."
        else:
            prompt = sim
        if count[phase] >= limits[phase] and prompt != "/dryforge:go":
            log("turn limit"); break
    res = {"id": rid, "case": case, "arm": arm, "task": task, "rep": rep,
           "wall_total": time.time() - t0, "agent_turns": len(turns),
           "user_replies": sum(1 for s in sims if s not in ("DONE", "PROCEED")),
           "cost_usd": sum((t.get("total_cost_usd") or 0) for t in turns),
           "errors": [t["error"] for t in turns if t.get("error")],
           "grade": grade(), "turns": turns, "sims": sims, "session_id": sid}
    json.dump(res, open(f"{AB}/results/{rid}.json", "w"), ensure_ascii=False, indent=1)
    log("RESULT", json.dumps({k: res[k] for k in ("wall_total", "agent_turns", "user_replies", "cost_usd", "grade")}, ensure_ascii=False))



main()
