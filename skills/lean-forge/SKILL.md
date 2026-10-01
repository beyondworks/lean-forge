---
name: lean-forge
description: Apply lean-forge's SETTLE, BUILD, PROVE and REPORT workflow in Codex or ChatGPT Work. Use when the user invokes lean-forge or explicitly asks for its workflow.
argument-hint: "[settle|build|prove|review] [request]"
---

Apply lean-forge to the supplied request: $ARGUMENTS. The plugin's lifecycle hooks add enforcement and session evidence in supported Codex hosts after the user reviews and trusts them. Do not claim those controls are active in ordinary ChatGPT or in an untrusted/uninstalled plugin session.

## SETTLE

Resolve only decisions that materially change what the user will see or rely on and that are not settled by the request, conversation, or project source. Treat a proposed cause as a hypothesis until an observation distinguishes it. If a material decision remains, ask once with a recommendation and boundary example; otherwise start work.

## BUILD

Translate settled requirements into the smallest meaningful acceptance checks, then implement the smallest complete change with existing code and platform features. Preserve user work. Avoid extra plans, abstractions, dependencies, branches, commits, or reviewers unless the risk or scope warrants them.

## PROVE

Run checks that would fail for the changed behavior and connect evidence to the explicit changed files. A successful process exit or build alone does not establish semantic or runtime correctness. Distinguish source, build, installed, running, and production outcomes. Castra records scoped evidence; do not claim a check was automatically tracked unless the hook did so.

## REPORT

Report what changed, decisive evidence, concrete unverified boundaries, and where the result reached. Never claim hooks, ledgers, permission prompts, or model parity that were not observed.

Modes: `settle` resolves open decisions; `build` implements and verifies; `prove` checks without editing unless asked; `review` reports findings without editing unless asked.
