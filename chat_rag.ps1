# ============================================================
# CHAT RAG — Interface terminal pour FORMA-IA
# Usage : cd C:\PROJET_FANA\FORMA_IA\backend  puis  .\chat_rag.ps1
# Quitter : taper "exit" ou Ctrl+C
# ============================================================

# Forcer la page de code UTF-8 (résout les caractères Ã© / â€" dans le terminal)
& chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$token = (Get-Content "C:\PROJET_FANA\FORMA_IA\backend\.env" | Where-Object { $_ -match "^SHARED_INTERNAL_TOKEN=" }) -replace "^SHARED_INTERNAL_TOKEN=",""
$url   = "http://127.0.0.1:8000/api/v1/ia/rag/chat"
$conv_id = $null

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  FORMA-IA -- Assistant documentaire RAG" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  Tape ton message et appuie sur Entree." -ForegroundColor Gray
Write-Host "  Tape 'exit' pour quitter." -ForegroundColor Gray
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

while ($true) {
    Write-Host "Toi : " -ForegroundColor Yellow -NoNewline
    $message = Read-Host

    if ($message -eq "") { continue }
    if ($message -match "^(exit|quitter|quit|bye)$") {
        Write-Host ""
        Write-Host "Au revoir !" -ForegroundColor Cyan
        break
    }

    $bodyObj = @{ message = $message }
    if ($conv_id) { $bodyObj["conversation_id"] = $conv_id }
    $bodyJson = $bodyObj | ConvertTo-Json -Compress
    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyJson)

    try {
        # Invoke-RestMethod dans PS 5.1 décode la réponse en Latin-1 même quand
        # le serveur envoie UTF-8. On passe par Invoke-WebRequest + décodage
        # manuel pour obtenir les accents correctement.
        $raw = Invoke-WebRequest -Uri $url -Method POST `
            -Headers @{ "Authorization" = "Bearer $token"; "Content-Type" = "application/json; charset=utf-8" } `
            -Body $bodyBytes -UseBasicParsing
        $r = [System.Text.Encoding]::UTF8.GetString($raw.Content) | ConvertFrom-Json

        $conv_id = $r.conversation_id

        Write-Host ""
        Write-Host "Assistant [$($r.type_reponse)] : " -ForegroundColor Green -NoNewline
        Write-Host $r.reponse
        Write-Host ""

        if ($r.sources -and $r.sources.Count -gt 0) {
            Write-Host "  Sources :" -ForegroundColor DarkGray
            foreach ($s in $r.sources) {
                $ligne = "    - "
                if ($s.fichier) { $ligne += $s.fichier }
                if ($s.page)    { $ligne += " (page $($s.page))" }
                if ($s.score)   { $ligne += " [score: $([math]::Round($s.score, 2))]" }
                Write-Host $ligne -ForegroundColor DarkGray
            }
            Write-Host ""
        }

        if ($r.suggestions -and $r.suggestions.Count -gt 0) {
            Write-Host "  Suggestions :" -ForegroundColor DarkCyan
            foreach ($s in $r.suggestions) {
                Write-Host "    > $s" -ForegroundColor DarkCyan
            }
            Write-Host ""
        }

    } catch {
        Write-Host ""
        Write-Host "Erreur : $($_.Exception.Message)" -ForegroundColor Red
        Write-Host ""
    }
}
