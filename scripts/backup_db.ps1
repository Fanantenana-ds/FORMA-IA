# Script de sauvegarde PostgreSQL — FORMA-IA
# Usage : .\scripts\backup_db.ps1

$ErrorActionPreference = "Stop"

$date = Get-Date -Format "yyyy-MM-dd_HHmmss"
$backupDir = "backups"
$backupFile = "$backupDir\forma_ia_$date.sql"

if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}

Write-Host "Sauvegarde en cours vers $backupFile ..."

docker exec altiora-forma-ia-db-1 pg_dump -U forma_user forma_ia > $backupFile

if ($LASTEXITCODE -eq 0) {
    Write-Host "Sauvegarde reussie : $backupFile"
} else {
    Write-Host "Echec de la sauvegarde"
    exit 1
}