# ADR-002: LangGraph state machine over CrewAI or a raw agent loop

**Status:** accepted
**Date:** 2026-06-13

## Context

The triage agent runs multiple LLM and non-LLM steps with one parallel fan-out, against attacker-controlled input, with a hard cost ceiling. Candidates: a free-running tool-use loop, CrewAI-style role agents, or an explicit LangGraph state machine.

## Decision

LangGraph `StateGraph` over a typed Pydantic state. Fixed topology, no cycles; the only dynamism is a single in-node escalation retry.

## Tradeoffs

- Gain: bounded execution by construction (an injected "keep going" cannot add steps); every node is a plain async function unit-testable with fakes; typed state catches shape bugs at the boundary; built-in parallel fan-out/join; Postgres checkpointing for resume.
- Give up: the flexibility of letting the model decide its own tool sequence — deliberately, since that flexibility is the attack surface; CrewAI's multi-agent ergonomics, which solve a problem we don't have (one pipeline, not negotiating agents).
- Raw loop rejected: would reimplement state merging, retries, checkpointing, and still lack static topology guarantees.
- Revisit if: triage needs genuinely dynamic plans (e.g. iterative repo exploration), where a constrained tool-use sub-loop inside one node would be added rather than unbounding the whole graph.
