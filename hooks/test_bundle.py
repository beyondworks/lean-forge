# `python3 test_bundle.py` — the vendored Castra and Ponytail parts run from this plugin alone.
# CASTRA_HOME points at an empty temp dir, so nothing can fall back to a standalone ~/.castra install.
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = os.path.join(ROOT, "hooks")
home = tempfile.mkdtemp(prefix="lf-castra-home-")
repo = tempfile.mkdtemp(prefix="lf-repo-")
subprocess.run("git init -q && echo 'x = 1' > app.py && git add app.py && git -c user.email=t@t -c user.name=t commit -qm init",
               shell=True, cwd=repo, check=True)
ENV = dict(os.environ, CASTRA_HOME=home, CLAUDE_PLUGIN_ROOT=ROOT)
SID = "11111111-2222-4333-8444-555555555555"


def hook(script, payload, runner=sys.executable):
    r = subprocess.run([runner, os.path.join(H, script)], input=json.dumps(payload), capture_output=True, text=True,
                       env=ENV, cwd=repo, timeout=60)
    return r.stdout


def pre_bash(cmd, mode="default"):
    return hook("castra-guardian.py", {"tool_name": "Bash", "tool_input": {"command": cmd}, "permission_mode": mode,
                                       "session_id": SID, "cwd": repo})


# guardian: hand-off → deny, confirm-at-action → ask (default mode), ordinary → nothing
assert '"deny"' in pre_bash("git push --force origin main"), "force push handed off"
assert '"deny"' in pre_bash("cat .env.local"), ".env output handed off"
assert '"ask"' in pre_bash("rm -rf build"), "recursive delete asks at action"
assert pre_bash("ls -la").strip() in ("", "{}"), "ordinary command passes"

# release gate: publication in a repo with no CI record must not be silently allowed
out = hook("castra-release-gate.py", {"tool_name": "Bash", "tool_input": {"command": "gh release create v1.0.0"},
                                      "permission_mode": "default", "session_id": SID, "cwd": repo})
assert ('"deny"' in out or '"ask"' in out), f"release without CI evidence is stopped: {out[:200]}"

# posture: contract injected, runtime hint points at this plugin's scripts
out = hook("castra-posture.py", {"hook_event_name": "SessionStart", "session_id": SID, "cwd": repo, "source": "startup"})
assert "castra_execution_posture" in out and os.path.join(ROOT, "scripts") in out, "posture uses vendored scripts"

# evidence ledger: edit → Stop blocked; verify → passes; re-edit → blocked again
edit = {"hook_event_name": "PostToolUse", "tool_name": "Edit", "session_id": SID, "cwd": repo,
        "tool_input": {"file_path": os.path.join(repo, "app.py")}, "tool_response": {"success": True}}
stop = {"hook_event_name": "Stop", "session_id": SID, "cwd": repo, "stop_hook_active": False}
open(os.path.join(repo, "app.py"), "w").write("x = 2\n")
hook("castra-trace.py", edit)
assert '"block"' in hook("castra-openloop.py", stop), "unverified edit blocks Stop"
v = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "castra_runtime.py"), "verify", "--session", SID,
                    "--file", os.path.join(repo, "app.py"), "--", sys.executable, "-c", "import app; assert app.x == 2"],
                   capture_output=True, text=True, env=ENV, cwd=repo)
assert '"verified"' in v.stdout, f"verify recorded: {v.stdout[:200]} {v.stderr[:200]}"
assert '"block"' not in hook("castra-openloop.py", stop), "verified edit lets Stop through"
open(os.path.join(repo, "app.py"), "w").write("x = 3\n")
hook("castra-trace.py", edit)
assert '"block"' in hook("castra-openloop.py", dict(stop)), "re-edit invalidates evidence"

# ponytail: activation injects the vendored SKILL.md with the SETTLE-compatible rule
out = hook("ponytail-activate.js", {"hook_event_name": "SessionStart", "session_id": SID, "cwd": repo, "source": "startup"},
           runner="node")
assert "PONYTAIL" in out and "Once the outcome-changing decisions are settled" in out, "ponytail patched rule injected"
assert "Never stall on an answer you can default." not in out.replace("After SETTLE, never stall", ""), "old rule gone"

print("bundle ok (guardian, release gate, posture, evidence ledger, ponytail)")
