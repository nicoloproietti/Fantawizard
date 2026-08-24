"""Pydantic schemas per request/response."""
from __future__ import annotations

from pydantic import BaseModel


class BonusRuleIn(BaseModel):
    code: str
    value: float
    enabled: bool = True


class ModifierIn(BaseModel):
    code: str
    enabled: bool


class RosterSlotIn(BaseModel):
    role: str
    count: int


class BudgetSplitIn(BaseModel):
    role: str
    percentage: float


class TeamIn(BaseModel):
    name: str
    is_user: bool = False


class AuctionCreate(BaseModel):
    name: str
    mode: str = "classic"
    auction_type: str = "chiamata"
    num_teams: int = 8
    initial_credits: int = 500
    num_matchdays: int = 38
    roster_slots: list[RosterSlotIn] = []
    bonus_rules: list[BonusRuleIn] = []
    modifiers: list[ModifierIn] = []
    budget_splits: list[BudgetSplitIn] = []
    teams: list[TeamIn] = []


class PurchaseCreate(BaseModel):
    player_id: int
    team_id: int
    price: int


class WatchlistAdd(BaseModel):
    player_id: int
    priority: int = 0
    notes: str | None = None


class PlayerSearch(BaseModel):
    query: str
    auction_id: int


class PurchaseUndo(BaseModel):
    purchase_id: int
