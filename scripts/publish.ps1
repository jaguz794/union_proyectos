param(
    [string]$Message = "Actualizar portal union proyectos"
)

$ErrorActionPreference = "Stop"

git add .

$hasChanges = $true
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    $hasChanges = $false
}

if (-not $hasChanges) {
    Write-Host "No hay cambios para publicar."
    exit 0
}

git commit -m $Message
git push origin main

Write-Host "Cambios publicados en GitHub. El servidor los tomara automaticamente en el proximo ciclo."
