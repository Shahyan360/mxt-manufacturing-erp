# Verification record

Date: 2026-10-26, Asia/Karachi. This records observed execution only.

## Runtime

- Odoo 17.0 Community public source, commit `dca5cd22d40f25066919d722bf687be48c51b0ec`.
- Python 3.12.4 on Windows, dedicated virtual environment on D:.
- PostgreSQL 18.6, **separate personal cluster** at loopback port 55471.
- wkhtmltopdf 0.12.6, patched Qt, portable public Windows package.
- Addon `mxt_operations` version `17.0.1.0.0`.
- Demonstration database `mxt_demo`; test database `mxt_test`.

## Executed

| Check | Result |
| --- | --- |
| Protected checkout / independent parent boundary metadata | Checked before workspace creation |
| Python AST and XML parsing | Passed |
| Docker Compose configuration validation | Passed |
| Docker clean installation | BLOCKED before container creation: Docker data filesystem read-only |
| Native clean install on empty `mxt_test` | Passed: 68 Community modules including custom addon |
| First custom TransactionCase suite | 20 executed, 5 errors; issues corrected, not represented as passing |
| Corrected suite with module upgrade | 20 executed, 0 failed, 0 errors |
| Expanded suite with module upgrade | **23 executed, 0 failed, 0 errors** |
| Final fresh installation and expanded suite on empty `mxt_clean` | **24 executed, 0 failed, 0 errors** |
| Native clean install on empty `mxt_demo`, no stock demo data | Passed |
| Custom fictional fixture installation | Passed |
| Repeat fictional fixture loading | Passed: one fixture sale, one native MO, two policies, panel stock 40 and pack stock 1 unchanged |
| HTTP login page | HTTP 200 at 127.0.0.1:8171 |
| Browser workflow / screenshots | Passed, no browser page errors; see browser-review.json and screenshots/ |
| Authenticated HTTP QWeb PDF export | Passed; sample-material-summary.pdf rendered and visually inspected |
| Demonstration database module upgrade | Passed, seeded records retained |
| Publication secret-pattern scan | Initial scan: 30 candidate files, 0 findings; rerun after final changes |

Expanded-suite summary from Odoo's actual test runner:

```text
23 post-tests in 35.68s, 8843 queries
0 failed, 0 error(s) of 23 tests when loading database 'mxt_test'
```

Final fresh-database summary after the inspection fingerprint control:

```text
24 post-tests in 50.94s, 9061 queries
0 failed, 0 error(s) of 24 tests when loading database 'mxt_clean'
```

Odoo's per-module statistic says 25 because it includes setup/teardown accounting;
the result count of **23 executed test methods** is the reported number here.
The final fresh database executed **24 test methods** (its statistic includes
setup/teardown and reports 26). It also verifies that changing actual component
consumption after quality approval prevents completion until reinspection.

Covered behavior: purchase role and direct-RPC bypass protection, reviewed-line
freeze, required independent approvers and amount tiers, rejection/reset/history,
BOM quantities and variant filtering, unit conversions, Buy shortages, existing
confirmed supply, repeat scheduler/cron calls, native resupply transit pickings,
warehouse quantities, material reservations, quality gate/rework, native completed
manufacturing stock, sales-to-MO demand, company record isolation, and QWeb HTML/PDF.

Logs remain local under `.local/` and are excluded from publication. An expected
unique-constraint rejection logs a SQL error during its passing negative test.
The early PDF test produced a valid PDF with CSS asset 404 warnings before the
demo database was installed. The expanded run fetched the actual stylesheet and
font assets successfully and generated its PDF. Visual report review is separate.
The final clean run served its report assets from `mxt_clean` on port 8172, without
using the demonstration database. One harmless idle request timeout was logged;
PDF, font requests and test results succeeded. The exported demonstration PDF was
rendered with Poppler and inspected for text/table overlap and clipping.

## Pending acceptance and limits

- Docker portability / pinned PostgreSQL 16 execution remains unverified until
  the host Docker storage issue is resolved. Native PostgreSQL 18 results do not
  prove a PostgreSQL 16 container run.
- User review of the proposed business rules and source is mandatory.
- Broader multi-level/subcontracting, tracked materials, partial production and
  high-concurrency stress scenarios require additional regression fixtures.
- No historic throughput, deployment identity or original performance figure
  was measured or claimed. No employer databases or sources were used.
- No public publication or deployment has occurred.
