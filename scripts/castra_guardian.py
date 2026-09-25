#!/usr/bin/env python3
"""Local command classifier: known hazardous patterns and authorization reminders.

A heuristic floor, not a sandbox, full shell parser, or model policy replica.
Exit codes: 0 ordinary; 1 existing authority required; 2 platform confirmation; 3 deny.
"""
import argparse, json, re, sys

# git 과 하위 명령 사이의 전역 옵션(-C 경로, -c 설정=값 등)은 건너뛴다 — `git -C repo push --force` 도 강제 푸시다
GIT = r"\bgit(?:\s+(?:-C|-c|--git-dir|--work-tree|--namespace)\s+\S+|\s+--[\w-]+(?:=\S+)?|\s+-[pP])*\s+"

# (정규식, 등급, 사유) — 위에서부터 먼저 맞는 것이 이긴다
RULES = [
    # hand_off: 에이전트가 최종 실행을 하지 않는다
    (GIT + r"push\b.*(--force\b|-f\b)",        "hand_off", "강제 푸시는 원격 히스토리를 되돌릴 수 없게 덮어쓴다"),
    (GIT + r"filter-(repo|branch)\b",          "hand_off", "히스토리 재작성"),
    (r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b",      "hand_off", "스키마 삭제"),
    (r"\bTRUNCATE\s+TABLE\b",                    "hand_off", "테이블 전체 삭제"),
    (r"\b(mkfs|fdisk|diskutil\s+erase)\b",       "hand_off", "디스크 포맷"),
    (r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\s+/(\s|$)", "hand_off", "루트 삭제"),
    # `getent passwd`·`/etc/passwd` 는 계정 정보를 읽을 뿐이다
    (r"(?<!getent )(?<![/\w.-])passwd\b(?![-.\w])|\bsecurity\s+add-generic-password\b", "hand_off", "자격증명 변경"),

    # confirm_at_action: 미리 승인받았어도 실행 시점에 다시 확인
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?\b",         "confirm_at_action", "재귀 삭제는 복구가 어렵다"),
    (GIT + r"reset\s+--hard\b",                "confirm_at_action", "미커밋 변경 소실"),
    (GIT + r"clean\s+-[a-zA-Z]*[fd]",          "confirm_at_action", "추적되지 않은 파일 삭제"),
    (r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)",        "confirm_at_action", "WHERE 없는 DELETE"),
    (r"\bUPDATE\b(?!.*\bWHERE\b).*\bSET\b",      "confirm_at_action", "WHERE 없는 UPDATE"),
    (r"curl[^|]*\|\s*(sudo\s+)?(ba)?sh",         "confirm_at_action", "원격 스크립트 즉시 실행"),
    (r"\bsudo\b",                                "confirm_at_action", "권한 상승"),
    (r"\bchmod\s+(-R\s+)?777\b",                 "confirm_at_action", "권한 전면 개방"),
    (r"\b(launchctl|systemctl)\s+(disable|unload)\b", "confirm_at_action", "서비스 비활성화"),
    (r"\btccutil\s+reset\b",                     "confirm_at_action", "보안 권한 초기화"),
    (r"\bnpm\s+publish\b|\bgh\s+release\s+create\b", "confirm_at_action", "외부 배포"),

    # pre_approval: 세션에서 구체적으로 승인했으면 진행
    (GIT + r"push\b",                          "pre_approval", "원격 반영"),
    (r"\bgh\s+pr\s+(create|merge)\b",            "pre_approval", "PR 생성·병합"),
    (r"\b(mail|sendmail|slack)\b.*\bsend\b",     "pre_approval", "외부 발송"),
    (r"\bbrew\s+(install|upgrade)\b|\bnpm\s+i(nstall)?\s+-g\b", "pre_approval", "소프트웨어 설치"),
    (r"\bdocker\s+(rm|rmi|system\s+prune)\b",    "pre_approval", "컨테이너·이미지 삭제"),
    (GIT + r"(commit|add)\b",                  "pre_approval", "커밋"),

    # 시크릿 노출 — security.md: .env 계열은 읽어서 출력 금지. POSIX 셸은 정규식이 아니라
    # _reads_env()가 명령별 파일 인자로 판정한다(`process.env` 검색·파일 이름 확인·본문 속 단어는 제외).
    # 비밀키·자격증명 파일 출력도 같은 방식으로 _reads_keyfile()이 판정한다.
    (GIT + r"add\s+(\.|-A|--all)(\s|$)",
     "confirm_at_action", "security.md: git add . / -A 금지, 파일을 명시하라"),

    # PowerShell — 윈도우에서 Git Bash 가 없으면 셸이 PowerShell 로 떨어진다.
    # 같은 위험이 전혀 다른 표기로 들어오므로 POSIX 규칙이 하나도 걸리지 않는다.
    (r"\bFormat-Volume\b|\bClear-Disk\b|\bInitialize-Disk\b",
     "hand_off", "디스크 포맷"),
    (r"\bSet-ExecutionPolicy\b",
     "hand_off", "스크립트 실행 정책 변경"),
    (r"\bRemove-Item\b[^|;]*(-Recurse|-r\b)[^|;]*(-Force|-f\b)|"
     r"\bRemove-Item\b[^|;]*(-Force|-f\b)[^|;]*(-Recurse|-r\b)",
     "confirm_at_action", "재귀 삭제는 복구가 어렵다"),
    (r"\b(iwr|irm|Invoke-WebRequest|Invoke-RestMethod)\b[^|;]*\|\s*(iex|Invoke-Expression)\b",
     "confirm_at_action", "원격 스크립트 즉시 실행"),
    (r"\bStop-(Service|Process)\b|\bSet-Service\b[^|;]*-StartupType\s+Disabled\b",
     "confirm_at_action", "서비스·프로세스 중단"),
    (r"\bStart-Process\b[^|;]*-Verb\s+RunAs\b",
     "confirm_at_action", "권한 상승"),
    # PowerShell 의 .env 읽기(Get-Content·gc·type)도 _reads_env()가 명령 자리만 보고 판정한다.
]

# 시크릿 노출 위험 (등급과 별개로 항상 경고)
SECRET_HINTS = [
    (r"\.env\b",                       "환경변수 파일"),
    (r"\b(sk|re|npg|ghp|xox[baprs])[-_][A-Za-z0-9]{8,}", "API 키 형태 문자열"),
    (r"postgres(ql)?://[^\s]+:[^\s]+@", "DB 접속 문자열"),
    (r"\bcat\b.*\b(id_rsa|\.pem|credentials)\b", "비밀키 출력"),
]

ORDER = {"hand_off": 3, "confirm_at_action": 2, "pre_approval": 1, "not_required": 0}
EXIT = {"hand_off": 3, "confirm_at_action": 2, "pre_approval": 2, "not_required": 0}

ACTION = {
    "hand_off": "사용자가 직접 실행해야 한다. 에이전트가 최종 단계를 수행하지 않는다.",
    "confirm_at_action": "실행 직전에 확인을 받아라. 사전 승인이 있어도 다시 확인한다.",
    "pre_approval": "세션에서 이 행위를 구체적으로 승인했으면 진행하고, 아니면 직전에 확인하라.",
    "not_required": "확인 없이 진행한다.",
}


# 인자를 읽거나 출력만 하고 실행하지는 않는 명령. 실행기로 파이프되지 않는 한 이 명령의 구간은
# 위험 규칙에서 뺀다 — 위험한 단어를 "검색하는 일"과 "실행하는 일"을 가르기 위한 것이다.
INERT = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "echo", "printf"}

ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _split_segments(cmd: str):
    """따옴표 안을 건드리지 않고 셸 구분자로 명령줄을 나눈다."""
    segments, buf = [], []
    quote = None
    i = 0
    while i < len(cmd):
        ch = cmd[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < len(cmd):
                buf.append(cmd[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
        elif ch in "|;&\n":
            segments.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    segments.append("".join(buf))
    return [s for s in (seg.strip() for seg in segments) if s]


def _head_command(segment: str) -> str:
    """구간의 실행 파일 이름. 앞에 붙은 환경변수 대입은 건너뛴다."""
    for word in segment.split():
        if ENV_ASSIGN.match(word):
            continue
        return word.rsplit("/", 1)[-1]
    return ""


ENV_READERS = {"cat", "less", "more", "head", "tail", "bat", "open", "grep", "egrep", "fgrep", "rg",
               "get-content", "gc", "type"}   # 뒤의 셋은 PowerShell·cmd
PATTERN_FIRST = {"grep", "egrep", "fgrep", "rg"}   # 첫 번째 위치 인자는 파일이 아니라 검색어
ENV_FILE = re.compile(r"(^|\.)env(\.[^/]*)?$")      # .env, .env.local, prod.env — process.environment 는 아님
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1")
# 스크립트 안에서 .env 를 여는 호출 — here-document 본문까지 본다(본문의 open()은 실제로 실행된다)
OPEN_ENV = re.compile(r"\bopen\(\s*[rbfu]?(['\"])(?:[^'\"]*/)?[^'\"/]*\.env(?:\.[^'\"/]*)?\1")


SUBST = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")
SHELL_FED = re.compile(r"\b(ba|z|da)?sh\b[^<|;&]*<<")   # bash <<'SH' 의 본문은 실행되는 명령이다


def _strip_heredocs(cmd: str) -> str:
    """here-document 본문은 데이터라서 지우고 명령 줄만 남긴다. 셸로 넘기는 본문은 명령이라 남긴다."""
    out, end = [], None
    for line in cmd.split("\n"):
        if end is not None:
            if line.strip() == end:
                end = None
            continue
        out.append(line)
        m = HEREDOC.search(line)
        if m and not SHELL_FED.search(line):
            end = m.group(2)
    return "\n".join(out)


def _reader_calls(cmd: str):
    """(명령 이름, 파일 인자) — here-document 본문을 빼고, $(…)·`…` 안의 명령까지 편다."""
    import shlex
    body = _strip_heredocs(cmd)
    # $(…)·`…` 안의 명령도 실행된다 — 값이 변수로 들어가 나중에 출력될 수 있다
    for m in SUBST.finditer(body):
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        if inner.strip() and inner != cmd:
            yield from _reader_calls(inner)
    for seg in _split_segments(body):
        try:
            words = shlex.split(seg)
        except ValueError:
            words = seg.split()
        while words and ENV_ASSIGN.match(words[0]):
            words = words[1:]
        if not words:
            continue
        head = words[0].rsplit("/", 1)[-1].lower()
        args = [w for w in words[1:] if not w.startswith("-")]
        if head in PATTERN_FIRST and not any(w in ("-e", "-f") or w.startswith("--regexp") for w in words[1:]):
            args = args[1:]
        yield head, args


def _reads_env(cmd: str) -> bool:
    """읽기·출력 명령이 .env 계열 파일을 인자로 받는가."""
    if OPEN_ENV.search(cmd):
        return True
    return any(head in ENV_READERS and any(ENV_FILE.search(a.rstrip("/").rsplit("/", 1)[-1]) and ".env" in a for a in args)
               for head, args in _reader_calls(cmd))


KEY_READERS = {"cat", "less", "more", "head", "tail", "bat"}
KEY_FILE = re.compile(r"^id_(rsa|dsa|ecdsa|ed25519)$|\.pem$|^credentials(\.json)?$")


def _reads_keyfile(cmd: str) -> bool:
    """출력 명령이 비밀키·자격증명 파일을 인자로 받는가."""
    return any(head in KEY_READERS and any(KEY_FILE.search(a.rstrip("/").rsplit("/", 1)[-1]) for a in args)
               for head, args in _reader_calls(cmd))


# 명령으로 실행되는 본문을 받는 실행기. 여기로 넘어가는 here-document·파이프 입력은 데이터가 아니다.
SHELLS = {"sh", "bash", "zsh", "dash"}
SQL_RUNNERS = {"psql", "sqlite3", "mysql"}
REMOTE_RUNNERS = {"ssh", "powershell", "pwsh"}
EXECUTORS = SHELLS | SQL_RUNNERS | REMOTE_RUNNERS | {"eval", "xargs", "python", "python3", "node"}
SCRIPT_RUNNERS = re.compile(r"\b(python3?|node|deno|ruby|perl)\b[^<|;&]*<<")
RUNS_COMMAND = re.compile(r"subprocess|os\.system|os\.popen|child_process|execSync|spawnSync|\bexec\(")


MISSPLIT = re.compile(r"\$\(|`|\n|;|&&|\|\|")
WRITES_TO = re.compile(r"(?:>>?|\btee\s+(?:-a\s+)?)\s*(['\"]?)([^\s'\"<>|;&]+)\1[^<]*<<")


def _command_view(cmd: str) -> str:
    """위험 규칙을 적용할 부분만 남긴다: 실행되지 않는 here-document 본문과 주석 줄을 뺀다.

    셸·SQL·원격 실행기로 넘기는 본문은 그대로, 스크립트 실행기로 넘기는 본문은 명령을 실행하는 줄만 남긴다.
    파일로 쓰는 본문은 그 파일 이름이 같은 명령의 다른 곳(실행·복사·등록)에 다시 나오면 명령으로 본다.
    """
    lines, bodies, end = [], [], None     # bodies: [파일 이름 또는 None, 남길 방식, 본문 줄]
    for line in cmd.split("\n"):
        if end is not None:
            if line.strip() == end:
                end = None
            else:
                bodies[-1][2].append(line)
            continue
        if line.lstrip().startswith("#"):
            continue
        lines.append(line)
        m = HEREDOC.search(line)
        if m:
            end = m.group(2)
            heads = {_head_command(s) for s in _split_segments(line[:m.start()])}
            # $(…) 안에서 시작한 본문은 출력이 다른 명령(원격 실행 등)에 쓰인다 — 명령으로 본다
            keep = "all" if heads & (SHELLS | SQL_RUNNERS | REMOTE_RUNNERS) or "$(" in line[:m.start()] else \
                   "calls" if SCRIPT_RUNNERS.search(line) else None
            w = WRITES_TO.search(line)
            name = w.group(2).rsplit("/", 1)[-1] if w and w.group(2) not in ("/dev/null",) else None
            bodies.append([name, keep, []])
    # 쓴 파일이 나중에 쓰이면(다른 본문 속 언급 포함) 그 본문도 명령이다 — 더 늘지 않을 때까지 반복
    shown = "\n".join(l for l in lines if not HEREDOC.search(l))
    changed = True
    while changed:
        changed = False
        for b in bodies:
            if b[0] and b[1] != "all" and re.search(r"(^|[^\w.-])" + re.escape(b[0]) + r"($|[^\w.-])", shown):
                b[1] = "all"; changed = True
                shown += "\n" + "\n".join(b[2])
    out = list(lines)
    for name, keep, body in bodies:
        out += body if keep == "all" else [l for l in body if keep == "calls" and RUNS_COMMAND.search(l)]
    return "\n".join(out)


def classify(cmd: str) -> dict:
    view = _command_view(cmd)
    segments = _split_segments(view)

    def piped_into_executor(seg):
        m = re.search(re.escape(seg) + r"\s*\|\s*(?:sudo\s+)?(\S+)", view)
        return bool(m) and m.group(1).rsplit("/", 1)[-1] in EXECUTORS

    # grep·echo 는 인자를 찾거나 보여줄 뿐이다 — 실행기로 파이프되지 않는 한 그 구간은 규칙에서 뺀다.
    # 구간 안에 $(…)·`…`·줄바꿈·구분자가 남아 있으면 따옴표를 잘못 따라간 것일 수 있으니 빼지 않는다.
    kept = [s for s in segments
            if _head_command(s) not in INERT or MISSPLIT.search(s) or piped_into_executor(s)]
    ignored = len(kept) < len(segments)
    scan = "\n".join(kept)
    verdict, reasons = "not_required", []
    if _reads_env(cmd):
        verdict = "hand_off"
        reasons.append({"grade": "hand_off", "reason": "security.md: .env 파일은 읽어서 출력하지 않는다",
                        "matched": "_reads_env"})
    if _reads_keyfile(cmd):
        verdict = "hand_off"
        reasons.append({"grade": "hand_off", "reason": "비밀키·자격증명 출력", "matched": "_reads_keyfile"})
    for pat, grade, why in RULES:
        # 파이프를 가로지르는 규칙(curl … | sh)만 명령줄 전체에, 나머지는 명령 구간마다 적용한다
        targets = [view] if r"\|" in pat else kept
        if any(re.search(pat, t, re.IGNORECASE) for t in targets):
            reasons.append({"grade": grade, "reason": why, "matched": pat})
            if ORDER[grade] > ORDER[verdict]:
                verdict = grade
    secrets = [w for pat, w in SECRET_HINTS if re.search(pat, scan, re.IGNORECASE)]
    return {
        "command": cmd,
        "verdict": verdict,
        "action": ACTION[verdict],
        "reasons": reasons,
        "secret_risk": secrets,
        "exit_code": EXIT[verdict],
        "quoted_args_ignored": ignored,
    }


def render(r: dict):
    mark = {"hand_off": "HAND-OFF", "confirm_at_action": "CONFIRM",
            "pre_approval": "PRE-APPROVAL", "not_required": "OK"}[r["verdict"]]
    print(f"[{mark}] {r['command']}")
    print(f"  → {r['action']}")
    for x in r["reasons"]:
        print(f"  · {x['grade']}: {x['reason']}")
    for s in r["secret_risk"]:
        print(f"  ! 시크릿 위험: {s} — 값을 출력하거나 커밋에 넣지 마라")


def main():
    p = argparse.ArgumentParser(prog="castra_guardian", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", nargs="?", default="")
    p.add_argument("--json", action="store_true")
    p.add_argument("--stdin", action="store_true", help="여러 줄 입력을 각각 판정")
    a = p.parse_args()

    cmds = [l.strip() for l in sys.stdin if l.strip()] if a.stdin else ([a.command] if a.command else [])
    if not cmds:
        p.error("명령을 인자나 --stdin 으로 주어라")

    results = [classify(c) for c in cmds]
    if a.json:
        print(json.dumps(results if len(results) > 1 else results[0], ensure_ascii=False, indent=2))
    else:
        for r in results:
            render(r)
    sys.exit(max(r["exit_code"] for r in results))


if __name__ == "__main__":
    main()
