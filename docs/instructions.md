# Azure Multi-Region Capacity Checker — User Guide

## Overview

The Azure Multi-Region Capacity Checker is a command-line tool designed for field engineers to verify Azure VM availability, capacity constraints, and quota headroom across multiple regions and SKUs (VM sizes/families) **before** customer conversations and deployments.

**Purpose:**
- Turn Azure capacity from a guess into a **live, queryable signal**
- Validate that recommended regions actually have available capacity
- Support conversation prep with current, data-driven availability insights
- Export results for dashboards, alerts, and scheduled monitoring

**Who is this for?**
- Azure field engineers preparing customer engagements
- Solution architects validating deployment guidance
- Capacity planners reviewing regional saturation
- Automation systems running scheduled capacity checks

---

## Prerequisites

### Requirements
1. **Azure CLI** installed and authenticated  
   - Ensure `az` is in your PATH and you can run `az account show`
   - The tool will use your current Azure CLI context and subscription

2. **Supported Subscription Access**  
   - You must have read access (Reader role or higher) to view quota and capacity metadata in your target subscription
   - Cross-subscription checks may require appropriate role assignments

3. **Target Azure Regions**  
   - You should know the region identifiers you want to check (e.g., `eastus`, `swedencentral`, `eastasia`)
   - Refer to [Azure Regions](https://azure.microsoft.com/en-us/global-infrastructure/regions/) for the complete list

4. **VM SKU Names**  
   - Identify the VM sizes or families relevant to your scenario (e.g., `Standard_D2s_v5`, `Standard_E4s_v5`)
   - SKU names are case-sensitive and must match Azure's official naming

### Installation

> **Note:** The current repository contains an MVP implementation. Run it with Python from the repository root, or install it in editable mode once packaging is desired.

```bash
# From the repository root:
python -m capacitychecker --version

# Optional editable install:
python -m pip install -e .
capacitychecker --version
```

---

## Authentication

The tool uses **Azure CLI authentication** by default. No separate credentials are required.

### Setup
1. Install and authenticate with the Azure CLI:
   ```bash
   az login
   ```
2. Select your target subscription (if you have multiple):
   ```bash
   az account set --subscription <subscription-id-or-name>
   ```
3. Verify your context:
   ```bash
   az account show
   ```
   The tool will operate in this subscription's scope.

### Permissions Required
- **Microsoft.Compute/skus/read** — to query available SKUs and region offerings
- **Microsoft.Quota/subscriptionQuotas/read** — to check quota headroom
- **Microsoft.Resources/subscriptions/resourceGroups/read** — to understand quota context (optional, for enrichment)

---

## Running a Capacity Check

### Basic Syntax

```bash
# Single SKU, single region
python -m capacitychecker check --sku Standard_D2s_v5 --region eastus

# Multiple SKUs, multiple regions (creates matrix)
python -m capacitychecker check --skus Standard_D2s_v5,Standard_E4s_v5 --regions eastus,swedencentral,eastasia

# With zones (if region is zoned)
python -m capacitychecker check --skus Standard_D2s_v5 --regions eastus --zones 1,2,3

# Include Microsoft Spot Placement Score guidance for Spot VM placement likelihood
python -m capacitychecker check --sku Standard_D2s_v5 --region eastus --include-spot-score --spot-desired-count 1

```

### Live Azure Mode

By default, live mode uses Azure CLI for both quota/headroom and Resource SKUs metadata. The tool calls the Azure Resource SKUs ARM endpoint through `az rest` for offered/restricted signals because `az vm list-skus` can be slow or hang in some environments.

```bash
python -m capacitychecker check --sku Standard_D2s_v5 --region eastus
```

Use `--skip-live-sku-metadata` for quota-only checks.

### Spot Placement Score

Use `--include-spot-score` when you want Microsoft Spot Placement Score guidance for Spot VM placement likelihood:

```bash
python -m capacitychecker check --sku Standard_D2s_v5 --region eastus --include-spot-score --spot-desired-count 1
```

Spot Placement Score is separate from regular VM allocatability. Regular VM allocatability uses offered/restricted metadata and subscription quota. Spot Placement Score answers a narrower question: given the requested Spot VM size, count, region, and optional zone scope, how favorable is the current Spot placement guidance?

Important caveat: Spot Placement Score is a Microsoft recommendation based on current data points like Spot VM availability. A high score does not guarantee that a Spot request will be fully or partially fulfilled, and it is not an eviction-risk guarantee after the VM is running.

### Example Scenarios

#### Scenario 1: Validate Capacity Before Customer Call
You are preparing to recommend `Standard_D2s_v5` in `swedencentral` to a customer.

```bash
# Check if it's available and has capacity:
python -m capacitychecker check --sku Standard_D2s_v5 --region swedencentral
```

**Expected Output:** Table showing allocation status, capacity restriction flags, and quota headroom.

#### Scenario 2: Find Healthy Regions for a Workload
You need to deploy `Standard_E4s_v5` and want to explore all available regions.

```bash
# Check across multiple regions:
python -m capacitychecker check --sku Standard_E4s_v5 --regions eastus,westus2,centralus,swedencentral,westeurope,eastasia

# Output will highlight which regions have capacity and which are restricted.
```

#### Scenario 3: Export for Monitoring or Dashboards
You want to log results for trend analysis or dashboard consumption.

```bash
# Output as JSON for programmatic consumption:
python -m capacitychecker check --skus Standard_D2s_v5,Standard_E4s_v5 --regions eastus,swedencentral \
  --output json > capacity-check.json

# Output as CSV for Excel or reporting tools:
python -m capacitychecker check --skus Standard_D2s_v5,Standard_E4s_v5 --regions eastus,swedencentral \
  --output csv > capacity-report.csv
```

---

## Understanding the Output

### Console Table Output

The default output is a human-readable table. Each row represents a **SKU × Region** combination:

```
SKU                  Region          Offered  Restricted  Spot Pressure  Quota Headroom  Allocatable  Confidence  Freshness
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Standard_D2s_v5      eastus          Yes      No          Low            50 vCPU         Likely Yes   High        5 min ago
Standard_D2s_v5      swedencentral   Yes      Yes         High           10 vCPU         Likely No    Medium      10 min ago
Standard_D2s_v5      eastasia        No       —           —              —               No           High        2 min ago
Standard_E4s_v5      eastus          Yes      No          Medium         120 vCPU        Likely Yes   High        3 min ago
Standard_E4s_v5      swedencentral   Yes      Yes         High           5 vCPU          Unknown      Low         1 hour ago
```

### Column Definitions

| Column | Meaning | Values |
|--------|---------|--------|
| **SKU** | Virtual machine size or family | e.g., `Standard_D2s_v5` |
| **Region** | Azure region identifier | e.g., `eastus`, `swedencentral` |
| **Offered** | Is this SKU available in the region at all? | Yes / No |
| **Restricted** | Does Azure metadata report a capacity restriction for this SKU/region/zone? | Yes / No / Unknown |
| **Spot Pressure** | Spot Placement Score guidance when `--include-spot-score` is used; otherwise unknown | High / Medium / Low / Unavailable / Unknown |
| **Quota Headroom** | Available quota for this SKU in your subscription in this region | e.g., `50 vCPU` or `Unlimited` |
| **Allocatable** | Metadata-derived recommendation confidence, not a live deployment guarantee in V1 | Likely Yes / Likely No / No / Unknown |
| **Confidence** | How confident is this signal? | High / Medium / Low |
| **Freshness** | When was this data collected? | e.g., `5 min ago`, `1 hour ago` |

### Interpreting Results

**Green Signal (Safe to Recommend):**
- `Offered: Yes`
- `Restricted: No`
- `Allocatable: Likely Yes`
- `Confidence: High`
- `Freshness` is recent (< 15 minutes)

**Yellow Signal (Use Caution):**
- `Offered: Yes`
- `Restricted: Yes` or `Unknown`
- `Allocatable: Unknown`
- `Confidence: Medium or Low`
- Consider contacting the customer's Account Team for additional capacity

**Red Signal (Not Recommended):**
- `Offered: No` — SKU not available in region
- `Restricted: Yes` + `Quota Headroom` is very low
- `Allocatable: No`

---

## Output Formats

### JSON Export

Use `--output json` to export results as structured JSON for programmatic consumption:

```bash
python -m capacitychecker check --sku Standard_D2s_v5 --region eastus --output json
```

**Example JSON Output:**
```json
{
  "timestamp": "2026-06-03T14:23:45Z",
  "subscription": "12345678-1234-1234-1234-123456789012",
  "results": [
    {
      "sku": "Standard_D2s_v5",
      "region": "eastus",
      "offered": true,
      "capacity_restricted": false,
      "spot_pressure": "low",
      "quota_headroom": {
        "value": 50,
        "unit": "vCPU"
      },
      "allocatable": "likely_yes",
      "allocatable_confidence": "high",
      "data_source": "azure_metadata_quota_restrictions",
      "freshness_seconds": 300
    }
  ]
}
```

**Use cases:**
- Feed into CI/CD pipelines for automated deployment validation
- Ingest into monitoring/alerting systems
- Store in a database for trend analysis

### CSV Export

Use `--output csv` to export as comma-separated values:

```bash
python -m capacitychecker check --skus Standard_D2s_v5,Standard_E4s_v5 --regions eastus,swedencentral --output csv
```

**Example CSV Output:**
```
SKU,Region,Offered,Capacity_Restricted,Spot_Pressure,Quota_Headroom_Value,Quota_Headroom_Unit,Allocatable,Confidence,Freshness_Seconds
Standard_D2s_v5,eastus,true,false,low,50,vCPU,likely_yes,high,300
Standard_D2s_v5,swedencentral,true,true,high,10,vCPU,likely_no,medium,600
Standard_E4s_v5,eastus,true,false,medium,120,vCPU,likely_yes,high,180
```

**Use cases:**
- Import into Excel or Google Sheets for reporting
- Share with non-technical stakeholders
- Archive for historical comparison

---

## Using Results in Customer Conversations

### Before the Call

1. **Run a check** targeting the SKUs and regions you plan to recommend:
   ```bash
   python -m capacitychecker check --skus Standard_D4s_v5,Standard_D8s_v5 \
     --regions swedencentral,germanywestcentral,northeurope
   ```

2. **Review the results:**
   - Identify which combinations have `Allocatable: Likely Yes` with `Confidence: High`
   - Note any regions flagged as `Restricted: Yes` or with low quota headroom
   - Check freshness — if data is >1 hour old, consider rerunning

3. **Prepare talking points:**
   - "swedencentral currently looks healthy based on metadata, restrictions, and quota headroom"
   - "northeurope is restricted; I recommend we explore germanywestcentral or westeurope"
   - "I verified this 10 minutes ago using our capacity checker"

### During the Conversation

- **Share confidence levels:** "We're highly confident in swedencentral availability; we checked 5 minutes ago"
- **Explain alternatives:** Use the matrix to justify why Region A is recommended over Region B
- **Set expectations:** "Quota headroom shows 30 vCPU available; this supports your immediate needs"

### After the Conversation

- **Export for your CRM/ticket system:**
  ```bash
  python -m capacitychecker check --skus <agreed-skus> --regions <agreed-regions> --output json > ticket-12345-capacity.json
  ```
- **Store for follow-up:** If the customer comes back with allocation issues, you'll have baseline data

---

## Troubleshooting

### Authentication Issues

**Problem:** `Error: Not authenticated with Azure CLI`

**Solution:**
```bash
az login
az account set --subscription <your-subscription>
```

### No SKU Data Returned

**Problem:** `Error: SKU not found or region not supported`

**Solution:**
1. Verify the SKU name is correct (case-sensitive):
   ```bash
   az vm list-skus --location eastus --query "[].name" --output table
   ```
2. Verify the region identifier:
   ```bash
   az account list-locations --query "[].name" --output table
   ```

### Stale Data / High Freshness Age

**Problem:** Results show `Freshness: 2 hours ago`

**Explanation:** The tool may be using cached quota data or Spot signals from the last check.

**Solution:**
```bash
# The MVP does not cache yet, so each live Azure run queries Azure CLI again.
python -m capacitychecker check --sku Standard_D2s_v5 --region eastus
```

### Quota Headroom Shows "Unknown" or "Unlimited"

**Problem:** Quota information is not available

**Reason:** Possible causes include:
- Your role does not have quota read permissions
- The region has no explicit quota limits (unlimited)
- Quota data has not been initialized for your subscription

**Solution:**
- Verify your role includes `Microsoft.Quota/subscriptionQuotas/read`
- Contact your subscription administrator if needed

### Timeout or Slow Performance

**Problem:** `Error: Request timed out`

**Solution:**
- Reduce the number of SKUs/regions in a single check
- Check your internet connectivity
- Retry the command (temporary Azure service delays)

---

## Advanced Usage

### Scheduled Capacity Monitoring

Set up a cron job or scheduled task to run checks on a cadence:

```bash
# Example: Daily check at 9 AM (Linux/Mac)
0 9 * * * /usr/local/bin/capacitychecker check \
  --skus Standard_D2s_v5,Standard_E4s_v5 \
  --regions eastus,swedencentral,westeurope \
  --output json > /var/log/capacity-check-$(date +\%Y\%m\%d).json
```

### Integration with Dashboards

Export results to a monitoring system (e.g., Azure Monitor, Grafana):

```bash
# Export as JSON and post to an endpoint:
capacitychecker check --skus Standard_D2s_v5 --regions eastus,swedencentral \
  --output json | curl -X POST -d @- https://your-dashboard-api.com/capacity
```

### Historical Trend Analysis

Store results over time to detect capacity tightening:

```bash
# Archive daily:
mkdir -p capacity-history
capacitychecker check --skus Standard_D2s_v5 --regions eastus,swedencentral \
  --output json > capacity-history/$(date +%Y-%m-%d).json

# Later, compare:
# "swedencentral showed 50 vCPU headroom on Jan 1, now 10 vCPU on Jan 15"
```

---

## Limitations and Known Constraints

### Current Limitations (V1)

1. **No Real Deployment Probes**  
   - The tool provides metadata-based allocatability signals (quota and capacity restrictions) but does not perform live test deployments
   - Stretch-goal feature: optional real deployment probes for higher confidence

2. **Live SKU Metadata Uses ARM Resource SKUs**
   - Live Azure mode uses quota/headroom signals and Resource SKUs metadata by default.
   - `az vm list-skus` is not used because it can hang in some environments.
   - Use `--skip-live-sku-metadata` if you need a quota-only check.

3. **Quota-Based Only**  
   - Quota headroom is subscription-specific and should not be treated as global Azure capacity
   - A region may look healthy for one subscription and still require separate validation for another customer context

4. **CLI-Only Interface**  
   - No web UI or dashboard (V1)
   - Stretch goal: shareable HTML matrix view

5. **Manual Region/SKU Selection**  
   - No built-in recommendation engine; you choose regions/SKUs to check
   - Stretch goal: agentic analysis and conversation prep material

6. **Spot Pressure is Derived**  
   - Spot pressure depends on whichever trustworthy Spot-related signals are validated during implementation
   - Not a guarantee of Spot availability

7. **Freshness Depends on Cache**  
   - Data freshness varies; quota info may be cached by Azure for up to 1 hour
   - Capacity restriction flags are based on the latest available telemetry

### Regional Considerations

- **Sovereign Clouds:** The tool is designed for Azure Public Cloud; sovereign cloud (Government, China) support is not included in V1
- **Zone Availability:** Zone-level granularity is supported only for regions with availability zones

### Subscription Constraints

- **Cross-Subscription Checks:** Requires appropriate RBAC roles in each subscription
- **Quota Limits:** Quota headroom reflects your subscription's current regional limits and usage; it is not a monthly consumption counter

---

## FAQ

**Q: Why does my recommended region now show "Restricted: Yes"?**  
A: Azure capacity is dynamic. Regions can transition from healthy to constrained. Re-run the check before every customer conversation to ensure current guidance.

**Q: Can I check capacity across multiple subscriptions?**  
A: The tool operates within your current Azure CLI context (one subscription at a time). To check multiple subscriptions, run separate checks after switching with `az account set`.

**Q: What if the SKU I want isn't offered in any of my regions?**  
A: This is often regional availability (e.g., some new SKUs roll out gradually). Check Azure's official [Regions and Availability Zones](https://azure.microsoft.com/en-us/global-infrastructure/availability-zones/) page or contact your Microsoft Account Team for timeline.

**Q: How do I know if a region is about to run out of capacity?**  
A: Watch for `Spot Pressure: High` and `Quota Headroom` trending downward over successive checks. If available, run the tool weekly and archive results in `capacity-history/`.

**Q: Is "Allocatable: Unknown" safe to recommend?**  
A: Use caution. This typically means the metadata, quota, or restriction signals are incomplete, stale, or inconclusive. Consider checking alternatives or reaching out to the Account Team before committing this to a customer.

**Q: Can I schedule this tool to run automatically?**  
A: Yes. See the "Scheduled Capacity Monitoring" section under Advanced Usage.

---

## Support and Feedback

For issues, questions, or feedback:

- **Documentation:** Refer to this guide and the project README
- **Issue Tracking:** Report bugs or request features via the project repository (when available)
- **Microsoft Account Team:** For capacity-related questions or large-scale deployment planning, engage your Account Team

---

**Last Updated:** 2026-06-03  
**Tool Version:** 0.1.0 MVP  
**Status:** End-user documentation for the implemented MVP CLI
