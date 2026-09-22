# `python3 test_forge.py` — SETTLE gate (fallback + live Jev). PROVE is Castra's ledger: see test_bundle.py. Live part needs the
# TYPESAFE_API_KEY (env or macOS keychain) and network; the temp repo only feeds `git ls-files`.
import glob, json, os, subprocess, sys, tempfile, time
H = os.path.join(os.path.dirname(os.path.abspath(__file__)), "forge.py")
REPO = tempfile.mkdtemp(prefix="lf-forge-")
subprocess.run("git init -q && mkdir invoicer && echo '' > invoicer/calc.py && git add invoicer/calc.py && "
               "git -c user.email=t@t -c user.name=t commit -qm init", shell=True, cwd=REPO, check=True)
S = os.path.expanduser("~/.cache/lean-forge")
denied = lambda out: '"deny"' in out

def session(tag):
    sid = f"selftest-{tag}-{os.getpid()}"
    def call(ev, jev_off=False, **kw):
        env = dict(os.environ, **({"LEAN_FORGE_JEV": "off"} if jev_off else {}))
        return subprocess.run([sys.executable, H, ev], input=json.dumps({"session_id": sid, "cwd": REPO, **kw}),
                              capture_output=True, text=True, env=env).stdout
    return call, f"{S}/{sid}.mechanical", f"{S}/{sid}.json"

# SETTLE fallback path
call, mech, sp = session("fallback")
call("prompt", jev_off=True, prompt="x")
assert denied(call("pre", tool_name="Edit")), "new request: edits closed"
assert not denied(call("pre", tool_name="Bash")), "non-edit tools pass"
call("stop")
call("prompt", prompt="answer")
assert not denied(call("pre", tool_name="Write")), "after ask + answer: open"
call("stop")
call("prompt", jev_off=True, prompt="y")
assert denied(call("pre", tool_name="Edit")), "next new request closes again"
time.sleep(0.01); open(mech, "w").write("typo fix\n")
assert not denied(call("pre", tool_name="Edit")), "fallback hatch opens"


# SETTLE live Jev path
call, mech, sp = session("live")
call("prompt", prompt="invoicer/calc.py 맨 위 설명문에 있는 오타 recieve를 receive로 고쳐 줘.")
st = json.load(open(sp)); assert st.get("jev") is not None, "Jev answered"
assert not denied(call("pre", tool_name="Edit")), f"Jev: typo opens at once (p={st['jev']})"
call("stop")
call("prompt", prompt="송장을 PDF로 뽑는 기능 만들어 줘. 거래처에 메일로 보낼 거야.")
st = json.load(open(sp)); time.sleep(0.01); open(mech, "w").write("I say it is mechanical\n")
out = call("pre", tool_name="Write")
assert denied(out) and "independent check" in out, f"Jev: open request stays closed, hatch refused (p={st['jev']})"

for f in glob.glob(f"{S}/selftest-*-{os.getpid()}.*"): os.remove(f)
print("forge ok (settle fallback, settle live Jev)")
