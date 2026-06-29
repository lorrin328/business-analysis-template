$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

function Invoke-Checked {
  param(
    [Parameter(Mandatory = $true)]
    [scriptblock]$Command,
    [Parameter(Mandatory = $true)]
    [string]$Name
  )

  & $Command
  if ($LASTEXITCODE -ne 0) {
    throw "$Name failed with exit code $LASTEXITCODE"
  }
}

Write-Host "== preflight: required files =="
@(
  "backend\main.py",
  "backend\business_data.db",
  "deploy\nginx.conf",
  "deploy\systemd.service"
) | ForEach-Object {
  if (-not (Test-Path -LiteralPath $_)) {
    throw "Missing required file: $_"
  }
}

$HtmlEntry = Get-ChildItem -File -Filter "*.html" | Select-Object -First 1
if (-not $HtmlEntry) {
  throw "Missing production HTML entry"
}

Write-Host "== preflight: nginx upload limit =="
$nginx = Get-Content -Encoding utf8 "deploy\nginx.conf" -Raw
if ($nginx -notmatch "client_max_body_size\s+100m") {
  throw "deploy\nginx.conf must include client_max_body_size 100m"
}

Write-Host "== preflight: tests =="
$env:UV_CACHE_DIR = Join-Path $Root ".uv-cache"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Root ".uv-python"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
  Invoke-Checked -Name "uv venv" -Command { uv venv }
}
Invoke-Checked -Name "uv pip install" -Command {
  uv pip install -r requirements.txt -r backend\requirements.txt
}
Invoke-Checked -Name "pytest" -Command { & $Python -m pytest -q }

Write-Host "== preflight: data quality =="
Invoke-Checked -Name "data quality audit" -Command { & $Python backend\audit_data_quality.py --year 2026 }

Write-Host "preflight ok"
