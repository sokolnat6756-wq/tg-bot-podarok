# Создаёт bot-deploy.tgz без .env и .venv. Запускать из корня проекта.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$out = Join-Path $root "bot-deploy.tgz"
if (Test-Path $out) { Remove-Item $out -Force }

# tar есть в Windows 10+
tar --exclude=".env" `
    --exclude=".venv" `
    --exclude="venv" `
    --exclude="__pycache__" `
    --exclude=".git" `
    --exclude="bot-deploy.tgz" `
    --exclude="bot/fonts/_preview_*.png" `
    -czf $out .

Write-Host "Готово: $out"
Write-Host "Далее (подставьте свой IP):"
Write-Host "  scp bot-deploy.tgz root@ВАШ_IP:/root/"
