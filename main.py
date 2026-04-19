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
    version="1.0.0",
    description="Dice rolling, character tracking, and campaign state management for a Cyberpunk 2020 GPT.",
    servers=[
        {"url": "https://cyberpunk-api-4vse.onrender.com"}
    ],
)

DATA_DIR = Path("data")
CHARACTER_DIR = DATA_DIR / "characters"
CAMPAIGN_DIR = DATA_DIR / "campaigns"

CHARACTER_DIR.mkdir(parents=True, exist_ok=True)
CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)

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


def merge_patch(existing: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    for key, value in updates.items():
        if value is not None:
            existing[key] = value
    return existing


def parse_dice_formula(formula: str) -> tuple[int, int, int]:
    match = DICE_PATTERN.match(formula)
    if not match:
        raise ValueError("Invalid dice formula. Use formats like 1d10, 2d6+3, 3d6-1.")
    num_dice = int(match.group(1))
    die_size = int(match.group(2))
    modifier = int(match.group(3) or 0)

    if num_dice < 1 or num_dice > 100:
        raise ValueError("Number of dice must be between 1 and 100.")
    if die_size < 2 or die_size > 1000:
        raise ValueError("Die size must be between 2 and 1000.")

    return num_dice, die_size, modifier


class RootResponse(BaseModel):
    status: str
    service: str


class RollRequest(BaseModel):
    formula: str = Field(..., examples=["1d10", "2d6+3"])
    reason: str | None = None


class RollResponse(BaseModel):
    formula: str
    rolls: list[int]
    modifier: int
    total: int
    reason: str | None = None


class CharacterState(BaseModel):
    character_id: str
    name: str | None = None
    hp: int | None = None
    max_hp: int | None = None
    wounds: str | None = None
    eddies: int | None = None
    humanity: int | None = None
    reputation: int | None = None
    inventory_notes: str | None = None
    status_notes: str | None = None

    weapons: list[str] | None = None
    ammo: dict[str, int] | None = None
    cyberware: list[str] | None = None
    loot: list[str] | None = None


class CharacterUpdateResponse(BaseModel):
    success: bool
    character_id: str
    message: str


class CampaignState(BaseModel):
    campaign_id: str
    session_id: str | None = None
    district: str | None = None
    world_notes: str | None = None
    faction_status: str | None = None
    npc_notes: str | None = None
    heat: int | None = None


class CampaignUpdateResponse(BaseModel):
    success: bool
    campaign_id: str
    message: str


@app.get("/", response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(
        status="ok",
        service="Night City Referee Actions API",
    )


@app.post("/roll", response_model=RollResponse)
def roll_dice(payload: RollRequest) -> RollResponse:
    try:
        num_dice, die_size, modifier = parse_dice_formula(payload.formula)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    rolls = [random.randint(1, die_size) for _ in range(num_dice)]
    total = sum(rolls) + modifier

    return RollResponse(
        formula=payload.formula,
        rolls=rolls,
        modifier=modifier,
        total=total,
        reason=payload.reason,
    )


@app.get("/character/get", response_model=CharacterState)
def get_character_state(character_id: str) -> CharacterState:
    try:
        char_id = safe_id(character_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    path = CHARACTER_DIR / f"{char_id}.json"
    data = load_json(path)

    if not data:
        raise HTTPException(status_code=404, detail="Character not found.")

    return CharacterState(**data)


@app.post("/character/update", response_model=CharacterUpdateResponse)
def update_character_state(payload: CharacterState) -> CharacterUpdateResponse:
    try:
        char_id = safe_id(payload.character_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    path = CHARACTER_DIR / f"{char_id}.json"
    existing = load_json(path)

    updates = payload.model_dump()
    updates["character_id"] = char_id

    merged = merge_patch(existing, updates)
    save_json(path, merged)

    return CharacterUpdateResponse(
        success=True,
        character_id=char_id,
        message="Character state updated.",
    )


@app.get("/campaign/load", response_model=CampaignState)
def load_campaign_state(campaign_id: str) -> CampaignState:
    try:
        camp_id = safe_id(campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    path = CAMPAIGN_DIR / f"{camp_id}.json"
    data = load_json(path)

    if not data:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    return CampaignState(**data)


@app.post("/campaign/save", response_model=CampaignUpdateResponse)
def save_campaign_state(payload: CampaignState) -> CampaignUpdateResponse:
    try:
        camp_id = safe_id(payload.campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    path = CAMPAIGN_DIR / f"{camp_id}.json"
    existing = load_json(path)

    updates = payload.model_dump()
    updates["campaign_id"] = camp_id

    merged = merge_patch(existing, updates)
    save_json(path, merged)

    return CampaignUpdateResponse(
        success=True,
        campaign_id=camp_id,
        message="Campaign state saved.",
    )
