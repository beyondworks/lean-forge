"""One-time exact-command confirmation for Codex, which has no PreToolUse ask decision."""
import hashlib
import secrets
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(HERE.parent / "scripts"))
import castra_runtime as runtime


def command_hash(command):
    return hashlib.sha256(command.encode("utf-8")).hexdigest()


def request(payload, command, reason):
    session, cwd = payload.get("session_id"), payload.get("cwd")
    if not isinstance(session, str) or not isinstance(cwd, str):
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": "Castra cannot bind approval to a Codex session; command denied."}}
    token = secrets.token_hex(6)
    with runtime.locked(cwd, session) as state:
        state["codex_approval"] = {"token": token, "cwd": runtime.canonical(cwd, cwd),
                                   "command_sha256": command_hash(command),
                                   "expires_at": time.time() + 900, "approved": False}
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": f"{reason} To authorize this exact command once, ask the user to reply exactly: APPROVE {token}."}}


def approve(payload, token):
    session, cwd = payload.get("session_id"), payload.get("cwd")
    if not isinstance(session, str) or not isinstance(cwd, str):
        return False
    accepted = False
    with runtime.locked(cwd, session) as state:
        item = state.get("codex_approval", {})
        if item.get("token") == token and item.get("expires_at", 0) >= time.time():
            item["approved"] = True
            accepted = True
    return accepted


def consume(payload, command):
    session, cwd = payload.get("session_id"), payload.get("cwd")
    if not isinstance(session, str) or not isinstance(cwd, str):
        return False
    accepted = False
    with runtime.locked(cwd, session) as state:
        item = state.get("codex_approval", {})
        if (item.get("approved") is True and item.get("cwd") == runtime.canonical(cwd, cwd)
                and item.get("expires_at", 0) >= time.time()
                and secrets.compare_digest(item.get("command_sha256", ""), command_hash(command))):
            state.pop("codex_approval", None)
            accepted = True
    return accepted
