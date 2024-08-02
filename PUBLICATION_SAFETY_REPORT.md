# Publication safety report

Publication explicitly authorized by the user on 2026-10-28.
Implementation author: Muhammad Shahyan Khalid. Each project has a separate Git repository.

## Publication scope

Only independently authored addon code, fictional fixtures, deployment scripts, documentation
and reviewed demonstration media are selected. Employer files and history were not used.
The parent workspace and private runtime remain outside this repository.

## Publication checks

- Exact independent Git root checked: `01-MXT-Manufacturing-ERP`.
- Candidate files scanned: 38. Content-pattern findings: 0.
- Symlinks/reparse points: 0. Nested repositories are rejected.
- Patterns cover private keys, known provider keys, credential URLs and literal credentials.
- Source review considered fictional identifiers, public provider endpoints and private environment configuration.
- Screenshots were visually reviewed; the PDF was generated from the fictional demonstration.
- A heuristic scan is supplemental to source and media review; it is not proof of absence of secrets.

## Exclusions

Private .env/.local contents, passwords, database/filestore data, runtime downloads, caches,
logs, archives, private keys and binaries remain excluded by the publication set and .gitignore.
No original employer code, client database or production record is included.

## Licenses and dependencies

New addon source is LGPL-3; the included license text applies. Public Odoo Community is an
external dependency. No Enterprise/commercial addon or runtime image is redistributed.
Referenced images, Python dependencies and official schema assets retain upstream terms.
Official PINT schema/rule assets are user-supplied private dependencies, not bundled files.

## Validation scope

Implementation and runtime validation are recorded separately. See docs/VERIFICATION.md.
Publication scanning does not execute business workflows, tests, providers or Docker builds.

## Published file inventory

- `.env.example`
- `.gitignore`
- `LICENSE`
- `README.md`
- `addons/mxt_operations/__init__.py`
- `addons/mxt_operations/__manifest__.py`
- `addons/mxt_operations/data/cron.xml`
- `addons/mxt_operations/data/stages.xml`
- `addons/mxt_operations/demo/scenario.xml`
- `addons/mxt_operations/models/__init__.py`
- `addons/mxt_operations/models/planning.py`
- `addons/mxt_operations/models/product.py`
- `addons/mxt_operations/models/production.py`
- `addons/mxt_operations/models/purchase.py`
- `addons/mxt_operations/reports/operations.xml`
- `addons/mxt_operations/security/groups.xml`
- `addons/mxt_operations/security/ir.model.access.csv`
- `addons/mxt_operations/security/rules.xml`
- `addons/mxt_operations/tests/__init__.py`
- `addons/mxt_operations/tests/test_operations.py`
- `addons/mxt_operations/views/operations.xml`
- `docker/compose.yaml`
- `docker/images.lock.json`
- `docs/MANUAL_REVIEW.md`
- `docs/NATIVE_RUNTIME.md`
- `docs/VERIFICATION.md`
- `docs/browser-review.json`
- `docs/sample-material-summary.pdf`
- `docs/screenshots/material-policies.png`
- `docs/screenshots/production-board.png`
- `docs/screenshots/production-workflow.png`
- `scripts/bootstrap.py`
- `scripts/browser_review.py`
- `scripts/configure_native.py`
- `scripts/lab.ps1`
- `scripts/native.ps1`
- `scripts/publication_audit.py`
- `scripts/seed.py`
- `PUBLICATION_SAFETY_REPORT.md` (excluded from its own recursive hash).
- `docs/publication-inventory.json` (excluded from its own recursive hash).

## Findings

No content-pattern, link, nested-repository or stale-status findings in the selected publication files.
