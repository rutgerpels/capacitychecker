# Azure Multi-Region Capacity Checker

## Problem

Azure capacity is not infinite and it is not static. Guidance we give customers
("deploy in Sweden Central") is accurate at a moment in time, then drifts as regional
capacity tightens. Today this knowledge is tribal and verbal, so customers hit allocation
failures in production and lose trust in our guidance.

We need a tool that turns capacity from a **guess** into a **live, queryable signal** —
runnable before every customer conversation and on a schedule — so guidance is always current.

## Goal

Given a set of **SKUs** (VM sizes / families) and a set of **candidate regions**, produce a
clean **availability matrix** showing, per SKU × region (× zone where relevant):

- Whether the SKU is **offered** in the region.
- Whether it is **capacity-restricted** (the key signal).
- A **capacity-pressure indicator** derived from Spot signals.
- **Quota headroom** for the subscription in that region.
- A definitive **allocatable yes/no** where we can test it.

Output should be human-readable (table/console) **and** machine-readable (JSON/CSV) so it can
feed dashboards, alerts, and scheduled runs.

## Stretch

- Agentic features to analyse results and generate conversation prep material with customers. 
- Historical trend store (so "swedencentral has been tightening for 3 weeks" is visible).
- Web view / shareable HTML matrix for customer conversations.
- Integration with the formal Azure capacity-request workflow (link out / pre-fill).

---
