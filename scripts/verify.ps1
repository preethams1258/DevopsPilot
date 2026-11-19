$ErrorActionPreference = 'Continue'
$checks = @(
    @{Name='Platform API'; Url='http://localhost:8000/health'},
    @{Name='Monitored API'; Url='http://localhost:8001/health'},
    @{Name='Demo Shop'; Url='http://localhost:8080'},
    @{Name='Prometheus'; Url='http://localhost:9090/-/healthy'},
    @{Name='Loki'; Url='http://localhost:3100/ready'},
    @{Name='Jaeger'; Url='http://localhost:16686'}
)
foreach ($check in $checks) {
    try {
        $response = Invoke-WebRequest -Uri $check.Url -TimeoutSec 5 -UseBasicParsing
        Write-Host "PASS $($check.Name) ($($response.StatusCode))" -ForegroundColor Green
    } catch {
        Write-Host "FAIL $($check.Name): $($_.Exception.Message)" -ForegroundColor Red
    }
}
