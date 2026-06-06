# MVP Validation Checklist

Use this checklist to validate the CLI in the Azure tenant and subscription context that matters for the deployment plan. Do not use results from one subscription as proof for another subscription.

## Prerequisites

1. Install the package from the repository root:

   ```powershell
   python -m pip install -e .
   capacitychecker --version
   ```

2. Authenticate with Azure CLI and select the target subscription:

   ```powershell
   az login
   az account set --subscription <subscription-id-or-name>
   az account show
   ```

3. If validating Spot Placement Score, verify command availability:

   ```powershell
   az compute-recommender spot-placement-score --help
   ```

## Unit and package checks

Run these before live Azure validation:

```powershell
python -m unittest discover -q
python -m pip install -e .
capacitychecker --version
python -m capacitychecker --version
```

## Live validation scenarios

### 1. Basic SKU and region

```powershell
python -m capacitychecker check --sku Standard_D2s_v5 --region eastus --no-cache
```

Expected result:
- The command exits successfully.
- The row contains the requested SKU and region.
- `Offered`, `Restricted`, `Quota`, `Allocatable`, and `Confidence` are populated with non-empty values.

### 2. Multi-region matrix and cache

```powershell
python -m capacitychecker check --clear-cache
python -m capacitychecker check --skus Standard_D2s_v5,Standard_E4s_v5 --regions eastus,swedencentral,westeurope --max-workers 4 --output json
python -m capacitychecker check --skus Standard_D2s_v5,Standard_E4s_v5 --regions eastus,swedencentral,westeurope --max-workers 4 --output json
python -m capacitychecker check --cache-info
```

Expected result:
- The first matrix run populates the cache.
- The second run completes faster and includes cache hit notes in JSON row metadata.
- `--cache-info` shows entries for Resource SKUs and usage.

### 3. Quota comparison

Compare the CLI quota result with Azure CLI usage for the same region:

```powershell
python -m capacitychecker check --sku Standard_D2s_v5 --region eastus --output json
az vm list-usage --location eastus --output table
```

Expected result:
- The CLI quota headroom aligns with the relevant vCPU family or regional vCPU quota returned by Azure CLI.
- If family-specific quota is unavailable, the CLI may fall back to broader vCPU quota signals.

### 4. Resource SKUs comparison

Compare offered/restricted metadata with the Resource SKUs endpoint:

```powershell
$sub = az account show --query id --output tsv
az rest --method get `
  --url "https://management.azure.com/subscriptions/$sub/providers/Microsoft.Compute/skus" `
  --url-parameters "api-version=2021-07-01" "`$filter=location eq 'eastus'" `
  --output json
```

Expected result:
- The requested SKU appears in Resource SKUs when the CLI reports `Offered: yes`.
- Any Resource SKUs restrictions for the SKU/region are reflected in the CLI `Restricted` and `Allocatable` values.

### 5. Spot Placement Score

```powershell
python -m capacitychecker check --sku Standard_D2s_v5 --region eastus --include-spot-score --spot-desired-count 1 --output json
az compute-recommender spot-placement-score `
  --location eastus `
  --availability-zones false `
  --desired-locations '["eastus"]' `
  --desired-count 1 `
  --desired-sizes '[{"sku":"Standard_D2s_v5"}]' `
  --output json
```

Expected result:
- The CLI Spot Placement Score fields align with Azure CLI `placementScores`.
- Spot guidance is treated as recommendation-only. It is not a deployment fulfillment guarantee and not an eviction guarantee after placement.

### 6. Performance baseline

```powershell
$skus = "Standard_D2s_v5,Standard_D4s_v5,Standard_E2s_v5,Standard_E4s_v5,Standard_B2s"
$regions = "eastus,westus2,centralus,northeurope,westeurope,swedencentral,eastasia,southeastasia,australiaeast,uksouth"

Measure-Command {
  python -m capacitychecker check --skus $skus --regions $regions --max-workers 4 --output json | Out-Null
}

Measure-Command {
  python -m capacitychecker check --skus $skus --regions $regions --max-workers 4 --output json | Out-Null
}
```

Expected result:
- Cold live runs may exceed the target because Azure CLI/API calls dominate runtime.
- Warm-cache runs should complete close to the documented warm-cache target.

## Sign-off criteria

- Unit tests pass locally and in CI.
- Live checks succeed in the target subscription context.
- Quota and Resource SKUs spot checks align with Azure CLI/direct API output.
- Spot Placement Score, when used, is documented as guidance only.
- JSON and CSV outputs are usable for downstream review or automation.
