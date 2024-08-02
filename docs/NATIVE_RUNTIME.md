# Isolated native fallback

This machine's Docker daemon responds but its internal data filesystem is
read-only. C: reports no free space. Docker data and existing services were not
reset or repaired. A fully separate fallback lives at:
`D:/Personal-Odoo-Portfolio/_runtime/`.

- Public Odoo 17 source, downloaded from GitHub rather than copied from the
  protected Odoo checkout. Archive commit `dca5cd22d40f25066919d722bf687be48c51b0ec`;
  SHA256 `71b3243e6e0cb6373974788666a2c5518a7f1ac6b141f83a205fe5b7ebc77f25`.
- Python 3.12 virtual environment `venv17`; official Odoo 17 requirements.
- Separate PostgreSQL 18.6 cluster `pg-mxt`, listening only at 127.0.0.1:55471.
  It uses the already installed public PostgreSQL binaries without connecting to
  the existing PostgreSQL service. PostgreSQL 18 is a fallback deviation from the
  declared Docker PostgreSQL 16 configuration, and must be reported in results.
- Portable wkhtmltopdf 0.12.6 with patched Qt from the official packaging release.
- Private logs, downloads, scratch files and PostgreSQL credentials. These are
  outside every intended project repository and must not be published.

The native application config is `.local/native.conf`; its data directory is
`.local/native-data`. `.env` and `.local/credentials.json` are generated locally.
Both Docker and native configurations use the **same credentials file**, but
different PostgreSQL instances, filestores and actual databases.

Native runtime control from this project's PowerShell directory:

```powershell
.\scripts\native.ps1 -Action init
.\scripts\native.ps1 -Action up
.\scripts\native.ps1 -Action test
.\scripts\native.ps1 -Action upgrade
.\scripts\native.ps1 -Action stop
```

`init` does not start the server; run `up` afterward. `upgrade` stops it and
upgrades; run `up` afterward. The helper controls only its recorded PID and checks
the process command line against this lab's configuration before stopping it.
The cluster must already be running. Its start/stop commands are local to the
cluster and never target the existing service:

```powershell
& 'D:\LocalDisk C\bin\pg_ctl.exe' -D 'D:\Personal-Odoo-Portfolio\_runtime\pg-mxt' -l 'D:\Personal-Odoo-Portfolio\_runtime\pg-mxt.log' -w start
& 'D:\LocalDisk C\bin\pg_ctl.exe' -D 'D:\Personal-Odoo-Portfolio\_runtime\pg-mxt' -m fast -w stop
```

To reproduce the fallback on another machine, install Python 3.12 and public
PostgreSQL binaries, download the exact public Odoo commit from
`https://codeload.github.com/odoo/odoo/zip/dca5cd22d40f25066919d722bf687be48c51b0ec`,
extract it into `_runtime/odoo-17.0`, create `_runtime/venv17`, and install the
source `requirements.txt` in that environment. Put temporary files on a drive
with free space. Download the official portable Windows archive:
`https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox-0.12.6-1.mxe-cross-win64.7z`.
Extract to the path expected by the helper or adjust its runtime dependency paths.

Initialize **a new empty** PostgreSQL cluster at `_runtime/pg-mxt` with
`portfolio_admin` as the initialization superuser, UTF8 and port 55471. Bind only
to loopback. Run `bootstrap.py`, then `configure_native.py` with the virtual
environment's Python. That helper checks `SHOW data_directory` before creating
the dedicated `mxt` role and enabling SCRAM authentication. It refuses any other
cluster. The one-time bootstrap initially requires trusted local access to that
new isolated cluster; it is replaced by password authentication immediately.
Do not point it at an existing service, reuse another database role, or publish
its generated private credential files.

Prefer the pinned Docker environment for portable review when the host Docker
storage issue has been resolved. Its clean-install validation remains separate
from the native test results.
