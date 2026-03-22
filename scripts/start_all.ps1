# start_all.ps1 — Start all local A2A agent servers and the webhook receiver.
#
# Usage (from project root):
#   .\scripts\start_all.ps1
#
# Prerequisites:
#   - Virtual environment created: python -m venv .venv
#   - .env file populated with required variables
#   - Dependencies installed: .venv\Scripts\pip install -r requirements.txt

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# ── Load .env ────────────────────────────────────────────────────────────────
if (Test-Path ".env") {
    Get-Content ".env" | Where-Object { $_ -match '^\s*[^#]\S*=' } | ForEach-Object {
        $k, $v = $_ -split '=', 2
        [System.Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), 'Process')
    }
}

$env:PYTHONPATH = $ProjectRoot
$env:PYTHONUTF8 = "1"

# ── Ensure logs directory exists ──────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path "logs" | Out-Null

# ── Helper ───────────────────────────────────────────────────────────────────
function Start-Agent {
    param (
        [string]$Name,
        [string]$Exe,
        [string]$Arguments,
        [string]$Log
    )
    Write-Host "  Starting $Name..." -NoNewline
    Start-Process `
        -FilePath $Exe `
        -ArgumentList $Arguments `
        -RedirectStandardOutput $Log `
        -RedirectStandardError "$Log.err" `
        -NoNewWindow
    Write-Host " done -> $Log"
}

Write-Host ""
Write-Host "=== A2A Demo: Starting all servers ==="

Start-Agent "weather_agent"  ".venv\Scripts\uvicorn.exe" "weather_agent.agent:app --host 0.0.0.0 --port 8001"  "logs\weather_agent.log"
Start-Agent "research_agent" ".venv\Scripts\uvicorn.exe" "research_agent.agent:app --host 0.0.0.0 --port 8002" "logs\research_agent.log"
Start-Agent "code_agent"     ".venv\Scripts\uvicorn.exe" "code_agent.agent:app --host 0.0.0.0 --port 8003"     "logs\code_agent.log"
Start-Agent "data_agent"     ".venv\Scripts\uvicorn.exe" "data_agent.agent:app --host 0.0.0.0 --port 8004"     "logs\data_agent.log"
Start-Agent "async_agent"    ".venv\Scripts\uvicorn.exe" "async_agent.agent:app --host 0.0.0.0 --port 8005"    "logs\async_agent.log"
Start-Agent "webhook_server" ".venv\Scripts\uvicorn.exe" "webhook_server.main:app --host 0.0.0.0 --port 9000"  "logs\webhook_server.log"
Start-Agent "orchestrator"   ".venv\Scripts\adk.exe"     "web . --port 8080"                                   "logs\orchestrator.log"

Write-Host ""
Write-Host "=== All servers started. Waiting 5s for startup... ==="
Start-Sleep -Seconds 5

# ── Health check ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Health Check ==="
$ports = @{8001="weather_agent"; 8002="research_agent"; 8003="code_agent"; 8004="data_agent"; 8005="async_agent"; 9000="webhook_server"; 8080="orchestrator"}
foreach ($port in $ports.Keys | Sort-Object) {
    $listening = netstat -ano | Select-String ":$port " | Select-String "LISTENING"
    if ($listening) {
        Write-Host "  [OK] :$port $($ports[$port])" -ForegroundColor Green
    } else {
        Write-Host "  [!!] :$port $($ports[$port]) NOT listening" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "  Open http://localhost:8080 in your browser"
Write-Host "  Logs: $ProjectRoot\logs\"
Write-Host "  To stop: .\scripts\stop_all.ps1"
Write-Host ""
