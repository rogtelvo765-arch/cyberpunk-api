from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Night City Referee API",
    version="3.0.0",
    servers=[{"url": "https://cyberpunk-api-4vse.onrender.com"}],
)

DATA_DIR = Path("data")
CHARACTER_DIR = DATA_DIR / "characters"
CAMPAIGN_DIR = DATA_DIR / "campaigns"

CHARACTER_DIR.mkdir(parents=True, exist_ok=True)
CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Helpers
# -----------------------------

def safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", value.strip())


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_json(path: Path, data: dict[str, Any]):
    path.write_text(json.dumps(data, indent=2))


def roll_dice_formula(formula: str):
    match = re.match(r"(\d+)d(\d+)([+-]\d+)?", formula)
    if not match:
        raise ValueError("Invalid dice")

    num = int(match.group(1))
    size = int(match.group(2))
    mod = int(match.group(3) or 0)

    rolls = [random.randint(1, size) for _ in range(num)]
    return rolls, sum(rolls) + mod


# -----------------------------
# Models
# -----------------------------

class RollRequest(BaseModel):
    formula: str


class RollResponse(BaseModel):
    total: int
    rolls: list[int]


class WeaponStatBlock(BaseModel):
    name: str
    damage: str | None = None
    accuracy: int | None = None
    reliability: str | None = None
    manufacturer: str | None = None
    rarity: str | None = None
    notes: str | None = None


class CharacterState(BaseModel):
    character_id: str
    name: str | None = None
    hp: int | None = None
    max_hp: int | None = None
    eddies: int | None = None

    weapons: list[str] | None = None
    ammo: dict[str, int] | None = None
    cyberware: list[str] | None = None
    loot: list[str] | None = None

    weapon_stats: list[WeaponStatBlock] | None = None


class InventoryAction(BaseModel):
    character_id: str

    add_weapons: list[str] | None = None
    remove_weapons: list[str] | None = None

    add_ammo: dict[str, int] | None = None
    remove_ammo: dict[str, int] | None = None
    set_ammo: dict[str, int] | None = None

    add_cyberware: list[str] | None = None
    remove_cyberware: list[str] | None = None

    add_loot: list[str] | None = None
    remove_loot: list[str] | None = None


class WeaponStatsUpdateRequest(BaseModel):
    character_id: str
    weapon: WeaponStatBlock


# -----------------------------
# Routes
# -----------------------------

@app.post("/roll", response_model=RollResponse)
def roll(payload: RollRequest):
    rolls, total = roll_dice_formula(payload.formula)
    return RollResponse(total=total, rolls=rolls)


@app.post("/character/update")
def update_character(payload: CharacterState):
    path = CHARACTER_DIR / f"{safe_id(payload.character_id)}.json"
    data = load_json(path)

    data.update({k: v for k, v in payload.model_dump().items() if v is not None})

    save_json(path, data)
    return {"success": True}


@app.get("/character/get")
def get_character(character_id: str):
    path = CHARACTER_DIR / f"{safe_id(character_id)}.json"
    data = load_json(path)
    if not data:
        raise HTTPException(404, "Character not found")
    return data


# 🔥 SMART INVENTORY
@app.post("/character/inventory")
def inventory(payload: InventoryAction):
    path = CHARACTER_DIR / f"{safe_id(payload.character_id)}.json"
    data = load_json(path)

    if not data:
        raise HTTPException(404, "Character not found")

    weapons = data.get("weapons") or []
    ammo = data.get("ammo") or {}
    cyberware = data.get("cyberware") or []
    loot = data.get("loot") or []

    if payload.add_weapons:
        for w in payload.add_weapons:
            if w not in weapons:
                weapons.append(w)

    if payload.remove_weapons:
        weapons = [w for w in weapons if w not in payload.remove_weapons]

    if payload.add_ammo:
        for w, amt in payload.add_ammo.items():
            ammo[w] = ammo.get(w, 0) + amt

    if payload.remove_ammo:
        for w, amt in payload.remove_ammo.items():
            ammo[w] = max(0, ammo.get(w, 0) - amt)

    if payload.set_ammo:
        for w, amt in payload.set_ammo.items():
            ammo[w] = amt

    if payload.add_cyberware:
        for c in payload.add_cyberware:
            if c not in cyberware:
                cyberware.append(c)

    if payload.remove_cyberware:
        cyberware = [c for c in cyberware if c not in payload.remove_cyberware]

    if payload.add_loot:
        for l in payload.add_loot:
            if l not in loot:
                loot.append(l)

    if payload.remove_loot:
        loot = [l for l in loot if l not in payload.remove_loot]

    data["weapons"] = weapons
    data["ammo"] = ammo
    data["cyberware"] = cyberware
    data["loot"] = loot

    save_json(path, data)

    return {"success": True}


# 🔥 WEAPON STATS SYSTEM
@app.post("/character/weapon_stats")
def update_weapon_stats(payload: WeaponStatsUpdateRequest):
    path = CHARACTER_DIR / f"{safe_id(payload.character_id)}.json"
    data = load_json(path)

    if not data:
        raise HTTPException(404, "Character not found")

    stats = data.get("weapon_stats") or []

    updated = False
    for i, w in enumerate(stats):
        if w.get("name") == payload.weapon.name:
            stats[i] = payload.weapon.model_dump()
            updated = True
            break

    if not updated:
        stats.append(payload.weapon.model_dump())

    data["weapon_stats"] = stats
    save_json(path, data)

    return {"success": True}
