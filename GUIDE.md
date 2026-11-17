# Guide d'installation (Windows)

```powershell
cd D:\Documents\Hugotrs1\Perso\downloads-organizer
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.yaml config.yaml
```

Adapte `config.yaml` si besoin, puis :

```powershell
python main.py sort --dry-run   # montre ce qui serait rangé, sans rien déplacer
python main.py sort             # range
python main.py undo             # annule
```

Pour qu'il se lance au démarrage de Windows :

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1
```
