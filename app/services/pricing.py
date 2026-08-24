"""Motore pricing: proiezione punti, prezzo atteso, aggiornamento dinamico."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import (
    Auction,
    BonusRule,
    BudgetSplit,
    Modifier,
    Player,
    PlayerSeason,
    Purchase,
    RosterSlot,
    Team,
)

SEASON_WEIGHTS = [0.50, 0.30, 0.20]

STAT_TO_BONUS_CODE: dict[str, str] = {
    "goals": "GOL",
    "assists": "ASSIST",
    "assists_set_piece": "ASSIST_FERMO",
    "penalties_scored": "RIGORE_SEGNATO",
    "penalties_taken_missed": "RIGORE_SBAGLIATO",
    "penalties_saved": "RIGORE_PARATO",
    "yellow_cards": "AMMONIZIONE",
    "red_cards": "ESPULSIONE",
    "own_goals": "AUTOGOL",
    "goals_conceded": "GOL_SUBITO",
    "clean_sheets": "PORTA_INVIOLATA",
    "winning_goals": "GOL_VITTORIA",
    "equalizing_goals": "GOL_PAREGGIO",
    "shots_on_post": "PALO_TRAVERSA",
    "penalties_won": "RIGORE_CONQUISTATO",
    "penalties_caused": "RIGORE_CAUSATO",
    "saves_decisive": "SALVATAGGIO",
    "errors_decisive": "ERRORE_DECISIVO",
    "goals_outside_box": "GOL_FUORI_AREA",
}


@dataclass
class PlayerProjection:
    player_id: int
    name: str
    team: str
    role: str
    fma: float
    base_price: float
    recommended_price: float
    max_bid: int
    tier: int
    convenience_index: float | None = None


def _bonus_map(auction_id: int, db: Session) -> dict[str, float]:
    rules = db.query(BonusRule).filter(
        BonusRule.auction_id == auction_id,
        BonusRule.enabled == True,  # noqa: E712
    ).all()
    return {r.code: r.value for r in rules}


def _modifier_flags(auction_id: int, db: Session) -> dict[str, bool]:
    mods = db.query(Modifier).filter(Modifier.auction_id == auction_id).all()
    return {m.code: m.enabled for m in mods}


def _season_stats(player_id: int, db: Session) -> list[PlayerSeason]:
    return (
        db.query(PlayerSeason)
        .filter(PlayerSeason.player_id == player_id)
        .order_by(PlayerSeason.season.desc())
        .limit(3)
        .all()
    )


def _weighted_stat(seasons: list[PlayerSeason], attr: str) -> float:
    vals = [getattr(s, attr, 0) or 0 for s in seasons]
    weights = SEASON_WEIGHTS[: len(vals)]
    if not weights:
        return 0.0
    total_w = sum(weights)
    return sum(v * w for v, w in zip(vals, weights)) / total_w


def project_fma(
    player: Player,
    seasons: list[PlayerSeason],
    bonus_map: dict[str, float],
    modifiers: dict[str, bool],
) -> float:
    if not seasons:
        return 0.0

    avg_rating = _weighted_stat(seasons, "avg_rating")
    appearances = _weighted_stat(seasons, "appearances")
    if appearances < 1:
        return 0.0

    bonus_total = 0.0
    for stat_attr, code in STAT_TO_BONUS_CODE.items():
        bval = bonus_map.get(code, 0.0)
        if bval == 0.0:
            continue

        if stat_attr == "penalties_taken_missed":
            taken = _weighted_stat(seasons, "penalties_taken")
            scored = _weighted_stat(seasons, "penalties_scored")
            count = taken - scored
        else:
            count = _weighted_stat(seasons, stat_attr)

        bonus_total += count * bval / appearances if appearances > 0 else 0.0

    fma = avg_rating + bonus_total

    if modifiers.get("MOD_DIFESA") and player.role_classic in ("P", "D"):
        fma += 0.15 * max(0, avg_rating - 5.5)
    if modifiers.get("MOD_PORTIERE") and player.role_classic == "P":
        fma += 0.1 * max(0, avg_rating - 5.5)

    return round(fma, 2)


def base_price_from_fma(
    fma: float,
    role: str,
    initial_credits: int,
    num_teams: int,
    total_slots: int,
) -> float:
    if fma <= 0:
        return 1.0

    credits_pool = initial_credits * num_teams
    credits_per_slot = credits_pool / max(total_slots * num_teams, 1)

    role_weight = {"P": 0.6, "D": 0.8, "C": 1.0, "A": 1.3}.get(role, 1.0)
    raw = (fma - 4.5) ** 1.8 * role_weight * credits_per_slot * 0.35

    return max(1.0, round(raw, 0))


def compute_inflation(auction_id: int, db: Session) -> dict[str, float]:
    purchases = (
        db.query(Purchase)
        .filter(Purchase.auction_id == auction_id)
        .all()
    )
    if not purchases:
        return {}

    bonus_map = _bonus_map(auction_id, db)
    modifiers = _modifier_flags(auction_id, db)
    auction = db.query(Auction).get(auction_id)
    slots = db.query(RosterSlot).filter(RosterSlot.auction_id == auction_id).all()
    total_slots = sum(s.count for s in slots)

    by_role: dict[str, list[tuple[float, float]]] = {}
    for p in purchases:
        player = db.query(Player).get(p.player_id)
        if not player:
            continue
        seasons = _season_stats(player.id, db)
        fma = project_fma(player, seasons, bonus_map, modifiers)
        bp = base_price_from_fma(
            fma, player.role_classic,
            auction.initial_credits, auction.num_teams, total_slots,
        )
        role = player.role_classic
        by_role.setdefault(role, []).append((p.price, bp))

    inflation: dict[str, float] = {}
    for role, pairs in by_role.items():
        sum_paid = sum(paid for paid, _ in pairs)
        sum_expected = sum(exp for _, exp in pairs)
        inflation[role] = sum_paid / sum_expected if sum_expected > 0 else 1.0

    return inflation


def compute_scarcity(
    auction_id: int,
    role: str,
    tier: int,
    tier_map: dict[int, list],
    db: Session,
) -> float:
    sold_ids = {
        p.player_id
        for p in db.query(Purchase).filter(Purchase.auction_id == auction_id).all()
    }
    raw = tier_map.get(tier, [])
    player_ids_in_tier = [
        (e["player_id"] if isinstance(e, dict) else e) for e in raw
    ]
    remaining = [pid for pid in player_ids_in_tier if pid not in sold_ids]
    total = len(player_ids_in_tier)
    if total == 0:
        return 1.0
    ratio = len(remaining) / total
    if ratio > 0.5:
        return 1.0
    return 1.0 + (0.5 - ratio) * 0.6


def compute_recommended_price(
    base_price: float,
    role: str,
    tier: int,
    inflation: dict[str, float],
    scarcity: float,
    budget_residuo: int,
) -> float:
    infl = inflation.get(role, 1.0)
    raw = base_price * infl * scarcity
    return max(1.0, min(round(raw, 0), budget_residuo))


def max_bid(
    auction: Auction,
    user_team: Team,
    db: Session,
) -> int:
    purchases = (
        db.query(Purchase)
        .filter(Purchase.auction_id == auction.id, Purchase.team_id == user_team.id)
        .all()
    )
    spent = sum(p.price for p in purchases)
    bought = len(purchases)
    slots = db.query(RosterSlot).filter(RosterSlot.auction_id == auction.id).all()
    total_slots = sum(s.count for s in slots)
    remaining_slots = total_slots - bought
    if remaining_slots <= 0:
        return 0
    budget_left = auction.initial_credits - spent
    return max(0, budget_left - (remaining_slots - 1))


def convenience_index(recommended: float, called_price: float) -> float:
    if called_price <= 0:
        return 99.0
    return round(recommended / called_price, 2)


def budget_status(auction: Auction, user_team: Team, db: Session) -> dict:
    purchases = (
        db.query(Purchase)
        .filter(Purchase.auction_id == auction.id, Purchase.team_id == user_team.id)
        .all()
    )
    spent = sum(p.price for p in purchases)
    slots = db.query(RosterSlot).filter(RosterSlot.auction_id == auction.id).all()
    total_slots = sum(s.count for s in slots)

    splits = {
        bs.role: bs.percentage
        for bs in db.query(BudgetSplit).filter(BudgetSplit.auction_id == auction.id).all()
    }

    bought_by_role: dict[str, list[int]] = {}
    for p in purchases:
        player = db.query(Player).get(p.player_id)
        if player:
            bought_by_role.setdefault(player.role_classic, []).append(p.price)

    slot_map = {s.role: s.count for s in slots}
    result: dict[str, dict] = {}
    for role, count in slot_map.items():
        pct = splits.get(role, 0.0)
        budget_role = auction.initial_credits * pct / 100.0
        spent_role = sum(bought_by_role.get(role, []))
        bought_count = len(bought_by_role.get(role, []))
        result[role] = {
            "budget_allocated": round(budget_role),
            "spent": spent_role,
            "remaining": round(budget_role - spent_role),
            "slots_total": count,
            "slots_filled": bought_count,
            "slots_remaining": count - bought_count,
        }

    return {
        "total_budget": auction.initial_credits,
        "total_spent": spent,
        "total_remaining": auction.initial_credits - spent,
        "total_slots": total_slots,
        "total_bought": len(purchases),
        "by_role": result,
    }
