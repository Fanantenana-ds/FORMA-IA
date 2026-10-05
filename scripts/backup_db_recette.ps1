# Script de sauvegarde PostgreSQL — Environnement de RECETTE
# Usage : .\scripts\backup_db_recette.ps1

$ErrorActionPreference = "Stop"

$date = Get-Date -Format "yyyy-MM-dd_HHmmss"
$backupDir = "backups"
$backupFile = "$backupDir\forma_ia_recette_$date.sql"

if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}

Write-Host "Sauvegarde recette en cours vers $backupFile ..."

docker exec altiora-forma-ia-db-1 pg_dump -U forma_user forma_ia_recette > $backupFile

if ($LASTEXITCODE -eq 0) {
    Write-Host "Sauvegarde reussie : $backupFile"
} else {
    Write-Host "Echec de la sauvegarde"
    exit 1
}# Script de sauvegarde PostgreSQL — Environnement de RECETTE
# Usage : .\scripts\backup_db_recette.ps1

$ErrorActionPreference = "Stop"

$date = Get-Date -Format "yyyy-MM-dd_HHmmss"
$backupDir = "backups"
$backupFile = "$backupDir\forma_ia_recette_$date.sql"

if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}

Write-Host "Sauvegarde recette en cours vers $backupFile ..."

docker exec altiora-forma-ia-db-1 pg_dump -U forma_user forma_ia_recette > $backupFile

if ($LASTEXITCODE -eq 0) {
    Write-Host "Sauvegarde reussie : $backupFile"
} else {
    Write-Host "Echec de la sauvegarde"
    exit 1
}