while ($true) {
    Write-Output "Starting AMD Trading Bot..."
    python deploy.py
    Write-Output "Bot exited or crashed. Restarting in 10 seconds..."
    Start-Sleep -Seconds 10
}
