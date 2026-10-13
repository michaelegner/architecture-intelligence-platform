# AIP v0.8.0 — Distributed System Candidate Evaluation, Round 2

**Status:** Completed  
**Target:** v0.8.0 product-boundary PoC preparation  
**Input:** Round 1 candidate longlist  
**Scope authority:** ROADMAP.md — v0.8 product-boundary validation

## 1. Purpose

Round 2 SHALL reduce the Round 1 longlist to a small set of systems that are genuinely suitable for the v0.8 comparison.

The focus is **architecture fitness**, not popularity or technology preference.

## 2. Evaluation question

For each candidate, answer:

> **Is there a realistic bounded change where an important distributed relationship matters, but that relationship is not simply equivalent to a direct source-code dependency?**

The candidate should remain interesting even when a strong coding agent receives all relevant repositories and existing agent-readable context such as `CLAUDE.md` or `AGENTS.md`.

## 3. What to inspect

For each candidate, inspect only enough architecture and source/configuration to determine:

- the main synchronous and asynchronous service relationships;
- one plausible bounded change, preferably around order, payment, inventory, fulfillment, or an event/API contract;
- which external services/components should be investigated for that change;
- how those relationships are represented in source code;
- whether runtime, broker, deployment, gateway, service-discovery, or configuration evidence could establish something materially different;
- whether the system is realistically runnable for a later PoC.

Coding-agent-native repositories are a plus because they provide a stronger baseline, not because they favor AIP.

## 4. Candidate record

| Field | Content |
|---|---|
| Candidate | Project |
| Bounded change | One concrete task |
| Relevant distributed relationship | What crosses the boundary |
| Source visibility | Direct / indirect / unclear |
| Independent evidence | Runtime, broker, deployment, gateway, config, etc. |
| Agent context | CLAUDE.md / AGENTS.md / none |
| PoC practicality | Good / possible / poor |
| Verdict | Keep / maybe / reject |
| Reason | One or two sentences |

No Teamscale installation or full AIP integration is required in Round 2.

## 5. Keep / reject rule

**Keep** a candidate when there is a credible chance that independent distributed evidence changes the investigation boundary beyond what strong multi-repository source analysis can safely establish.

**Reject** candidates where:

- the interesting relationship is already an obvious direct source dependency;
- the scenario only works by withholding relevant source from the baseline;
- there is no meaningful bounded change;
- independent Current-State evidence is unavailable or artificial;
- the system is too difficult or fragile to reproduce.

Do not reject merely because the project is little known or uses a particular messaging technology.

## 6. Exit criteria

Round 2 is complete when the Round 1 list has been reduced to approximately **5–8 strong candidates**.

For every survivor, the result SHALL state:

> the bounded change, the relevant distributed relationship, why source analysis may be insufficient, and what independent evidence could establish the relationship.

These survivors become the input for Round 3.
