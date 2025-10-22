from fastapi import FastAPI
import json
import os

app = FastAPI()

@app.get("/patches")
def get_patches(game: str = None):
    patches = []
    patches_dir = "patches"
    if not os.path.exists(patches_dir):
        return {"error": "patches klasörü bulunamadı!"}
    for file in os.listdir(patches_dir):
        if file.endswith(".json"):
            try:
                with open(os.path.join(patches_dir, file), encoding='utf-8') as f:
                    data = json.load(f)
                    if game is None or data.get("game", "").lower() == game.lower():
                        patches.append(data)
            except Exception as e:
                continue
    return patches