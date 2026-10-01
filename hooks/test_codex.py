import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "hooks"
sys.path.insert(0, str(HOOKS))
sys.path.insert(0, str(ROOT / "scripts"))
import castra_runtime
from codex_approval import approve, consume, request

risk_spec = importlib.util.spec_from_file_location("codex_risk", HOOKS / "codex-risk.py")
codex_risk = importlib.util.module_from_spec(risk_spec)
risk_spec.loader.exec_module(codex_risk)

trace_spec = importlib.util.spec_from_file_location("castra_trace", HOOKS / "castra-trace.py")
castra_trace = importlib.util.module_from_spec(trace_spec)
trace_spec.loader.exec_module(castra_trace)


def call(script, payload, *args):
    return subprocess.run([sys.executable, str(HOOKS / script), *args], input=json.dumps(payload),
                          text=True, capture_output=True, check=True)


def main():
    assert castra_trace.patch_paths("*** Begin Patch\n*** Add File: pkg/new.py\n*** Update File: pkg/edit.py\n*** Delete File: pkg/old.py\n") == [
        ("pkg/new.py", "added"), ("pkg/edit.py", "updated"), ("pkg/old.py", "deleted")]
    assert castra_trace.patch_paths("*** Begin Patch\n*** Update File: pkg/old.py\n*** Move to: pkg/new.py\n") == [
        ("pkg/old.py", "deleted"), ("pkg/new.py", "moved")]
    with tempfile.TemporaryDirectory() as temp:
        os.environ["CASTRA_HOME"] = str(Path(temp) / "castra")
        work = Path(temp) / "repo"
        work.mkdir()
        old = work / "old.py"
        old.write_text("value = 1\n")
        sid = "codex-test-" + str(os.getpid())
        old.unlink()
        castra_runtime.record_edit(work, sid, old, deleted=True)
        canonical_old = castra_runtime.canonical(work, old)
        verified = subprocess.run([sys.executable, str(ROOT / "scripts" / "castra_runtime.py"), "verify",
                                   "--session", sid, "--file", str(old), "--", sys.executable, "-c", "pass"],
                                  cwd=work, text=True, capture_output=True, check=True)
        assert '"verified"' in verified.stdout, verified.stdout
        moved_source, moved_target = work / "before.py", work / "after.py"
        moved_source.write_text("value = 1\n")
        moved_source.rename(moved_target)
        moved_source, moved_target = castra_runtime.canonical(work, moved_source), castra_runtime.canonical(work, moved_target)
        call("castra-trace.py", {"session_id": sid, "cwd": str(work), "hook_event_name": "PostToolUse", "tool_name": "apply_patch",
             "tool_input": {"command": "*** Begin Patch\n*** Update File: before.py\n*** Move to: after.py\n"},
             "tool_response": {"exit_code": 0}})
        moved_check = subprocess.run([sys.executable, str(ROOT / "scripts" / "castra_runtime.py"), "verify",
                                      "--session", sid, "--file", moved_source, "--file", moved_target,
                                      "--", sys.executable, "-c", "pass"], cwd=work, text=True,
                                     capture_output=True, check=True)
        assert '"verified"' in moved_check.stdout, moved_check.stdout
        payload = {"session_id": sid, "cwd": str(work)}
        result = request(payload, "rm -rf ./exact", "test")
        token = result["hookSpecificOutput"]["permissionDecisionReason"].split("APPROVE ")[1].rstrip(".")
        assert approve(payload, token)
        assert consume(payload, "rm -rf ./exact")
        assert not consume(payload, "rm -rf ./exact")
        result = request(payload, "rm -rf ./exact", "test")
        token = result["hookSpecificOutput"]["permissionDecisionReason"].split("APPROVE ")[1].rstrip(".")
        assert approve(payload, token)
        assert not consume(payload, "rm -rf ./different")
        other = Path(temp) / "other"
        other.mkdir()
        assert not consume({**payload, "cwd": str(other)}, "rm -rf ./exact")
        assert consume(payload, "rm -rf ./exact")
        assert not consume(payload, "rm -rf ./exact")
        risk_payload = {**payload, "tool_name": "Bash", "tool_input": {"command": "rm -rf ./codex-test"}}
        denied = json.loads(call("codex-risk.py", risk_payload).stdout)
        reason = denied["hookSpecificOutput"]["permissionDecisionReason"]
        assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
        integration_token = reason.split("APPROVE ")[1].rstrip(".")
        call("forge.py", {**payload, "prompt": "APPROVE " + integration_token}, "prompt")
        allowed = json.loads(call("codex-risk.py", risk_payload).stdout)
        assert allowed["hookSpecificOutput"]["permissionDecision"] == "allow"
        bypass = json.loads(call("codex-risk.py", {**risk_payload, "permission_mode": "bypassPermissions",
                                                  "tool_input": {"command": "rm -rf ./build-cache"}}).stdout)
        assert "permissionDecision" not in bypass["hookSpecificOutput"] and "advisory" in bypass["hookSpecificOutput"]["additionalContext"], \
            "approval never: rm -r is a note, not a token stop"
        env_read = json.loads(call("codex-risk.py", {**risk_payload, "permission_mode": "bypassPermissions",
                                                    "tool_input": {"command": "cat .env.local"}}).stdout)
        assert env_read["hookSpecificOutput"]["permissionDecision"] == "deny", "hand-off still denies"
        tag_payload = {**payload, "permission_mode": "auto", "tool_name": "Bash",
                       "tool_input": {"command": "git tag v1.0.0"}}
        tag_result = json.loads(call("codex-risk.py", tag_payload).stdout)
        assert tag_result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "APPROVE " in tag_result["hookSpecificOutput"]["permissionDecisionReason"]

    class Failed:
        returncode = 1
        stdout = "{}"

    original_run = codex_risk.subprocess.run
    try:
        codex_risk.subprocess.run = lambda *args, **kwargs: Failed()
        try:
            codex_risk.run_hook("castra-release-gate.py", {})
            raise AssertionError("nonzero release gate must fail closed")
        except RuntimeError:
            pass
        Failed.returncode = 0
        Failed.stdout = "not json"
        try:
            codex_risk.run_hook("castra-release-gate.py", {})
            raise AssertionError("malformed release gate output must fail closed")
        except RuntimeError:
            pass
        Failed.stdout = json.dumps({"hookSpecificOutput": {"additionalContext": "no prompt"}})
        assert codex_risk.decision(json.loads(Failed.stdout)) is None
    finally:
        codex_risk.subprocess.run = original_run
    print("codex adapter ok (patch paths, deleted-file evidence, exact one-time approval)")


if __name__ == "__main__":
    main()
