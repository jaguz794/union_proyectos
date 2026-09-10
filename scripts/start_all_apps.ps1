$ErrorActionPreference = "Stop"

$PortalRoot = Split-Path -Parent $PSScriptRoot

function Start-AppWindow {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )
    Start-Process powershell.exe -WorkingDirectory $WorkingDirectory -ArgumentList @(
        "-NoExit",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        $Command
    )
    Write-Host "$Title iniciado."
}

Start-AppWindow "Portal" $PortalRoot "python portal.py --host 127.0.0.1 --port 9000"

Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:9000"

Write-Host ""
Write-Host "Portal:               http://127.0.0.1:9000"
Write-Host "Portal de Horarios:              http://192.168.10.7:8010"
Write-Host "Conciliador de Costos:           http://192.168.10.9:5173"
Write-Host "Conciliador Cierre de Cajas:     http://192.168.10.7:8017"
Write-Host "Portal de Compras y RRHH:        http://192.168.10.7:3000"
Write-Host "Revisor de Ofertas:              temporal en construccion"
