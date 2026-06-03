# Azure Multi-Region Capacity Checker – Roadmap

**Last Updated:** 2026-06-03  
**Status:** V1 Planning  
**Audience:** Internal product team, field engineers, Azure capacity stakeholders

---

## Executive Summary

The Azure Multi-Region Capacity Checker is a CLI-first tool designed to transform capacity from **tribal knowledge** into a **live, queryable signal**. Field engineers can run it before customer conversations to get a current SKU-by-region availability matrix, informing what deployment guidance we can confidently give. V1 focuses on core functionality: canonical matrix schema, console/JSON/CSV output, and allocatability confidence derived from Azure metadata, quota, and restriction signals. Real deployment probes are explicitly post-V1 or opt-in stretch work.

---

## Current State

- **Repo:** `capacitychecker_v2` (fresh start)
- **Team:** Azure Capacity / Field Engineering alignment
- **Inputs:** None yet (design phase)
- **Outputs:** None yet (design phase)
- **Maturity:** Pre-alpha; requirements and architecture in progress

---

## Vision

A **trustworthy, always-current capacity signal** accessible to field engineers in seconds, reducing the risk of outdated guidance causing production allocation failures. The tool evolves from a CLI-first capacity reader to an agentic platform that prepares customer conversations, alerts on regional capacity drift, and integrates with Azure's formal capacity-request workflow.

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

3. **Spot Pressure** (signal):  
   - Derived from Spot signals where available, such as pricing signals or other documented indicators.  
   - Source: To be validated during the Azure signal spike.  
   - Interpretation: Higher pressure → general scarcity signal (not definitive but indicative).

4. **Quota Headroom** (integer):  
   - Remaining quota for this SKU in this region on the target subscription.  
   - Source: Azure Quota API.  
   - Caveat: Subscription-scoped, so must be validated per customer context.

5. **Allocatable** (status + confidence):  
   - Can we reasonably recommend this SKU/region combination based on metadata, restrictions, and quota?  
   - Source: V1 metadata, quota, and restriction signals.  
   - Confidence: Metadata-derived, not deployment-probe-confirmed.  
   - Note: Live deployment probes are **post-V1/stretch** because they introduce cost, permissions, cleanup, rate limits, and possible customer-environment side effects.

6. **Freshness & Source** (metadata):  
   - When was this data refreshed?  
   - Which API(s) sourced the signal?  
   - Example: `ResourceSkus (cached 5min ago)`, `QuotaAPI (2min ago)`, `SpotPressure (unknown source pending validation)`.

### Output Formats

- **Console Table:**  
  Human-readable ASCII table, sortable/filterable by region, SKU, or allocatability status.
  
- **JSON:**  
  Structured matrix for dashboard ingestion, alerting, or downstream automation.
  
- **CSV:**  
  Spreadsheet-friendly export for customer sharing or reporting.

### Metadata & Caching

- **Cache strategy:** ResourceSkus (long-lived, 10–60min); Quota (medium, 2–5min); Spot signals (short, 1–2min).
- **Offline mode (optional V1):** Load previously cached matrix if live APIs unavailable.
- **Source attribution:** Every cell includes metadata so users know how fresh the data is and whether to trust it.
- **MVP live-mode caveat:** live Azure mode should avoid `az vm list-skus` by default because validation showed it can hang or time out. Use `az vm list-usage` for quota/headroom in the MVP, fixture data for deterministic offered/restricted behavior, and a cached SKU metadata service or robust REST integration post-MVP.

---

## Out-of-Scope (Post-V1, Backlog)

### Phase 2: Historical & Agentic
- **Trend store:** Time-series database of capacity signals so "swedencentral has been tightening for 3 weeks" is visible.
- **Agentic analysis:** AI-powered summaries ("3 SKUs are constrained in EU regions; recommend rotation to <alternatives>").
- **Customer prep material:** Auto-generated talking points and risk summaries for field engineer conversations.

### Phase 3: Web & Integration
- **Shareable web view:** HTML matrix/dashboard to share with customers or pin to internal wikis.
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
     - Document Azure ResourceSkus API schema and filtering options.
     - Document Azure Quota API schema (subscription-scoped quota lookups).
     - Identify Spot signal source (pricing API, documented telemetry, or leave as unknown if no trustworthy source exists).
     - Document post-V1 probe strategy without implementing it in the v1 critical path.
     - Decide on SDK choice (Azure SDK for Python/Go/Node, or raw REST calls).
     - Design schema for canonical matrix internal representation.
   - **Outputs:** Architecture decision doc, API integration guide, matrix schema (JSON).

### 2. **Core CLI & Data Fetching** (Week 2–4)
   - **Goal:** Implement CLI argument parsing and data-fetching logic.
   - **Tasks:**
     - Implement SKU and region input validation/normalization.
     - Implement ResourceSkus API queries with caching layer.
     - Implement Quota API queries (authenticated, subscription-scoped).
     - Implement Spot signal fetch (or mock if API unavailable).
     - Model allocatability as a metadata-derived status with confidence.
     - Build in-memory matrix representation and enrichment.
     - Add basic error handling and user feedback.
   - **Outputs:** Working CLI that fetches and combines data into matrix form.

### 3. **Output Formatting** (Week 3–5)
   - **Goal:** Render matrix in console, JSON, and CSV formats.
   - **Tasks:**
     - Implement console table rendering (ASCII, colored, sortable).
     - Implement JSON serialization with full metadata.
     - Implement CSV export with appropriate headers and escaping.
     - Add output flags (--format json/csv/table, --sort-by, --filter, etc.).
     - Add pretty-printing and validation before output.
   - **Outputs:** CLI producing all three output formats; integration tests.

### 4. **Caching & Offline** (Week 4–5)
   - **Goal:** Add caching layer and optional offline fallback.
   - **Tasks:**
     - Design cache key strategy (per API, per region, per tenant).
     - Implement local file or in-memory cache with TTL.
     - Implement cache invalidation logic.
     - Implement optional offline mode (load cached matrix if APIs fail).
     - Add cache diagnostics (--show-cache, --clear-cache, --cache-info).
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
     - Unit tests for matrix schema, data transformation, and output formatting.
     - Integration tests with mock Azure APIs (or sandbox tenant if available).
     - End-to-end tests (CLI invocation, data fetch, output validation).
     - Performance tests (time to fetch N regions × M SKUs, cache hit rates).
     - User acceptance testing with 2–3 field engineers.
     - Document known limitations and data quality caveats.
   - **Outputs:** Test suite, UAT results, known-issues doc.

### 7. **Documentation & Release** (Week 5–6)
   - **Goal:** Package and document the tool for internal use.
   - **Tasks:**
     - Write CLI usage guide (--help, examples, common workflows).
     - Write API/data source documentation (which APIs, freshness, confidence levels).
     - Write troubleshooting and FAQ.
     - Write developer guide for future contributors.
     - Prepare release notes and internal communication.
     - Set up CI/CD pipeline (build, test, release).
   - **Outputs:** User guide, developer docs, CI/CD, release v1.0.

### 8. **Post-Launch Monitoring & Feedback** (Ongoing)
   - **Goal:** Gather field engineer feedback and identify improvements.
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
| **UAT Complete** | Week 6 end | Field engineers validate accuracy and UX | UAT signoff, known-issues list |
| **V1 Release** | Week 6 end | Documented, tested, released internally | v1.0 tag, user guide, CI/CD online |
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
   - **Decision Required:** In-memory (simplest, process-scoped), local file (shared across runs), or external store (Redis, if scalable later)?
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
   - How should field engineers install and update this tool? (Pip package, downloadable binary, GitHub releases, Azure CLI plugin, Docker container?)
   - Should it be bundled with other Azure tools or standalone?

2. **Authentication:**
   - Can field engineers rely on their default Azure SDK auth (DefaultAzureCredential), or do we need interactive browser-based auth?
   - Should the tool work for "my subscription" or also allow cross-subscription/cross-tenant queries?

3. **Spot Signal Availability:**
   - Is there a public Azure API for Spot eviction rates or preemption frequency by region/zone?
   - If not, should we approximate from pricing or skip for V1?

4. **Probe Cost & Risk:**
   - If we include deployment probes, what is the acceptable cost (test VMs) and risk (customer environment interference)?
   - Should probes run in a sandbox subscription or customer's subscription?

5. **Freshness & SLA:**
   - What is the acceptable data staleness for field engineers? (30s, 5min, 1hr?)
   - Should we warn users if cache is stale or API calls failed?

6. **Scale & Concurrency:**
   - Are we optimizing for single-user CLI runs, or multi-user/scheduled backend runs?
   - Any concurrency limits on Azure API calls we should respect?

7. **Customer Sharing:**
   - Should field engineers be able to "download" a snapshot matrix to share with customers, or is that a Phase 3 feature (shareable HTML)?
   - Any compliance/sensitivity around exposing capacity data to customers?

8. **Integration with Existing Tools:**
   - Does this replace or augment existing capacity/SKU tools (e.g., Azure Pricing API, ResourceSkus explorer in portal)?
   - Should we integrate with internal dashboards or wikis?

---

## Validation Plan

### User Acceptance Testing (UAT)

**Participants:**  
- 2–3 field engineers who regularly advise customers on regional deployments.

**Scenarios:**
1. **Happy path:** "Give me a matrix for Standard_D4s_v5 and Standard_E8s_v5 across EU regions." Verify output accuracy and freshness.
2. **Constrained SKU:** Test with a known-constrained SKU (e.g., high-memory in specific region); verify capacity-restricted flag is accurate.
3. **Quota edge case:** Test with subscription that has low/zero quota in a region; verify headroom is accurate.
4. **Output formats:** Verify JSON and CSV are usable (customer-shareable, import into tools).
5. **Performance:** Measure time to run matrix for 5 SKUs × 10 regions; target <10s.

**Success Criteria:**
- Field engineers confirm output informs their region-selection conversation.
- No data accuracy issues vs. manual Azure portal checks.
- Output formats are readily shareable with customers or internal dashboards.
- Performance meets expectations (no long waits).

### Data Quality Validation

- **Spot Signal:** Cross-check with Azure portal Spot pricing/eviction rates if available.
- **Quota:** Compare output vs. Azure portal Quota Blades for same subscription/region.
- **Capacity Restrictions:** Cross-check with ResourceSkus API directly via portal or SDK.

### Performance Benchmarks

- **Target:** Fetch matrix for 5 SKUs × 10 regions in <10 seconds (with warm cache, <3 seconds).
- **Acceptable:** Cache hit rate >80% in typical usage (same SKUs/regions queried repeatedly).

---

## Suggested Backlog

### V1 Core (MVP)
- [ ] Architecture & API integration finalized
- [ ] CLI with SKU/region input validation
- [ ] ResourceSkus API integration with caching
- [ ] Quota API integration (subscription-scoped)
- [ ] Spot signal integration (or mock)
- [ ] Matrix schema and internal representation
- [ ] Console table output (with sorting/filtering)
- [ ] JSON output format
- [ ] CSV output format
- [ ] Authentication & permission requirements
- [ ] Unit & integration tests (70%+ coverage)
- [ ] User guide and API docs
- [ ] Internal release (v1.0)

### V1.1 – Enhancements & Hardening
- [ ] Offline mode (cached fallback if APIs fail)
- [ ] Improved error messages and troubleshooting
- [ ] Performance optimization (parallel API calls, smarter caching)
- [ ] Shell completions (bash, zsh, PowerShell)
- [ ] Optional probe feature (allocatability test, opt-in)

### Phase 2 – Trending & Agentic
- [ ] Historical trend store (time-series database)
- [ ] Trend analysis (3-week tightening, etc.)
- [ ] AI-powered summaries ("constrained in X regions, try Y")
- [ ] Customer prep material generation

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
| **Field engineer adoption low** | Gather feedback early (Week 2–3 prototype demos); co-design with 1–2 champions. |
| **Data accuracy doubts** | Provide source attribution (API, timestamp, cache status); encourage UAT spot-checks vs. portal. |
| **Scope creep (agentic, web features)** | Lock V1 scope; defer Phase 2+ to separate roadmap; use feature flags if needed. |

---

## Success Criteria (V1 Release)

✅ CLI tool runs, accepts SKU/region inputs, and produces accurate matrix in <10s.  
✅ Output in console, JSON, and CSV formats; all consumable by field engineers or dashboards.  
✅ Allocatability/confidence signals inform region-selection decisions.  
✅ Caching reduces repeated queries to <3s.  
✅ Tested against real Azure APIs (or sandbox tenant).  
✅ Field engineers confirm tool is useful and would use it before customer conversations.  
✅ Full documentation (user guide, API guide, troubleshooting).  
✅ CI/CD pipeline in place for future updates.

---

## Next Steps

1. **Kick-off meeting:** Finalize architecture, API strategy, and tool design (Week 1 start).
2. **API integration spike:** Prototype fetching from ResourceSkus, Quota, Spot APIs (Week 1).
3. **Schema finalization:** Agree on matrix schema and internal representation (Week 1 end).
4. **Core development begins:** Implement CLI and data fetching (Week 2 start).
5. **Weekly syncs:** Track progress, unblock, and adjust scope if needed.
6. **UAT setup:** Recruit 2–3 field engineers for feedback (Week 4).
7. **Release prep:** Documentation, CI/CD, internal communication (Week 6).

---

## Appendix: Related Tools & Resources

- **Azure ResourceSkus API:** [Documentation](https://learn.microsoft.com/en-us/rest/api/compute/resource-skus/list)
- **Azure Quota APIs:** Validate the appropriate Compute quota API/documentation during the signal spike.
- **Azure Spot Pricing:** [Portal & REST APIs](https://learn.microsoft.com/en-us/azure/virtual-machines/spot-vms)
- **Azure SDK:** [Python](https://github.com/Azure/azure-sdk-for-python), [Go](https://github.com/Azure/azure-sdk-for-go), [Node](https://github.com/Azure/azure-sdk-for-js)

---

**Document Status:** Draft – Ready for architecture review and team feedback.
