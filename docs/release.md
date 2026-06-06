# V1 Release Checklist

Use this checklist when preparing a v1.0 release.

## Scope gate

Confirm the MVP scope is complete:

- CLI accepts one or more SKUs and regions.
- Live Azure mode uses the active or specified subscription context.
- Resource SKUs, quota/headroom, and optional Spot Placement Score signals are available.
- Console, JSON, and CSV outputs work.
- Persistent cache controls are available: `--no-cache`, `--clear-cache`, and `--cache-info`.
- Bounded parallel region workers are available through `--max-workers`.
- Documentation describes subscription-scoped behavior and known caveats.

## Versioning

The package version is sourced from `capacitychecker.__version__` through `pyproject.toml`. For a release:

1. Update `capacitychecker\__init__.py`.
2. Verify package metadata and CLI output agree:

   ```powershell
   python -m pip install -e .
   python -m capacitychecker --version
   capacitychecker --version
   python -c "import importlib.metadata, capacitychecker; assert importlib.metadata.version('capacitychecker') == capacitychecker.__version__"
   ```

## Required checks

Run:

```powershell
python -m unittest discover -q
git --no-pager diff --check
python -m pip install -e .
capacitychecker --version
capacitychecker check --help
```

Run the manual validation checklist in `docs\validation.md` for at least one known subscription context before tagging v1.0.

## Release notes draft

### v1.0.0

Initial MVP release:

- SKU x region capacity matrix for Azure VM sizes.
- Live Azure Resource SKUs metadata for offered/restricted signals.
- Live Azure CLI quota/headroom lookup.
- Optional Microsoft Spot Placement Score guidance.
- Table, JSON, and CSV output.
- Persistent response cache with inspect, clear, and bypass controls.
- Bounded parallel region checks with `--max-workers`.
- Subscription-scoped user guide, validation checklist, and release checklist.

Known caveats:

- Results are valid for the Azure tenant and subscription context used to run the tool.
- Allocatability is metadata-derived and not a live deployment guarantee.
- Spot Placement Score is recommendation-only and does not guarantee Spot fulfillment or post-placement eviction behavior.
- Cold no-cache runs can be dominated by Azure CLI/API latency; warm-cache runs are the expected fast path for repeated checks.

## Tagging

After checks pass and release notes are finalized:

```powershell
git tag v1.0.0
git push origin v1.0.0
```
