#!/usr/bin/env python3
"""lean-forge SETTLE gate (Jev triage). PROVE is Castra's evidence ledger (castra-trace/openloop).

A message after a turn that ended without edits opens the gate only if Jev judges it a reply to that turn;
a new request there is triaged from scratch.

Per request, edits stay closed until the user answered our questions, unless Jev judges the request
mechanical. If Jev is unavailable, a one-line marker file opens a mechanical request (fallback).
ponytail: per-session JSON state, no locking; one session's hooks run sequentially.
"""
import json, os, subprocess, sys, time, urllib.request

STATE_DIR = os.path.expanduser("~/.cache/lean-forge")
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
JEV_Q = {"fixed": {"type": "noul", "instructions":
    "Given the request and the repository summary, does the request literally determine the exact result, so that any two "
    "competent engineers who have never talked to this user would produce the same observable output (same names, formats, "
    "rules, edge-case behavior)? Answer yes only if no product, policy, or output-format decision is left open."}}
MECH_THRESHOLD = 0.5  # ponytail: calibrated on 16 requests (mechanical >= 0.55, must-ask <= 0.21); tune on real traffic
REPLY_Q = {"reply": {"type": "noul", "instructions":
    "The agent's last message and the user's new message are given. Is the user's new message a reply to the agent's "
    "last message (answering its questions, choosing among its options, approving or correcting its proposal), rather than "
    "a new, separate request about something else?"}}
REPLY_THRESHOLD = 0.5  # ponytail: calibrated on 10 exchanges (reply >= 0.79, new request <= 0.24)


def jev(state, questions, name):
    """Jev probability for one noul question, or None when Jev is unavailable (callers fall back)."""
    if os.environ.get("LEAN_FORGE_JEV") == "off":
        return None
    try:
        key = os.environ.get("TYPESAFE_API_KEY") or subprocess.run(
            ["security", "find-generic-password", "-s", "TYPESAFE_API_KEY", "-w"],  # macOS keychain
            capture_output=True, text=True, timeout=2).stdout.strip()
        if not key:
            return None
        body = json.dumps({"model": "jev-latest", "questions": questions, "state": state}).encode()
        req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", data=body, method="POST",
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=4) as r:
            return json.load(r)["answers"][name]["noul"]
    except Exception:
        return None


def jev_fixed(prompt, cwd):
    """Probability that the request fixes the result."""
    try:
        files = subprocess.run(["git", "ls-files"], cwd=cwd, capture_output=True, text=True, timeout=2).stdout.split()[:60]
    except Exception:
        files = []
    return jev({"repository_files": files, "request": prompt[:6000]}, JEV_Q, "fixed")


def last_agent_message(transcript_path):
    """Text of the last assistant message in the session transcript ('' if unreadable)."""
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, 2); f.seek(max(0, f.tell() - 400_000))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except Exception:
        return ""
    for line in reversed(lines):
        try:
            m = json.loads(line)
        except Exception:
            continue
        content = (m.get("message") or {}).get("content")
        if m.get("type") == "assistant" and isinstance(content, list):
            text = "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text").strip()
            if text:
                return text[-4000:]
    return ""


def is_reply(prompt, transcript_path):
    """After a turn that ended without edits: is this message an answer, not a new request? Unknown counts as answer."""
    agent = last_agent_message(transcript_path)
    if not agent:
        return True
    p = jev({"agent_last_message": agent, "user_new_message": prompt[:4000]}, REPLY_Q, "reply")
    return p is None or p >= REPLY_THRESHOLD


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


def main():
    ev = sys.argv[1]
    inp = json.load(sys.stdin)
    sid = inp.get("session_id", "unknown")
    os.makedirs(STATE_DIR, exist_ok=True)
    sp, mech = f"{STATE_DIR}/{sid}.json", f"{STATE_DIR}/{sid}.mechanical"
    try:
        st = json.load(open(sp))
    except Exception:
        st = {"state": "closed", "prompt_at": 0}
    now = time.time()

    if ev == "prompt":
        if st.get("state") == "asked" and is_reply(inp.get("prompt", ""), inp.get("transcript_path", "")):
            st = {"state": "open", "prompt_at": now, "jev": st.get("jev")}  # the user is answering our questions
        else:  # a new request, including one that follows a turn which only explained something
            p = jev_fixed(inp.get("prompt", ""), inp.get("cwd", "."))
            st = {"state": "open" if (p is not None and p >= MECH_THRESHOLD) else "closed",
                  "prompt_at": now, "jev": p, "hatch": p is None}

    elif ev == "pre":
        if inp.get("tool_name") not in EDIT_TOOLS or st.get("state") == "open":
            return
        if not st.get("hatch", True):
            return deny("lean-forge SETTLE: an independent check judged that this request leaves outcome-changing "
                        "decisions open. Send the user your questions / confirm-by-example message and end your turn; "
                        "edits open when they answer.")
        try:
            if os.path.getmtime(mech) >= st["prompt_at"] and open(mech).read().strip():
                return
        except OSError:
            pass
        return deny("lean-forge SETTLE: edits are closed until the outcome-changing decisions are settled. Either "
                    "(a) send the user your questions and end your turn, or (b) if the request literally fixes the "
                    f"result, run `echo '<one-line reason>' > {mech}` and retry the edit.")

    elif ev == "stop":
        used_hatch = os.path.exists(mech) and os.path.getmtime(mech) >= st.get("prompt_at", 0)
        if st.get("state") == "closed" and not used_hatch:
            st["state"] = "asked"

    json.dump(st, open(sp, "w"))


main()
