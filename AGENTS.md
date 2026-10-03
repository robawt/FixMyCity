# FixMyCity Agent Rules

## Goal
Build a reliable Hyderabad civic-AI hackathon MVP.

## Priorities
1. Working demo
2. Correctness
3. Simplicity
4. Performance
5. Everything else

## Architecture
AI extracts evidence.
Backend validates structured output.
Policy code calculates/adjusts severity.
Never invent citizen facts.

## Token discipline
Read only relevant files.
Do not dump full files.
Do not repeat unchanged code.
Prefer patches.
Keep responses concise.

## Engineering
Reuse existing components.
Avoid unnecessary dependencies.
Do not replace the current stack without reason.
Test the smallest relevant path after edits.

## Golden path
QR/web
→ text/photo
→ GPS
→ AI
→ structured ticket
→ dashboard

## Data integrity
Separate:
- real data
- seeded demo data
- unavailable data

Never present synthetic data as live municipal data.

## Stop condition
Once the requested feature works and its smoke test passes, stop.