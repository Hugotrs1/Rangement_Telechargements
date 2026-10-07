# Lance le rangement automatique a chaque ouverture de session Windows, sans fenetre.
#   Installer   : powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1
#   Desinstaller: powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1 -Uninstall

param([switch]$Uninstall)

$project = Split-Path -Parent $PSScriptRoot
$shortcut = Join-Path ([Environment]::GetFolderPath("Startup")) "Downloads Organizer.lnk"

if ($Uninstall) {
    Remove-Item $shortcut -ErrorAction SilentlyContinue
    Write-Host "Lancement automatique desactive."
    exit
}

$pythonw = Join-Path $project ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) { throw "Cree d'abord l'environnement Python (.venv) : voir le README." }
if (-not (Test-Path (Join-Path $project "config.yaml"))) { throw "Cree d'abord config.yaml (copie de config.example.yaml)." }

$link = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcut)
$link.TargetPath = $pythonw
$link.Arguments = "main.py watch"
$link.WorkingDirectory = $project
$link.Save()

Write-Host "OK : le rangement se lancera a chaque demarrage de Windows."
