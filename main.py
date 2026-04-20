from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="Night City Referee Actions API",
    version="2.0.0",
    description="Cyberpunk 2020 backend with dice, character, campaign, and smart inventory.",
    servers=[
        {"url": "https://cyberpunk-api-4vse.onrender.com"}
    ],
)

DATA_DIR = Path("data")
CHARACTER_DIR = DATA_DIR / "characters"
CAMPAIGN_DIR = DATA_DIR / "campaigns"

CHARACTER_DIR.mkdir(parents=True, exist_ok=True)
CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Helpers
# -----------------------------

DICE_PATTERN = re.compile(r"^\s*(\d+)d(\d+)([+-]\d+)?\s*$")


def safe_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "_", value.strip())
    if not cleaned:
        raise ValueError("Identifier cannot be empty.")
    return cleaned


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def parse_dice_formula(formula: str):
    match = DICE_PATTERN.match(formula)
    if not match:
        raise ValueError("Invalid dice formula.")

    num_dice = int(match.group(1))
    die_size = int(match.group(2))
    modifier = int(match.group(3) or 0)

    return num_dice, die_size, modifier


# -----------------------------
# Models
# -----------------------------

class RootResponse(BaseModel):
    status: str
    service: str


class RollRequest(BaseModel):
    formula: str
    reason: str | None = None


class RollResponse(BaseModel):
    total: int
    rolls: list[int]


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


class SimpleResponse(BaseModel):
    success: bool
    message: str


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


class CampaignState(BaseModel):
    campaign_id: str
    world_notes: str | None = None


# -----------------------------
# Routes
# -----------------------------

@app.get("/", response_model=RootResponse)
def root():
    return RootResponse(status="ok", service="Cyberpunk API")


# 🎲 Dice
@app.post("/roll", response_model=RollResponse)
def roll(payload: RollRequest):
    num, size, mod = parse_dice_formula(payload.formula)
    rolls = [random.randint(1, size) for _ in range(num)]
    return RollResponse(total=sum(rolls) + mod, rolls=rolls)


# 🧍 Character
@app.post("/character/update", response_model=SimpleResponse)
def update_character(payload: CharacterState):
    char_id = safe_id(payload.character_id)
    path = CHARACTER_DIR / f"{char_id}.json"

    data = load_json(path)
    new_data = payload.model_dump()

    data.update({k: v for k, v in new_data.items() if v is not None})

    save_json(path, data)

    return SimpleResponse(success=True, message="Character updated")


@app.get("/character/get")
def get_character(character_id: str):
    path = CHARACTER_DIR / f"{safe_id(character_id)}.json"
    data = load_json(path)

    if not data:
        raise HTTPException(404, "Character not found")

    return data


# 🎒 Smart Inventory
@app.post("/character/inventory", response_model=SimpleResponse)
def inventory(payload: InventoryAction):
    char_id = safe_id(payload.character_id)
    path = CHARACTER_DIR / f"{char_id}.json"

    data = load_json(path)
    if not data:
        raise HTTPException(404, "Character not found")

    weapons = data.get("weapons") or []
    ammo = data.get("ammo") or {}
    cyberware = data.get("cyberware") or []
    loot = data.get("loot") or []

    # Weapons
    if payload.add_weapons:
        weapons += [w for w in payload.add_weapons if w not in weapons]

    if payload.remove_weapons:
        weapons = [w for w in weapons if w not in payload.remove_weapons]

    # Ammo
      if payload.add_ammo:
        for w, amt in payload.add_ammo.items():
            ammo[w] = ammo.get(w, 0) + amt

    if payload.remove_ammo:
        for w, amt in payload.remove_ammo.items():
            ammo[w] = max(0, ammo.get(w, 0) - amt)

    if payload.set_ammo:
        for w, amt in payload.set_ammo.items():
            ammo[w] = amt

    # Cyberware
    if payload.add_cyberware:
        cyberware += [c for c in payload.add_cyberware if c not in cyberware]

    if payload.remove_cyberware:
        cyberware = [c for c in cyberware if c not in payload.remove_cyberware]

    # Loot
    if payload.add_loot:
        loot += [l for l in payload.add_loot if l not in loot]

    if payload.remove_loot:
        loot = [l for l in loot if l not in payload.remove_loot]

    data["weapons"] = weapons
    data["ammo"] = ammo
    data["cyberware"] = cyberware
    data["loot"] = loot

    save_json(path, data)

    return SimpleResponse(success=True, message="Inventory updated")


# 🌆 Campaign
@app.post("/campaign/save", response_model=SimpleResponse)
def save_campaign(payload: CampaignState):
    path = CAMPAIGN_DIR / f"{safe_id(payload.campaign_id)}.json"
    save_json(path, payload.model_dump())
    return SimpleResponse(success=True, message="Saved")


@app.get("/campaign/load")
def load_campaign(campaign_id: str):
    path = CAMPAIGN_DIR / f"{safe_id(campaign_id)}.json"
    return load_json(path)
