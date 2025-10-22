# main.py
from fastapi import FastAPI
import json
import os

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Game Patch Notes Intelligence API", "docs": "/docs"}

@app.get("/patches/latest")
def get_latest_patch(game: str = "Valorant"):
    filename = f"{game.lower()}_latest.json"
    filepath = os.path.join("patches", filename)
    if os.path.exists(filepath):
        try:
            with open(filepath, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"error": "JSON okunamadı", "details": str(e)}
    else:
        return {"error": "En son yama verisi bulunamadı", "expected_file": filepath}

@app.get("/scrape")
def trigger_scrape():
    import subprocess
    try:
        result = subprocess.run(
            ["python", "scrape.py"],
            capture_output=True,
            text=True,
            cwd="."
        )
        if result.returncode == 0:
            return {"status": "success", "output": result.stdout[-500:]}  # Son 500 karakter
        else:
            return {"status": "error", "output": result.stderr[-500:]}
    except Exception as e:
        return {"status": "exception", "error": str(e)}