# stop_all.ps1 — Stop all local A2A agent servers and free their ports.
#
# Usage (from project root):
#   .\scripts\stop_all.ps1

Write-Host ""
Write-Host "=== A2A Demo: Stopping all servers ==="

$ports = @{8001="weather_agent"; 8002="research_agent"; 8003="code_agent"; 8004="data_agent"; 8005="async_agent"; 9000="webhook_server"; 8080="orchestrator"}

foreach ($port in $ports.Keys | Sort-Object) {
    $conn = netstat -ano | Select-String ":$port " | Select-String "LISTENING"
    if ($conn) {
        $procId = ($conn.ToString().Trim() -split '\s+')[-1]
        try {
            taskkill /PID $procId /F | Out-Null
            Write-Host "  [OK] Stopped :$port $($ports[$port]) (PID $procId)" -ForegroundColor Green
        } catch {
            Write-Host "  [!!] Failed to stop :$port (PID $procId): $_" -ForegroundColor Red
        }
    } else {
        Write-Host "  [--] :$port $($ports[$port]) was not running" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "=== All servers stopped ==="
Write-Host ""
