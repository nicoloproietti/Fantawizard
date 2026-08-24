"""Tier list: fasce 1-4 per ruolo basate su FMA."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Auction, Player, PlayerSeason, Purchase
from app.services.pricing import (
    _bonus_map,
    _modifier_flags,
    _season_stats,
    project_fma,
)

TIER_THRESHOLDS = [0.15, 0.40, 0.70]


def build_tier_map(
    auction_id: int,
    db: Session,
) -> dict[str, dict[int, list[dict]]]:
    bonus_map = _bonus_map(auction_id, db)
    modifiers = _modifier_flags(auction_id, db)

    sold_ids = {
        p.player_id
        for p in db.query(Purchase).filter(Purchase.auction_id == auction_id).all()
    }

    players = db.query(Player).filter(Player.active == True).all()  # noqa: E712

    by_role: dict[str, list[tuple[float, Player]]] = {}
    for pl in players:
        seasons = _season_stats(pl.id, db)
        fma = project_fma(pl, seasons, bonus_map, modifiers)
        by_role.setdefault(pl.role_classic, []).append((fma, pl))

    result: dict[str, dict[int, list[dict]]] = {}
    tier_id_map: dict[str, dict[int, list[int]]] = {}

    for role, items in by_role.items():
        items.sort(key=lambda x: x[0], reverse=True)
        n = len(items)
        tiers: dict[int, list[dict]] = {1: [], 2: [], 3: [], 4: []}
        tid_map: dict[int, list[int]] = {1: [], 2: [], 3: [], 4: []}

        for i, (fma, pl) in enumerate(items):
            pct = i / n if n > 0 else 1.0
            if pct < TIER_THRESHOLDS[0]:
                tier = 1
            elif pct < TIER_THRESHOLDS[1]:
                tier = 2
            elif pct < TIER_THRESHOLDS[2]:
                tier = 3
            else:
                tier = 4

            tiers[tier].append({
                "player_id": pl.id,
                "name": pl.name,
                "team": pl.team,
                "role": pl.role_classic,
                "fma": fma,
                "sold": pl.id in sold_ids,
                "tier": tier,
            })
            tid_map[tier].append(pl.id)

        result[role] = tiers
        tier_id_map[role] = tid_map

    return result


def get_player_tier(
    player_id: int,
    role: str,
    tier_data: dict[str, dict[int, list[dict]]],
) -> int:
    role_tiers = tier_data.get(role, {})
    for tier_num, entries in role_tiers.items():
        for e in entries:
            if e["player_id"] == player_id:
                return tier_num
    return 4
