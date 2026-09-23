param([string]$Question = '')
$ErrorActionPreference = 'Stop'
$credentialPath = Join-Path $env:LOCALAPPDATA 'BusinessAnalysis/hermes-api-key.xml'
if (-not (Test-Path -LiteralPath $credentialPath)) {
    throw 'Hermes credential is not configured for this Windows user. See docs/HERMES_RESEARCH.md.'
}
$secureKey = Import-Clixml -LiteralPath $credentialPath
$credential = [System.Management.Automation.PSCredential]::new('hermes', $secureKey)
$previousKey = $env:MARKET_ANALYSIS_HERMES_API_KEY
$previousEncoding = $env:PYTHONIOENCODING
try {
    $env:MARKET_ANALYSIS_HERMES_API_KEY = $credential.GetNetworkCredential().Password
    $env:PYTHONIOENCODING = 'utf-8'
    python (Join-Path $PSScriptRoot 'invoke_hermes_research.py') --question $Question
    if ($LASTEXITCODE -ne 0) { throw 'Hermes research request failed.' }
} finally {
    $env:MARKET_ANALYSIS_HERMES_API_KEY = $previousKey
    $env:PYTHONIOENCODING = $previousEncoding
}
