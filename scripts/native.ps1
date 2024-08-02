param([ValidateSet('init','up','test','upgrade','stop')][string]$Action='up')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$runtimeRoot=Join-Path (Split-Path -Parent $projectRoot) '_runtime'
$pythonExe=Join-Path $runtimeRoot 'venv17\Scripts\python.exe'
$odooBin=Join-Path $runtimeRoot 'odoo-17.0\odoo-bin'
$configPath=Join-Path $projectRoot '.local\native.conf'
$pidPath=Join-Path $projectRoot '.local\native.pid'
$env:TEMP=Join-Path $runtimeRoot 'temp'
$env:TMP=$env:TEMP
$env:PATH=(Join-Path $runtimeRoot 'wkhtmltox\wkhtmltox\bin')+';'+$env:PATH
$env:LAB_CREDENTIALS=Join-Path $projectRoot '.local\credentials.json'
$env:ODOO_RC=$configPath
Set-Location -LiteralPath $projectRoot
if (!(Test-Path -LiteralPath $configPath)) { throw 'Prepare the isolated fallback runtime first; see docs/NATIVE_RUNTIME.md.' }
function Invoke-LabOdoo {
    & $pythonExe $odooBin -c $configPath @args
    if ($LASTEXITCODE -ne 0) { throw "Native Odoo failed ($LASTEXITCODE)." }
}
function Stop-LabOdoo {
    if (Test-Path -LiteralPath $pidPath) {
        $labPid=[int](Get-Content -LiteralPath $pidPath)
        $labProcess=Get-CimInstance Win32_Process -Filter "ProcessId = $labPid"
        if ($labProcess) {
            if (!$labProcess.CommandLine.Contains($configPath)) { throw 'PID does not belong to this personal lab; refusing to stop it.' }
            Stop-Process -Id $labPid
        }
    }
}
switch ($Action) {
    'init' {
        Invoke-LabOdoo -d mxt_demo -i mxt_operations --without-demo=all --stop-after-init --no-http
        Get-Content -Raw -LiteralPath scripts/seed.py | & $pythonExe $odooBin shell -c $configPath -d mxt_demo --no-http
        if ($LASTEXITCODE -ne 0) { throw 'Native fixture seed failed.' }
    }
    'up' {
        if (Test-Path -LiteralPath $pidPath) {
            $savedLabPid=[int](Get-Content -LiteralPath $pidPath)
            if (Get-Process -Id $savedLabPid -ErrorAction SilentlyContinue) { throw 'Saved lab process is already running.' }
        }
        $nativeArgs=@('"'+$odooBin+'"','-c','"'+$configPath+'"','-d','mxt_demo')
        $process=Start-Process -FilePath $pythonExe -ArgumentList $nativeArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput '.local/native-stdout.log' -RedirectStandardError '.local/native-server.log'
        Set-Content -LiteralPath $pidPath -Value $process.Id
        Write-Output 'Personal Odoo launch requested at http://127.0.0.1:8171. Check .local/native-server.log.'
    }
    'test' { Invoke-LabOdoo -d mxt_test -i mxt_operations -u mxt_operations --without-demo=all --test-enable --test-tags /mxt_operations --stop-after-init --no-http }
    'upgrade' { Stop-LabOdoo; Invoke-LabOdoo -d mxt_demo -u mxt_operations --without-demo=all --stop-after-init --no-http }
    'stop' { Stop-LabOdoo }
}
