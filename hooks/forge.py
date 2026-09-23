#!/usr/bin/env python3
"""lean-forge SETTLE gate (Jev triage). PROVE is Castra's evidence ledger (castra-trace/openloop).

At each user message Jev, given the agent's last message, judges whether carrying it out needs a user-visible
decision the conversation has not settled. If so, edits stay closed until the user answered our questions;
continuing, approving or correcting the plan, fixes and runs stay open. If Jev is unavailable, a message after an
asking turn counts as its answer, and a one-line marker file opens a mechanical request (fallback).
ponytail: per-session JSON state, no locking; one session's hooks run sequentially.
"""
import json, os, subprocess, sys, time, urllib.request

STATE_DIR = os.path.expanduser("~/.cache/lean-forge")
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
NEEDS_Q = {"needs_decision": {"type": "noul", "instructions":
    "The user's new message is a request to a coding agent; the agent's last message and a note on how this user works are "
    "given as context. To carry out the new message, must the agent choose something the user will see or rely on that "
    "neither the message nor the conversation settles: an output format, names or labels, a screen or interaction design, "
    "a policy or business rule, or one of several meaningfully different behaviors? Answer no when the work is fixing a "
    "reported problem so things work as intended, investigating, checking, running, testing, deploying, publishing, "
    "restarting, processing a named file with stated parameters, following a standing procedure, or applying a change the "
    "user described concretely or the agent already proposed."}}
# ponytail: calibrated on the author's own messages: 100 labeled to choose the question and threshold, 100 fresh ones held
# out (must-ask scored 0.85-0.96; wrongly closed 1 of 42, wrongly opened 0 of 5). Re-check on your own traffic.
NEEDS_THRESHOLD = 0.8
PROFILE = os.path.expanduser("~/.config/lean-forge/profile.txt")  # optional, private: how this user instructs agents


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
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                              "User-Agent": "lean-forge"})  # the API's edge blocks Python-urllib's default UA (403, error 1010)
        with urllib.request.urlopen(req, timeout=4) as r:
            return json.load(r)["answers"][name]["noul"]
    except Exception:
        return None


def needs_decision(prompt, agent):
    """Probability that the request leaves a user-visible decision open, judged with the conversation and the user's habits."""
    state = {"agent_last_message": agent[-3000:], "user_new_message": prompt[:4000]}
    try:
        state["about_this_user"] = open(PROFILE).read().strip()[:2000]
    except OSError:
        pass
    return jev(state, NEEDS_Q, "needs_decision")


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
        if "<task-notification>" in inp.get("prompt", ""):
            return  # a background-task notice, not a user request: the gate keeps its state
        prompt = inp.get("prompt", "")
        agent = last_agent_message(inp.get("transcript_path", "")) if st.get("prompt_at") else ""
        p = needs_decision(prompt, agent)
        if p is None:  # Jev unavailable: only a message after an asking turn counts as its answer; otherwise the hatch
            opened = st.get("state") == "asked"
        else:  # continuing, approving or correcting the agent's plan, fixes and runs stay open; open-ended new work asks
            opened = p < NEEDS_THRESHOLD
        st = {"state": "open" if opened else "closed", "prompt_at": now, "jev": p, "hatch": p is None}

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
        used_hatch = (st.get("hatch", True) and os.path.exists(mech)  # a marker the gate refused (Jev answered) is not a used hatch
                      and os.path.getmtime(mech) >= st.get("prompt_at", 0))
        if st.get("state") == "closed" and not used_hatch:
            st["state"] = "asked"

    json.dump(st, open(sp, "w"))


main()
