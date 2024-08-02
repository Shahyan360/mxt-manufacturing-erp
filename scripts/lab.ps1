param([ValidateSet('init','up','stop','test','upgrade','reset')][string]$Action='up')
$ErrorActionPreference='Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$composeArgs = @('compose','--env-file','.env','-f','docker/compose.yaml')
function Invoke-LabCompose { & docker @composeArgs @args; if ($LASTEXITCODE -ne 0) { throw "Docker action failed ($LASTEXITCODE)." } }
if (!(Test-Path -LiteralPath '.env')) { python scripts/bootstrap.py; if ($LASTEXITCODE -ne 0) { throw 'Bootstrap failed.' } }
switch ($Action) {
    'init' {
        Invoke-LabCompose up -d db
        Invoke-LabCompose run --rm odoo odoo -d mxt_demo -i mxt_operations --without-demo=all --stop-after-init --no-http
        Get-Content -Raw -LiteralPath 'scripts/seed.py' | & docker @composeArgs run --rm -T odoo odoo shell -d mxt_demo --no-http
        if ($LASTEXITCODE -ne 0) { throw 'Demo seed failed.' }
        Invoke-LabCompose up -d odoo
    }
    'up' { Invoke-LabCompose up -d }
    'stop' { Invoke-LabCompose stop }
    'upgrade' {
        Invoke-LabCompose stop odoo
        Invoke-LabCompose run --rm odoo odoo -d mxt_demo -u mxt_operations --without-demo=all --stop-after-init --no-http
        Invoke-LabCompose up -d odoo
    }
    'test' {
        Invoke-LabCompose up -d db
        # Separate disposable database; never run destructive tests on mxt_demo.
        Invoke-LabCompose run --rm odoo odoo -d mxt_test -i mxt_operations -u mxt_operations --without-demo=all --test-enable --test-tags /mxt_operations --stop-after-init --no-http
    }
    'reset' {
        # Only the two explicitly named personal lab databases are reset.
        Invoke-LabCompose stop odoo
        Invoke-LabCompose exec -T db dropdb -U mxt --if-exists --force mxt_demo
        & $PSCommandPath -Action init
    }
}
