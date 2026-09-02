param([int]$Year = (Get-Date).Year, [string]$Database = "")
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

Write-Host "== preflight: Node.js test runtime =="
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  throw "Node.js 18+ is required for the tax calculator tests. Install it before running preflight; the production app does not require Node.js."
}
Invoke-Checked -Name "Node.js version" -Command {
  node -e "if (Number(process.versions.node.split('.')[0]) < 18) { console.error('Node.js 18+ is required for tests'); process.exit(1); }"
}

Write-Host "== preflight: required files =="
@(
  "backend\main.py",
  "deploy\nginx.conf",
  "deploy\systemd.service"
) | ForEach-Object {
  if (-not (Test-Path -LiteralPath $_)) {
    throw "Missing required file: $_"
  }
}

if (-not (Test-Path -LiteralPath "经营分析模板.html")) {
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
if ($Database) { $env:BUSINESS_ANALYSIS_DB = (Resolve-Path -LiteralPath $Database).Path }
$AuditDatabase = if ($env:BUSINESS_ANALYSIS_DB) { $env:BUSINESS_ANALYSIS_DB } else { Join-Path $Root 'backend\business_data.db' }
if (Test-Path -LiteralPath $AuditDatabase) {
  Invoke-Checked -Name "data quality audit" -Command { & $Python backend\audit_data_quality.py --year $Year }
} else {
  Write-Host 'No business database supplied: code checks complete; business data readiness was not assessed.'
}

Write-Host "preflight ok"
