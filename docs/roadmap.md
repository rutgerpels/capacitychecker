# Azure Multi-Region Capacity Checker – Roadmap

**Last Updated:** 2026-06-04
**Status:** MVP implemented; V1 hardening in progress
**Audience:** Azure users, solution architects, capacity planners, and automation owners

---

## Executive Summary

The Azure Multi-Region Capacity Checker is a CLI-first tool designed to transform capacity from guesswork into a **live, queryable signal** for the Azure tenant and subscription context used to run it. Users can run it before deployment planning to get a current SKU-by-region availability matrix. V1 focuses on core functionality: canonical matrix schema, console/JSON/CSV output, and allocatability confidence derived from Azure metadata, quota, and restriction signals. Real deployment probes are explicitly post-V1 or opt-in stretch work.

---

## Current State

- **Repo:** `capacitychecker_v2` (fresh start)
- **Project focus:** Azure capacity guidance for deployment planning
- **Inputs:** CLI accepts one or more SKUs, one or more regions, optional zones, and optional subscription.
- **Outputs:** Console table, JSON, and CSV are implemented.
- **Live Azure data:** Default live mode queries quota/headroom with `az vm list-usage` and offered/restricted metadata through the Azure Resource SKUs ARM endpoint via `az rest`.
- **Maturity:** MVP release candidate. Core CLI works against live Azure; CI, validation, and release checklists are in place.

---

## Vision

A **trustworthy, current capacity signal** accessible from the command line in seconds, reducing the risk of outdated guidance causing production allocation failures. The tool evolves from a CLI-first capacity reader to an agentic platform that supports deployment planning, alerts on regional capacity drift, and integrates with Azure's formal capacity-request workflow.

---

## V1 Scope: CLI-First Capacity Checker

### Input
- **SKU list:** User specifies VM sizes/families to check (e.g., `Standard_D4s_v5`, `Standard_E8s_v5`).
- **Region list:** User specifies candidate Azure regions (e.g., `eastus`, `swedencentral`, `australiaeast`).
- **Zones (optional):** Zone-specific availability where relevant.
- **Subscription context:** Current or specified Azure subscription/tenant for quota lookups.

### Core Output: Canonical Matrix Schema

Per **SKU × Region (× Zone)**, the matrix surfaces:

1. **Offered** (boolean):  
   - Whether the SKU is offered/published in the region.  
   - Source: Azure `ResourceSkus` API.

2. **Capacity-Restricted** (boolean):  
   - Whether the region/zone is under capacity pressure for this SKU.  
   - Source: Azure `ResourceSkus` API `restrictions` field.

3. **Spot Placement Guidance** (optional signal):
   - Microsoft Spot Placement Score guidance for Spot VM placement likelihood when `--include-spot-score` is used.
   - Source: Azure Compute Recommender Spot Placement Score (`az compute-recommender spot-placement-score`).
   - Interpretation: Higher score means more favorable Spot placement guidance for the requested size/count/region/zone. It is not a guarantee that the Spot request will be fully or partially fulfilled, and it is not a post-placement eviction-risk guarantee.

4. **Quota Headroom** (integer):  
   - Remaining quota for this SKU in this region on the target subscription.  
   - Source: Azure Quota API.  
   - Caveat: Subscription-scoped, so results must be generated in the tenant and subscription that matter for the deployment.

5. **Allocatable** (status + confidence):  
   - Can we reasonably recommend this SKU/region combination based on metadata, restrictions, and quota?  
   - Source: V1 metadata, quota, and restriction signals.  
   - Confidence: Metadata-derived, not deployment-probe-confirmed.  
   - Note: Live deployment probes are **post-V1/stretch** because they introduce cost, permissions, cleanup, rate limits, and possible environment side effects.

6. **Freshness & Source** (metadata):  
   - When was this data refreshed?  
   - Which API(s) sourced the signal?  
   - Example: `ResourceSkus (cached 5min ago)`, `QuotaAPI (2min ago)`, `SpotPlacementScore (current run)`.

### Output Formats

- **Console Table:**  
  Human-readable ASCII table, sortable/filterable by region, SKU, or allocatability status.
  
- **JSON:**  
  Structured matrix for dashboard ingestion, alerting, or downstream automation.
  
- **CSV:**  
  Spreadsheet-friendly export for stakeholder sharing or reporting.

### Metadata & Caching

- **Cache strategy:** ResourceSkus (about 60min); Quota (about 5min); Spot Placement Score (about 2min).
- **Offline mode (optional V1.1):** Load previously cached matrix if live APIs unavailable.
- **Source attribution:** Every cell includes metadata so users know how fresh the data is and whether to trust it.
- **MVP live-mode implementation:** live Azure mode avoids `az vm list-skus` because validation showed it can hang or time out. It now uses `az rest` against the Azure Resource SKUs ARM endpoint by default for offered/restricted signals. Use `--skip-live-sku-metadata` for quota-only checks.

---

## Out-of-Scope (Post-V1, Backlog)

### Phase 2: Historical & Agentic
- **Trend store:** Time-series database of capacity signals so "swedencentral has been tightening for 3 weeks" is visible.
- **Agentic analysis:** AI-powered summaries ("3 SKUs are constrained in EU regions; recommend rotation to <alternatives>").
- **Deployment planning summaries:** Auto-generated talking points and risk summaries for deployment planning.

### Phase 3: Web & Integration
- **Shareable web view:** HTML matrix/dashboard to share with stakeholders or publish to team wikis.
- **Azure capacity-request workflow integration:** Deep link or API integration so "request more quota" flows directly to Azure's formal capacity-request process.
- **Scheduled reports:** Background runs that email or Slack digest summaries on a cadence.

### Phase 4: Enhancements
- **Multi-tenant support:** Scope queries across multiple subscriptions or AAD tenants.
- **Predictive modeling:** "Based on trends, swedencentral will likely be constrained in 2 weeks."
- **Alerts & automations:** Trigger actions when allocatability drops or quota hits thresholds.

---

## Workstreams

### 1. **Architecture & API Integration** (Week 1–2)
   - **Goal:** Finalize how to call Azure ResourceSkus, Quota, Spot, and optional Probe APIs.
   - **Tasks:**
     - [x] Document Azure ResourceSkus API schema and filtering options.
     - [x] Document Azure quota/headroom lookup behavior for the current Azure CLI-backed MVP.
     - [x] Identify Spot signal source: Microsoft Spot Placement Score for optional Spot placement guidance.
     - [x] Document post-V1 probe strategy without implementing it in the v1 critical path.
     - Decide on SDK choice (Azure SDK for Python/Go/Node, or raw REST calls).
     - [x] Design schema for the canonical matrix data model.
   - **Outputs:** Architecture decision doc, API integration guide, matrix schema (JSON).

### 2. **Core CLI & Data Fetching** (Week 2–4)
   - **Goal:** Implement CLI argument parsing and data-fetching logic.
   - **Tasks:**
     - [x] Implement SKU and region input parsing/normalization.
     - [x] Implement ResourceSkus API queries through `az rest` with per-run in-memory caching.
     - [x] Implement quota/headroom queries through `az vm list-usage`.
     - [x] Implement optional Spot Placement Score fetch.
     - [x] Model allocatability as a metadata-derived status with confidence.
     - [x] Build in-memory matrix representation and enrichment.
     - [x] Add basic error handling and user feedback.
   - **Outputs:** Working CLI that fetches and combines data into matrix form.

### 3. **Output Formatting** (Week 3–5)
   - **Goal:** Render matrix in console, JSON, and CSV formats.
   - **Tasks:**
     - [x] Implement console table rendering.
     - [x] Implement JSON serialization with metadata.
     - [x] Implement CSV export with appropriate headers and escaping.
     - [x] Add output flags for table/json/csv.
     - Add sorting/filtering flags.
     - Add richer pretty-printing and validation before output.
   - **Outputs:** CLI producing all three output formats; integration tests.

### 4. **Caching & Offline** (Week 4–5)
   - **Goal:** Add caching layer and optional offline fallback.
   - **Tasks:**
     - [x] Design cache key strategy (per API, per region, per subscription, and Spot request shape).
     - [x] Implement local file-backed cache with TTL.
     - Implement cache invalidation logic.
     - Implement optional offline mode (load cached matrix if APIs fail).
     - [x] Add cache diagnostics (`--cache-info`, `--clear-cache`) and bypass (`--no-cache`).
   - **Outputs:** Caching logic, offline mode, cache CLI commands.

### 5. **Authentication & Authorization** (Week 2–3)
   - **Goal:** Ensure secure, transparent auth flow for Azure API calls.
   - **Tasks:**
     - Integrate with Azure SDK authentication (DefaultAzureCredential or user-specified approach).
     - Require appropriate RBAC roles (Reader or compute-focused roles for ResourceSkus, Quota Requestor for Quota API).
     - Handle token refresh and expiry gracefully.
     - Document required permissions and troubleshooting steps.
   - **Outputs:** Auth integration, permission requirements doc, troubleshooting guide.

### 6. **Testing & Validation** (Week 4–6)
   - **Goal:** Ensure accuracy, performance, and user experience.
   - **Tasks:**
     - [x] Unit tests for matrix schema, data transformation, and output formatting.
     - [x] End-to-end tests for CLI invocation, output selection, and failure handling with mocked providers.
     - [x] Performance tests (time to fetch N regions × M SKUs, cache hit rates).
     - [x] Manual live Azure validation checklist for a target tenant/subscription context.
     - [x] Document known limitations and data quality caveats.
   - **Outputs:** Test suite, UAT results, known-issues doc.

### 7. **Documentation & Release** (Week 5–6)
   - **Goal:** Package and document the tool for users.
   - **Tasks:**
     - [x] Write CLI usage guide (--help, examples, common workflows).
     - [x] Write API/data source documentation (which APIs, freshness, confidence levels).
     - [x] Write troubleshooting and FAQ.
     - [x] Prepare release notes and usage communication.
     - [x] Set up CI pipeline (install, version wiring, unit tests, console-script smoke test).
   - **Outputs:** User guide, developer docs, CI/CD, release v1.0.

### 8. **Post-Launch Monitoring & Feedback** (Ongoing)
   - **Goal:** Gather user feedback and identify improvements.
   - **Tasks:**
     - Instrument CLI to log usage (anonymously, conforming to privacy policy).
     - Gather feedback from early users.
     - Track bug reports and feature requests.
     - Prioritize backlog based on actual usage patterns.
   - **Outputs:** Feedback dashboard, roadmap refinement.

---

## Milestones

| Milestone | Target Date | Criteria | Deliverable |
|-----------|------------|----------|-------------|
| **Architecture Review** | Week 1 end | APIs identified, schema finalized, SDK chosen | Architecture doc, schema spec |
| **Core CLI + Fetching** | Week 4 end | CLI runs, fetches ResourceSkus, Quota, Spot, merges into matrix | Working CLI (table output only) |
| **All Outputs** | Week 5 end | JSON, CSV, console table all working; caching in place | CLI with all formats, basic tests |
| **UAT Complete** | Week 6 end | Representative users validate accuracy and UX | UAT signoff, known-issues list |
| **V1 Release** | Week 6 end | Documented, tested, and released | v1.0 tag, user guide, CI/CD online |
| **Phase 2 Kickoff** | Week 7+ | Feedback analysis, prioritization | Roadmap for trend store & agentic features |

---

## Technical Decisions

### 1. **Language & Ecosystem**
   - **Decision Required:** Python (familiar, rich data libs) vs. Go (performant, single binary) vs. Node (npm ecosystem, scripting).
   - **Recommendation:** Go for single-binary distribution; Python if data transformation complexity dominates. Finalize in Architecture Review.

### 2. **Azure SDK**
   - **Decision Required:** Use official Azure SDK (Python, Go, Node) or raw REST calls + auth library?
   - **Recommendation:** Official SDK for abstraction, error handling, and long-term maintenance.

### 3. **Caching Backend**
   - **Decision Required:** In-memory (simplest, process-scoped), local file (shared across runs), or shared store (Redis, if scalable later)?
   - **Recommendation:** Local file for V1 (`.capacitychecker/cache/`), with clear TTL; upgrade to shared store if V2 multi-user support needed.

### 4. **Probe Strategy**
   - **Decision Required:** Allocatability probes (deploy test VM) or metadata-only for V1?
   - **Recommendation:** Metadata-only for V1 (faster, cheaper, less risk). Offer probe as opt-in flag for V1.5 if demand exists.

### 5. **Output Defaults**
   - **Decision Required:** Default output format (table vs. JSON)?
   - **Recommendation:** Console table by default (user-friendly); flags for JSON/CSV. Follow Unix philosophy: defaults human-readable, machine-readable via flags.

### 6. **Spot Signal Source**
   - **Decision Required:** How to derive Spot pressure if direct API unavailable?
   - **Recommendation:** Use Spot pricing differential vs. On-Demand; if unavailable, leave as "unknown" field. Document the approximation.

---

## Open Questions

1. **Deployment & Distribution:**
   - How should users install and update this tool? (Pip package, downloadable binary, GitHub releases, Azure CLI plugin, Docker container?)
   - Should it be bundled with other Azure tools or standalone?

2. **Authentication:**
   - Can users rely on their default Azure SDK auth (DefaultAzureCredential), or do we need interactive browser-based auth?
   - Should the tool work for "my subscription" or also allow cross-subscription/cross-tenant queries?

3. **Spot Signal Availability:**
   - Is there a public Azure API for Spot eviction rates or preemption frequency by region/zone?
   - If not, should we approximate from pricing or skip for V1?

4. **Probe Cost & Risk:**
   - If we include deployment probes, what is the acceptable cost (test VMs) and risk (environment interference)?
   - Should probes run in a sandbox subscription or the target deployment subscription?

5. **Freshness & SLA:**
   - What is the acceptable data staleness for deployment planning? (30s, 5min, 1hr?)
   - Should we warn users if cache is stale or API calls failed?

6. **Scale & Concurrency:**
   - Are we optimizing for single-user CLI runs, or multi-user/scheduled backend runs?
   - Any concurrency limits on Azure API calls we should respect?

7. **Stakeholder Sharing:**
   - Should users be able to download a snapshot matrix for stakeholder sharing, or is that a Phase 3 feature (shareable HTML)?
   - Any compliance/sensitivity around exposing capacity data outside the immediate deployment team?

8. **Integration with Existing Tools:**
   - Does this replace or augment existing capacity/SKU tools (e.g., Azure Pricing API, ResourceSkus explorer in portal)?
   - Should we integrate with dashboards or wikis?

---

## Validation Plan

### User Acceptance Testing (UAT)

**Participants:**  
- 2–3 representative users who regularly make or validate regional deployment decisions.

**Scenarios:**
1. **Happy path:** "Give me a matrix for Standard_D4s_v5 and Standard_E8s_v5 across EU regions." Verify output accuracy and freshness.
2. **Constrained SKU:** Test with a known-constrained SKU (e.g., high-memory in specific region); verify capacity-restricted flag is accurate.
3. **Quota edge case:** Test with subscription that has low/zero quota in a region; verify headroom is accurate.
4. **Output formats:** Verify JSON and CSV are usable for stakeholder sharing and tool import.
5. **Performance:** Measure time to run matrix for 5 SKUs × 10 regions; target <10s.

**Success Criteria:**
- Representative users confirm output informs region-selection decisions.
- No data accuracy issues vs. manual Azure portal checks.
- Output formats are readily shareable with stakeholders or dashboards.
- Performance meets expectations (no long waits).

### Data Quality Validation

- **Spot Signal:** Cross-check with Azure portal Spot pricing/eviction rates if available.
- **Quota:** Compare output vs. Azure portal Quota Blades for same subscription/region.
- **Capacity Restrictions:** Cross-check with ResourceSkus API directly via portal or SDK.

### Test Baseline

- **CI boundary:** CI runs install, version wiring, console-script smoke test, and mocked `unittest` coverage only. It must not require Azure CLI login or live Azure access.
- **MVP coverage expectation:** Unit tests cover CLI argument validation and error UX, matrix behavior, output formats, cache read/write/expiry/corruption, provider command construction, and package version wiring.
- **Live validation:** Azure CLI/API accuracy is validated manually through `docs\validation.md` in the target tenant/subscription context.

### Performance Benchmarks

- **Target:** Fetch matrix for 5 SKUs × 10 regions in <10 seconds (with warm cache, <3 seconds).
- **Acceptable:** Cache hit rate >80% in typical usage (same SKUs/regions queried repeatedly).
- **Current benchmark:** Bounded parallel region workers reduce cold no-cache Azure CLI runtime significantly, but cold runs still exceed the <10s target because each region requires live Azure CLI/API calls. Warm-cache runs meet the <3s target.
- **Observed 5 SKUs × 10 regions:** max-workers 1 cold no-cache: ~120s; max-workers 4 cold no-cache: ~37s; max-workers 10 cold no-cache: ~19s; max-workers 4 warm cache: ~2.4s.

---

## Suggested Backlog

### V1 Core (MVP)
- [x] Architecture & API integration baseline
- [x] CLI with SKU/region input parsing
- [x] ResourceSkus API integration with per-run and persistent caching
- [x] Quota/headroom integration using Azure CLI
- [x] Spot Placement Score integration for optional Spot placement guidance
- [x] Matrix schema and data model
- [x] Console table output
- [x] JSON output format
- [x] CSV output format
- [x] Authentication & permission requirements documented
- [x] Bounded parallel region fetching
- [x] Unit & integration test baseline
- [x] User guide and API docs baseline
- [x] CI baseline
- [x] Validation checklist
- [x] Release checklist and notes draft
- [ ] V1 release/tag

### V1.1 – Enhancements & Hardening
- [ ] Offline mode (cached fallback if APIs fail)
- [ ] Improved error messages and troubleshooting
- [x] Performance optimization baseline (bounded parallel region fetches; persistent caching baseline is complete)
- [ ] Shell completions (bash, zsh, PowerShell)
- [ ] Optional probe feature (allocatability test, opt-in)

### Phase 2 – Trending & Agentic
- [ ] Historical trend store (time-series database)
- [ ] Trend analysis (3-week tightening, etc.)
- [ ] AI-powered summaries ("constrained in X regions, try Y")
- [ ] Deployment planning summary generation

### Phase 3 – Web & Sharing
- [ ] Shareable HTML matrix view
- [ ] Web dashboard (if justified by usage)
- [ ] Integration with Azure capacity-request workflow

### Phase 4 – Scaling & Automation
- [ ] Multi-tenant/multi-subscription support
- [ ] Scheduled batch runs
- [ ] Alerts & notifications
- [ ] Predictive modeling

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| **Azure API changes or deprecations** | Monitor Azure SDK release notes; maintain thin abstraction layer so APIs can be swapped. |
| **Spot signal unavailability** | Design around it early; use pricing differential as fallback; ship with graceful "unknown" if unavailable. |
| **Quota API latency** | Cache aggressively; document acceptable staleness; offer offline fallback. |
| **User adoption low** | Gather feedback early (Week 2–3 prototype demos); co-design with 1–2 champions. |
| **Data accuracy doubts** | Provide source attribution (API, timestamp, cache status); encourage UAT spot-checks vs. portal. |
| **Scope creep (agentic, web features)** | Lock V1 scope; defer Phase 2+ to separate roadmap; use feature flags if needed. |

---

## Success Criteria (V1 Release)

✅ CLI tool runs, accepts SKU/region inputs, and produces accurate matrix in <10s.  
✅ Output in console, JSON, and CSV formats; all consumable by users or dashboards.
✅ Allocatability/confidence signals inform region-selection decisions.  
✅ Caching reduces repeated queries to <3s.  
✅ Tested against real Azure APIs (or sandbox tenant).  
✅ Representative users confirm tool is useful for deployment planning.
✅ Full documentation (user guide, API guide, troubleshooting).  
✅ CI/CD pipeline in place for future updates.

---

## Next Steps

1. **Final manual validation:** Run `docs\validation.md` in a target subscription context.
2. **V1 release/tag:** Follow `docs\release.md` after validation signoff.
3. **Offline fallback:** Add an explicit V1.1 mode that can reuse stale cached entries when Azure APIs are unavailable.

---

## Appendix: Related Tools & Resources

- **Azure ResourceSkus API:** [Documentation](https://learn.microsoft.com/en-us/rest/api/compute/resource-skus/list)
- **Azure Quota APIs:** Validate the appropriate Compute quota API/documentation during the signal spike.
- **Azure Spot Pricing:** [Portal & REST APIs](https://learn.microsoft.com/en-us/azure/virtual-machines/spot-vms)
- **Azure SDK:** [Python](https://github.com/Azure/azure-sdk-for-python), [Go](https://github.com/Azure/azure-sdk-for-go), [Node](https://github.com/Azure/azure-sdk-for-js)

---

**Document Status:** Draft – Ready for architecture review and team feedback.
