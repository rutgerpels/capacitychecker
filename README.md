# Azure Multi-Region Capacity Checker

CLI-first MVP for checking Azure VM SKU availability signals across regions.

The tool runs against Azure CLI live data.

```powershell
python -m capacitychecker check --sku Standard_D2s_v5 --region eastus
python -m capacitychecker check --skus Standard_D2s_v5,Standard_E4s_v5 --regions eastus,swedencentral --output json
python -m capacitychecker check --skus Standard_D2s_v5,Standard_E4s_v5 --regions eastus,swedencentral --max-workers 4
python -m capacitychecker check --sku Standard_D2s_v5 --region eastus --include-spot-score --spot-desired-count 1
python -m capacitychecker check --cache-info
```

See:

- `docs\instructions.md` for end-user guidance.
- `docs\validation.md` for live Azure validation steps.
- `docs\release.md` for the v1 release checklist.
- `docs\roadmap.md` for the implementation roadmap.
