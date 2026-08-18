# Lance le simulateur de fan-out de requêtes dans le navigateur.
# Usage : .\lancer.ps1

$ErrorActionPreference = "Stop"

# Environnement Python, par ordre de preference :
# venv local du projet, puis venv du cabinet, puis python du systeme.
$candidats = @(
    (Join-Path $PSScriptRoot ".venv\Scripts\python.exe"),
    "C:\Users\BenjaminGningue\Documents\IA & SEO\seo_cabinet_env\gsc_api\.venv\Scripts\python.exe"
)

$python = $null
foreach ($c in $candidats) {
    if (Test-Path $c) { $python = $c; break }
}
if (-not $python) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $python = $cmd.Source }
}
if (-not $python) {
    Write-Host "Aucun interpreteur Python trouve." -ForegroundColor Red
    exit 1
}

# Streamlit reclame une adresse email au tout premier demarrage et bloque
# tant qu'on ne repond pas. On neutralise cet ecran une fois pour toutes.
$dossierStreamlit = Join-Path $env:USERPROFILE ".streamlit"
$identifiants = Join-Path $dossierStreamlit "credentials.toml"
if (-not (Test-Path $identifiants)) {
    New-Item -ItemType Directory -Force -Path $dossierStreamlit | Out-Null
    Set-Content -Path $identifiants -Value "[general]`nemail = `"`"" -Encoding utf8
}

if (-not $env:GEMINI_API_KEY) {
    Write-Host "GEMINI_API_KEY absente de ce terminal, la cle sera a saisir dans l'interface." -ForegroundColor Yellow
}

Write-Host "Ouverture de l'interface sur http://localhost:8501" -ForegroundColor Green
& $python -m streamlit run (Join-Path $PSScriptRoot "streamlit_app.py")
