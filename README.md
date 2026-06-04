# Azure Multi-Region Capacity Checker

CLI-first MVP for checking Azure VM SKU availability signals across regions.

The tool can run against Azure CLI live data or local JSON fixtures for repeatable tests and demos.

```powershell
python -m capacitychecker check --sku Standard_D2s_v5 --region eastus
python -m capacitychecker check --skus Standard_D2s_v5,Standard_E4s_v5 --regions eastus,swedencentral --output json
python -m capacitychecker check --sku Standard_D2s_v5 --region eastus --include-spot-score --spot-desired-count 1
```

See `docs\instructions.md` for end-user guidance and `docs\roadmap.md` for the implementation roadmap.
