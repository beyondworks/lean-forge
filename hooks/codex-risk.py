#!/usr/bin/env python3
"""Codex Bash risk adapter: deny hand-off, and translate unsupported ask into one-time confirmation."""
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
from castra_guardian import classify
from importlib.util import spec_from_file_location, module_from_spec
from codex_approval import consume, request

release_spec = spec_from_file_location("castra_release_gate", HERE / "castra-release-gate.py")
release_module = module_from_spec(release_spec)
release_spec.loader.exec_module(release_module)


def run_hook(name, payload):
    proc = subprocess.run([sys.executable, str(HERE / name)], input=json.dumps(payload),
                          text=True, capture_output=True, timeout=28)
    if proc.returncode != 0:
        raise RuntimeError(f"{name} exited unsuccessfully")
    if not proc.stdout.strip():
        return {}
    try:
        result = json.loads(proc.stdout)
        if not isinstance(result, dict):
            raise RuntimeError(f"{name} returned invalid output")
        return result
    except (ValueError, TypeError) as error:
        raise RuntimeError(f"{name} returned invalid output") from error


def decision(result):
    return (result.get("hookSpecificOutput") or {}).get("permissionDecision")


def main():
    payload = json.load(sys.stdin)
    inp = payload.get("tool_input") or {}
    command = inp.get("command")
    if payload.get("tool_name") != "Bash" or not isinstance(command, str):
        print("{}")
        return
    verdict = classify(command)
    if verdict["verdict"] == "hand_off":
        print(json.dumps(run_hook("castra-guardian.py", payload)))
        return
    release_active, _, _ = release_module.release_target(command, payload.get("cwd") or os.getcwd())
    release = run_hook("castra-release-gate.py", payload)
    if release_active and decision(release) not in ("allow", "deny", "ask"):
        release["needs_user_confirmation"] = True
    if decision(release) == "deny":
        print(json.dumps(release))
        return
    reasons = "; ".join(item["reason"] for item in verdict.get("reasons", []))
    needs_confirmation = (verdict["verdict"] == "confirm_at_action" or decision(release) == "ask"
                          or release.get("needs_user_confirmation") is True)
    if needs_confirmation:
        if consume(payload, command):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}))
        else:
            if decision(release) == "ask":
                reasons = (release.get("hookSpecificOutput") or {}).get("permissionDecisionReason", "Release target needs review.")
            elif release.get("needs_user_confirmation") is True:
                reasons = (release.get("hookSpecificOutput") or {}).get("additionalContext", "Release gate did not grant explicit permission.")
            print(json.dumps(request(payload, command, "Castra Codex confirmation required: " + reasons)))
        return
    # Keep non-blocking context from either legacy guard.
    advisories = []
    for result in (run_hook("castra-guardian.py", payload), release):
        out = result.get("hookSpecificOutput") or {}
        if out.get("additionalContext"):
            advisories.append(out["additionalContext"])
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "\n".join(advisories)}} if advisories else {}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.TimeoutExpired):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                        "permissionDecisionReason": "Castra Codex risk adapter failed closed; inspect hook state before retrying."}}))
