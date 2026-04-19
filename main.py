from fastapi import FastAPI
import random

app = FastAPI()

# Simple dice roller
@app.post("/roll")
def roll_dice(formula: str):
    # only supports 1d10 for now (simple)
    if formula == "1d10":
        roll = random.randint(1, 10)
        return {"result": roll}
    return {"error": "Only 1d10 supported for now"}

# Simple character storage (temporary)
character = {
    "hp": 30,
    "eddies": 100
}

@app.get("/character")
def get_character():
    return character

@app.post("/character/update")
def update_character(hp: int = None, eddies: int = None):
    if hp is not None:
        character["hp"] = hp
    if eddies is not None:
        character["eddies"] = eddies
    return character