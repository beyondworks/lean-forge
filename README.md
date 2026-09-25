# lean-forge

**Ask what matters. Build the least. Prove it ran.**

One Claude Code plugin that settles the decisions a result depends on before any file is touched,
builds the smallest thing that satisfies them, and closes every edit with evidence.
It carries its own copies of [Castra](https://github.com/beyondworks/castra) and
[Ponytail](https://github.com/DietrichGebert/ponytail), and adds a questioning phase that a hook enforces —
so there is nothing else to install and nothing to choose between.

[![release](https://img.shields.io/github/v/release/beyondworks/lean-forge?label=release)](https://github.com/beyondworks/lean-forge/releases)
![license](https://img.shields.io/badge/license-MIT-black)
![claude code](https://img.shields.io/badge/Claude%20Code-plugin-6f4ad2)

[한국어](README.ko.md)

---

## The idea

Coding agents fail in two opposite ways.

- **Fast harnesses guess.** Told to keep moving, the agent fills every open question with a plausible
  default: English CSV headers the accountant never asked for, an invoice number format nobody approved,
  the user's own wrong diagnosis ("it's probably `round()`") taken as the cause.
- **Thorough harnesses pay for ceremony.** They ask the right questions — and then spend most of their
  time on contract documents, review subagents and branch-and-commit workflows.

The accuracy comes from the questions, asked in the first minutes, not from the ceremony that follows.
The fast harness is fast because it never asks.

lean-forge keeps the questions and drops the ceremony — and it does not trust a prompt to keep the
questions alive. A hook closes file edits until the outcome-changing decisions are settled.
Rules written only as text were followed in 4 of 10 cases; enforced by a hook, in every case.

---

## One flow for every request

```mermaid
flowchart LR
    R([request]) --> J{"Jev: does it need a<br/>decision nobody settled?"}
    J -- "no: continue, fix,<br/>run, stated change" --> B
    J -- "yes" --> S["<b>SETTLE</b><br/>reproduce the symptom<br/>ask with boundary examples<br/>'any other rule?'"]
    S -- "user answers" --> B["<b>BUILD</b><br/>confirmed rules → tests first<br/>smallest change that passes"]
    B --> P["<b>PROVE</b><br/>run the check that would fail<br/>on the defect, tie it to the file"]
    P --> T(["<b>REPORT</b><br/>result · evidence · unverified<br/>where it reached"])
    P -. "edit again" .-> B
```

| Phase | What happens | Enforced by |
|---|---|---|
| **SETTLE** | A cause the user suggests is a hypothesis: reproduce it. List the decisions the result must answer (structure, behavior, contract, technical). Ask once, at most five items, each with a recommendation and a worked example at a boundary value, and end with *"any other rule you hold?"* | Edits stay closed until the user answers. An independent classifier (Jev), reading the agent's last message too, opens them at once when nothing user-visible is left to decide: continuing or approving the plan, fixing a reported problem, running, a stated change. |
| **BUILD** | Each confirmed rule becomes an acceptance test with its reason in one line. Then the Ponytail ladder: does it need to exist → stdlib → native → installed dependency → one line → minimum code. | Ponytail rules, injected every session |
| **PROVE** | Every edited file is tracked as unverified until a check is explicitly tied to it; editing again voids the evidence. | Castra ledger: ending a turn with unverified edits is blocked |
| **REPORT** | What changed, the decisive evidence, what was not verified, and where the change reached: source, installed build, running service, production. | Castra execution contract |

Questions happen only in SETTLE. From BUILD on, the agent never stalls — the two speed rules that used
to fight each other ("don't stall" and "ask first") now live in different phases.

---

## How SETTLE is enforced

```mermaid
stateDiagram-v2
    direction LR
    state judge <<choice>>
    [*] --> judge: user message
    judge --> open: Jev < 0.8 (nothing left to decide)
    judge --> closed: Jev ≥ 0.8 (a user-visible decision is open)
    closed --> asked: turn ends without edits (the agent asked)
    asked --> judge: next message
    open --> judge: next message
    closed --> open: Jev unavailable and the agent writes a one-line reason
    note right of closed
        Edit / Write / MultiEdit / NotebookEdit
        are denied while closed
    end note
```

The classifier is [Jev](https://docs.typesafe.ai), a small model that returns a probability instead of
text. One call costs about 0.7 s. At every user message it is given that message and the agent's last
message, and asks one question: *to carry this out, must the agent choose something the user will see or
rely on that nothing has settled yet?* Without a key, or if Jev does not answer, a message after an asking
turn counts as its answer, and a mechanical edit needs a one-line written reason.

Up to v2.0.4 the gate judged each message alone, asking whether it *literally fixed the result*. A
two-word go-ahead ("진행해줘", "go ahead") after a working turn never does, so it closed edits in the
middle of agreed work. On the author's own messages (4,534 from 298 sessions):

| Fresh sample of 100 (threshold chosen on a separate 100) | Wrongly closed | Wrongly opened |
|---|---|---|
| v2.0.4 rule, after a working turn | 42 of 42 | 0 of 5 |
| **v2.0.5 rule** | **1 of 42** | **0 of 5** |

The rest of the sample were questions and checks, where either answer is harmless.

**Your own habits (optional).** The gate reads `~/.config/lean-forge/profile.txt` if it exists: a short
plain-text note on how you instruct agents (your usual go-ahead phrases, your standing procedures). It is
sent to Jev with each judgment and nowhere else; keep it out of any repository. Without it the gate still
works; on the author's data the note removed three of five wrong closes on the tuning sample.

---

## What is inside

```mermaid
flowchart TB
    subgraph LF["lean-forge (one plugin)"]
        direction TB
        F["forge.py<br/>SETTLE gate + Jev triage"]
        subgraph C["Castra 0.9.1 (vendored)"]
            C1["evidence ledger<br/>trace · verify · stop gate"]
            C2["execution contract"]
            C3["guardian<br/>risky commands"]
            C4["release gate<br/>CI of the exact commit"]
            C5["checkpoints · budget · /castra modes"]
        end
        subgraph P["Ponytail 4.5.0 (vendored)"]
            P1["ladder & rules"]
            P2["review · audit · debt · help"]
        end
    end
```

| Part | Kept from the original | Changed |
|---|---|---|
| Castra | Everything: per-file evidence ledger, execution contract, guardian (force push, `DROP`, reading `.env` are handed to the user; `rm -rf`, `reset --hard`, `sudo`, publishing ask first), release gate, checkpoints, budget advisory, `/castra` modes | nothing |
| Ponytail | Everything: ladder, rules, `/ponytail lite\|full\|ultra`, four skills | one sentence: *"ship the lazy version and question it … never stall"* now applies **after** SETTLE |

---

## Results

Eight tasks on a small Python invoicing library, 36 hidden tests. A scripted user (Claude Sonnet)
answered every harness from the same intent file. Model: Claude Opus 5 for every agent. Cost is the
API-price equivalent of the tokens used.

**No other harness loaded**

| Harness | Hidden tests passed | Time | Cost |
|---|---|---|---|
| Castra + Ponytail | 15/36 | 10 min | $3.79 |
| **lean-forge** (2 runs) | **31/36 · 36/36** | **18 min** | **$5.2** |

**Is the difference real?** The hidden tests of one task are not independent, so each task is one cluster: paired
per-task differences, their mean with a 95% confidence interval, and a sign test (as recommended by
[Miller 2024](https://arxiv.org/abs/2411.00640)).

| lean-forge − Castra + Ponytail (8 tasks) | Difference | 95% CI | Sign test |
|---|---|---|---|
| Task pass rate (0.94 vs 0.47) | **+0.46** | +0.17 to +0.76 | p = 0.031 |
| Share of runs passing every hidden test (0.94 vs 0.25) | **+0.69** | +0.30 to +1.07 | p = 0.031 |
| Time per task (2.3 vs 1.2 min) | +1.1 min | +0.5 to +1.6 | p = 0.070 |
| Cost per task ($0.65 vs $0.47) | +$0.18 | +0.05 to +0.31 | p = 0.070 |

Accuracy is clearly higher; it costs about a minute and $0.18 more per task.

On the author's full personal setup (other plugins, hooks and memory loaded; 7 tasks) the direction was the same
(task pass rate 0.96 vs 0.57, +0.39, 95% CI −0.05 to +0.82), but not conclusive at this size; time and cost did not differ.

On Claude Opus 5.5 (Claude Code 2.1.280, effort medium, 3 runs per task): 0.75 with no harness, 0.97 with lean-forge
(+0.23, 95% CI −0.04 to +0.49).

*Up to v2.0.3 this README pooled the 36 hidden tests as if independent and reported Fisher's test as "p < 0.001", which
overstates significance. Corrected in v2.0.4.*

- 6 of lean-forge's 8 missed tests came from two runs where the scripted user answered against its own
  intent file (it approved a wrong number format, and waved off a question the file answered). The agent
  had asked the right question both times. The other 2 were one rounding boundary every harness missed
  at least once.
- Every file lean-forge edited ended *verified* in the Castra ledger, and the stop gate never had to
  fire (0 of 30 runs; the Castra + Ponytail pair needed it in 7 of 8).

Everything needed to rerun it is in [`bench/`](bench/): tasks, intent files, hidden tests, fixtures,
the runner, and per-run numbers ([`bench/results-summary.csv`](bench/results-summary.csv)).

```bash
cd bench
python3 run.py G t1 1          # lean-forge on task t1, run 1
python3 significance.py        # compare with the recorded results
```

---

## Install

```text
/plugin marketplace add beyondworks/lean-forge
/plugin install lean-forge@lean-forge
```

Requirements: `python3`, `node`, `git`. Optional: a TypeSafe key for Jev, as the environment variable
`TYPESAFE_API_KEY` or a macOS keychain item of that name.

If you already run Castra hooks from `settings.json` or the Ponytail plugin, turn them off — lean-forge
contains both, and the same hooks would run twice.

## Use

There is nothing to call. Make requests as usual:

- A request whose result is fully stated goes straight through, and so does a go-ahead, an approval or a
  correction of the plan the agent proposed.
- Anything else gets one message of questions first. Answer it and the work continues without stopping.
- `/castra review · verify · reframe · finish · resume · status` and `/ponytail lite | full | ultra`
  work as they do in the originals.

Self-tests:

```bash
python3 hooks/test_forge.py    # SETTLE gate, with and without Jev
python3 hooks/test_bundle.py   # guardian, release gate, session contract, evidence ledger, Ponytail
```

---

## Limits

- One small repository and eight tasks; the older harnesses ran once per task. Large codebases,
  multi-module changes and verification on real screens or installed apps were not part of the
  benchmark; the guardian, release gate and ledger are covered by `hooks/test_bundle.py` instead.
- The scripted user is itself a model and made mistakes (above).
- The SETTLE gate watches the edit tools. A file written through the shell passes it, as it passes
  Castra's ledger.
- The Jev threshold (0.8) was set on one person's messages (100 to tune, 100 held out). Tune it on your own traffic.

## Credits

- [Castra](https://github.com/beyondworks/castra) 0.9.1 — MIT, vendored with the guardian's matching narrowed: rules apply to what a command runs, not to words in data (here-document bodies written to files, searches, comments), and `git -C …` no longer hides a subcommand ([license](vendor-licenses/castra-LICENSE))
- [Ponytail](https://github.com/DietrichGebert/ponytail) 4.5.0 by Dietrich Gebert — MIT, vendored with one sentence changed ([license](vendor-licenses/ponytail-LICENSE))
- [Jev](https://docs.typesafe.ai) by TypeSafe — external API

MIT © beyondworks
