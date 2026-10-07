# Lance le rangement automatique a chaque ouverture de session Windows (sans fenêtre).
# Usage : powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1
#         powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1 -Uninstall

param([switch]$Uninstall)

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $PSScriptRoot
$shortcutPath = Join-Path ([Environment]::GetFolderPath("Startup")) "Downloads Organizer.lnk"

if ($Uninstall) {
    if (Test-Path $shortcutPath) { Remove-Item $shortcutPath }
    Write-Host "Lancement automatique desactive."
    exit 0
}

$pythonw = Join-Path $projectDir ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
    throw "Environnement virtuel introuvable. Lance d'abord : python -m venv .venv ; .venv\Scripts\pip install -r requirements.txt"
}
if (-not (Test-Path (Join-Path $projectDir "config.yaml"))) {
    throw "config.yaml introuvable. Copie config.example.yaml en config.yaml et adapte-le."
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = "-m organizer watch"
$shortcut.WorkingDirectory = $projectDir
$shortcut.Description = "Range automatiquement le dossier Telechargements"
$shortcut.Save()

Write-Host "OK : le rangement demarrera a la prochaine ouverture de session."
Write-Host "Pour le lancer tout de suite : Start-Process '$pythonw' -ArgumentList '-m organizer watch' -WorkingDirectory '$projectDir'"
