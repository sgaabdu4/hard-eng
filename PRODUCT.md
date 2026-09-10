# Hard Eng

Hard Eng is a repository-local scaffold that adds shared engineering instructions, tool configuration and project checks to existing repositories.

## Register

Developer tooling.

## Users

Developers and coding agents working in existing projects.

## Problem

Projects need consistent engineering instructions and checks that report real failures before work is treated as complete.

## Product Purpose

Install project-specific guidance and native checks, then validate evidence before work is treated as complete. [README](README.md) lists capabilities; [DECISION](DECISION.md#current-status) separates implemented behavior, observed proof and remaining acceptance.

## Brand Personality / Tone

Concise, plain-English output that distinguishes passing checks, failures and unverified work.

## Boundaries

Installation preserves project-owned content. Updates affect the installed scaffold; checks must report real failures rather than claim unverified work is complete. Skills guide judgment; automated checks do not certify product correctness, test quality or complete scanner coverage.

The source repository is not a global agent directory. Installation, hook configuration and generated files belong to the target repository. Remote branch protection requires separate approval.

## Stack

Python implementation: [installer](setup.py), [shared runner](.hooks/hard-eng.py) and [language templates](.agents/skills/he/templates). Dart configuration parsing additionally requires PyYAML in the runner's Python environment; missing prerequisites fail the check.
