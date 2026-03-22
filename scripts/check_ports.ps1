# check_ports.ps1 — Show status of all A2A demo ports without killing anything.
#
# Usage (from project root):
#   .\scripts\check_ports.ps1

$ports = @{
    8001 = "weather_agent"
    8002 = "research_agent"
    8003 = "code_agent"
    8004 = "data_agent"
    8005 = "async_agent"
    9000 = "webhook_server"
    8080 = "orchestrator"
}

Write-Host ""
Write-Host "=== A2A Demo: Port Status ==="

foreach ($port in $ports.Keys | Sort-Object) {
    $conn = netstat -ano | Select-String ":$port " | Select-String "LISTENING"
    if ($conn) {
        $pid = ($conn.ToString().Trim() -split '\s+')[-1]
        Write-Host "  [RUNNING] :$port  $($ports[$port])  (PID $pid)" -ForegroundColor Green
    } else {
        Write-Host "  [STOPPED] :$port  $($ports[$port])" -ForegroundColor Red
    }
}

Write-Host ""
