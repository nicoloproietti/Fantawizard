"""FantaWizard — API FastAPI + serve frontend statico."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.importers.quotazioni import parse_csv, parse_excel
from app.importers.sample_data import load_sample_data
from app.importers.stats import import_stats_csv, import_stats_excel
from app.models import (
    BONUS_DEFAULTS,
    MODIFIER_DEFAULTS,
    Auction,
    AuctionType,
    BonusRule,
    BudgetSplit,
    LeagueMode,
    Modifier,
    Player,
    PlayerSeason,
    Purchase,
    RosterSlot,
    Team,
    WatchlistEntry,
)
from app.schemas import (
    AuctionCreate,
    PurchaseCreate,
    PurchaseUndo,
    WatchlistAdd,
)
from app.services.pricing import (
    _bonus_map,
    _modifier_flags,
    _season_stats,
    base_price_from_fma,
    budget_status,
    compute_inflation,
    compute_scarcity,
    compute_recommended_price,
    convenience_index,
    max_bid,
    project_fma,
)
from app.services.tiers import build_tier_map, get_player_tier

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="FantaWizard", version="0.1.0")


@app.on_event("startup")
def on_startup():
    init_db()
    db = next(get_db())
    try:
        load_sample_data(db)
    finally:
        db.close()


# ── Auction CRUD ─────────────────────────────────────────────────────────────


@app.post("/api/auctions")
def create_auction(data: AuctionCreate, db: Session = Depends(get_db)):
    auction = Auction(
        name=data.name,
        mode=LeagueMode(data.mode),
        auction_type=AuctionType(data.auction_type),
        num_teams=data.num_teams,
        initial_credits=data.initial_credits,
        num_matchdays=data.num_matchdays,
    )
    db.add(auction)
    db.flush()

    if data.roster_slots:
        for rs in data.roster_slots:
            db.add(RosterSlot(auction_id=auction.id, role=rs.role, count=rs.count))
    else:
        for role, cnt in [("P", 3), ("D", 8), ("C", 8), ("A", 6)]:
            db.add(RosterSlot(auction_id=auction.id, role=role, count=cnt))

    if data.bonus_rules:
        for br in data.bonus_rules:
            defaults = next((d for d in BONUS_DEFAULTS if d["code"] == br.code), None)
            if defaults:
                db.add(BonusRule(
                    auction_id=auction.id,
                    code=br.code,
                    label=defaults["label"],
                    value=br.value,
                    enabled=br.enabled,
                    roles=defaults["roles"],
                    advanced=defaults["advanced"],
                ))
    else:
        for d in BONUS_DEFAULTS:
            db.add(BonusRule(
                auction_id=auction.id,
                code=d["code"],
                label=d["label"],
                value=d["default_value"],
                enabled=d["default_value"] != 0,
                roles=d["roles"],
                advanced=d["advanced"],
            ))

    if data.modifiers:
        for m in data.modifiers:
            defaults = next((d for d in MODIFIER_DEFAULTS if d["code"] == m.code), None)
            if defaults:
                db.add(Modifier(
                    auction_id=auction.id,
                    code=m.code,
                    label=defaults["label"],
                    enabled=m.enabled,
                ))
    else:
        for d in MODIFIER_DEFAULTS:
            db.add(Modifier(
                auction_id=auction.id,
                code=d["code"],
                label=d["label"],
                enabled=d["enabled"],
            ))

    if data.budget_splits:
        for bs in data.budget_splits:
            db.add(BudgetSplit(auction_id=auction.id, role=bs.role, percentage=bs.percentage))
    else:
        for role, pct in [("P", 8), ("D", 20), ("C", 27), ("A", 45)]:
            db.add(BudgetSplit(auction_id=auction.id, role=role, percentage=pct))

    if data.teams:
        for t in data.teams:
            db.add(Team(auction_id=auction.id, name=t.name, is_user=t.is_user))
    else:
        db.add(Team(auction_id=auction.id, name="La mia squadra", is_user=True))
        for i in range(1, data.num_teams):
            db.add(Team(auction_id=auction.id, name=f"Squadra {i + 1}"))

    db.commit()
    return {"id": auction.id, "name": auction.name}


@app.get("/api/auctions")
def list_auctions(db: Session = Depends(get_db)):
    auctions = db.query(Auction).order_by(Auction.created_at.desc()).all()
    return [
        {"id": a.id, "name": a.name, "mode": a.mode.value, "num_teams": a.num_teams,
         "initial_credits": a.initial_credits, "is_active": a.is_active}
        for a in auctions
    ]


@app.get("/api/auctions/{auction_id}")
def get_auction(auction_id: int, db: Session = Depends(get_db)):
    auction = db.query(Auction).get(auction_id)
    if not auction:
        raise HTTPException(404, "Asta non trovata")
    slots = db.query(RosterSlot).filter(RosterSlot.auction_id == auction_id).all()
    bonuses = db.query(BonusRule).filter(BonusRule.auction_id == auction_id).all()
    mods = db.query(Modifier).filter(Modifier.auction_id == auction_id).all()
    splits = db.query(BudgetSplit).filter(BudgetSplit.auction_id == auction_id).all()
    teams = db.query(Team).filter(Team.auction_id == auction_id).all()
    return {
        "id": auction.id,
        "name": auction.name,
        "mode": auction.mode.value,
        "auction_type": auction.auction_type.value,
        "num_teams": auction.num_teams,
        "initial_credits": auction.initial_credits,
        "num_matchdays": auction.num_matchdays,
        "roster_slots": [{"role": s.role, "count": s.count} for s in slots],
        "bonus_rules": [
            {"code": b.code, "label": b.label, "value": b.value,
             "enabled": b.enabled, "roles": b.roles, "advanced": b.advanced}
            for b in bonuses
        ],
        "modifiers": [{"code": m.code, "label": m.label, "enabled": m.enabled} for m in mods],
        "budget_splits": [{"role": s.role, "percentage": s.percentage} for s in splits],
        "teams": [{"id": t.id, "name": t.name, "is_user": t.is_user} for t in teams],
    }


@app.put("/api/auctions/{auction_id}/bonus")
def update_bonus(auction_id: int, rules: list[dict], db: Session = Depends(get_db)):
    for r in rules:
        existing = (
            db.query(BonusRule)
            .filter(BonusRule.auction_id == auction_id, BonusRule.code == r["code"])
            .first()
        )
        if existing:
            existing.value = r["value"]
            existing.enabled = r.get("enabled", True)
    db.commit()
    return {"ok": True}


@app.put("/api/auctions/{auction_id}/modifiers")
def update_modifiers(auction_id: int, mods: list[dict], db: Session = Depends(get_db)):
    for m in mods:
        existing = (
            db.query(Modifier)
            .filter(Modifier.auction_id == auction_id, Modifier.code == m["code"])
            .first()
        )
        if existing:
            existing.enabled = m["enabled"]
    db.commit()
    return {"ok": True}


# ── Players ──────────────────────────────────────────────────────────────────


@app.get("/api/players/search")
def search_players(
    q: str = Query(..., min_length=1),
    auction_id: int = Query(...),
    db: Session = Depends(get_db),
):
    sold_ids = {
        p.player_id
        for p in db.query(Purchase).filter(Purchase.auction_id == auction_id).all()
    }
    players = (
        db.query(Player)
        .filter(Player.name.ilike(f"%{q}%"), Player.active == True)  # noqa: E712
        .limit(15)
        .all()
    )

    bonus_map = _bonus_map(auction_id, db)
    modifiers = _modifier_flags(auction_id, db)
    auction = db.query(Auction).get(auction_id)
    slots = db.query(RosterSlot).filter(RosterSlot.auction_id == auction_id).all()
    total_slots = sum(s.count for s in slots)
    inflation = compute_inflation(auction_id, db)
    tier_data = build_tier_map(auction_id, db)

    results = []
    for pl in players:
        seasons = _season_stats(pl.id, db)
        fma = project_fma(pl, seasons, bonus_map, modifiers)
        bp = base_price_from_fma(
            fma, pl.role_classic, auction.initial_credits, auction.num_teams, total_slots,
        )
        tier = get_player_tier(pl.id, pl.role_classic, tier_data)
        role_tier_ids = tier_data.get(pl.role_classic, {})
        scarcity = compute_scarcity(auction_id, pl.role_classic, tier, role_tier_ids, db)
        user_team = db.query(Team).filter(
            Team.auction_id == auction_id, Team.is_user == True  # noqa: E712
        ).first()
        mb = max_bid(auction, user_team, db) if user_team else 0
        rec = compute_recommended_price(bp, pl.role_classic, tier, inflation, scarcity, mb)

        results.append({
            "id": pl.id,
            "name": pl.name,
            "team": pl.team,
            "role_classic": pl.role_classic,
            "role_mantra": pl.role_mantra,
            "initial_price": pl.initial_price,
            "fma": fma,
            "base_price": bp,
            "recommended_price": rec,
            "tier": tier,
            "max_bid": mb,
            "is_penalty_taker": pl.is_penalty_taker,
            "is_freekick_taker": pl.is_freekick_taker,
            "sold": pl.id in sold_ids,
            "seasons": [
                {
                    "season": s.season,
                    "appearances": s.appearances,
                    "avg_rating": s.avg_rating,
                    "fanta_avg": s.fanta_avg,
                    "goals": s.goals,
                    "assists": s.assists,
                    "minutes": s.minutes,
                    "yellow_cards": s.yellow_cards,
                    "red_cards": s.red_cards,
                    "clean_sheets": s.clean_sheets,
                }
                for s in seasons
            ],
        })

    results.sort(key=lambda x: x["fma"], reverse=True)
    return results


@app.get("/api/players/{player_id}")
def get_player(player_id: int, auction_id: int = Query(...), db: Session = Depends(get_db)):
    player = db.query(Player).get(player_id)
    if not player:
        raise HTTPException(404, "Giocatore non trovato")
    seasons = _season_stats(player.id, db)
    bonus_map = _bonus_map(auction_id, db)
    modifiers = _modifier_flags(auction_id, db)
    auction = db.query(Auction).get(auction_id)
    slots = db.query(RosterSlot).filter(RosterSlot.auction_id == auction_id).all()
    total_slots = sum(s.count for s in slots)
    fma = project_fma(player, seasons, bonus_map, modifiers)
    bp = base_price_from_fma(
        fma, player.role_classic, auction.initial_credits, auction.num_teams, total_slots,
    )
    inflation = compute_inflation(auction_id, db)
    tier_data = build_tier_map(auction_id, db)
    tier = get_player_tier(player.id, player.role_classic, tier_data)
    role_tier_ids = tier_data.get(player.role_classic, {})
    scarcity = compute_scarcity(auction_id, player.role_classic, tier, role_tier_ids, db)
    user_team = db.query(Team).filter(
        Team.auction_id == auction_id, Team.is_user == True  # noqa: E712
    ).first()
    mb = max_bid(auction, user_team, db) if user_team else 0
    rec = compute_recommended_price(bp, player.role_classic, tier, inflation, scarcity, mb)

    return {
        "id": player.id,
        "name": player.name,
        "team": player.team,
        "role_classic": player.role_classic,
        "role_mantra": player.role_mantra,
        "initial_price": player.initial_price,
        "fma": fma,
        "base_price": bp,
        "recommended_price": rec,
        "tier": tier,
        "max_bid": mb,
        "is_penalty_taker": player.is_penalty_taker,
        "is_freekick_taker": player.is_freekick_taker,
        "seasons": [
            {
                "season": s.season,
                "appearances": s.appearances,
                "avg_rating": s.avg_rating,
                "fanta_avg": s.fanta_avg,
                "goals": s.goals,
                "assists": s.assists,
                "minutes": s.minutes,
                "yellow_cards": s.yellow_cards,
                "red_cards": s.red_cards,
                "clean_sheets": s.clean_sheets,
                "goals_conceded": s.goals_conceded,
            }
            for s in seasons
        ],
    }


# ── Purchases (asta live) ───────────────────────────────────────────────────


@app.post("/api/auctions/{auction_id}/purchases")
def add_purchase(auction_id: int, data: PurchaseCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(Purchase)
        .filter(Purchase.auction_id == auction_id, Purchase.player_id == data.player_id)
        .first()
    )
    if existing:
        raise HTTPException(400, "Giocatore già acquistato")
    purchase = Purchase(
        auction_id=auction_id,
        player_id=data.player_id,
        team_id=data.team_id,
        price=data.price,
    )
    db.add(purchase)
    db.commit()
    return {"id": purchase.id}


@app.delete("/api/auctions/{auction_id}/purchases/{purchase_id}")
def undo_purchase(auction_id: int, purchase_id: int, db: Session = Depends(get_db)):
    purchase = db.query(Purchase).get(purchase_id)
    if not purchase or purchase.auction_id != auction_id:
        raise HTTPException(404, "Acquisto non trovato")
    db.delete(purchase)
    db.commit()
    return {"ok": True}


@app.get("/api/auctions/{auction_id}/purchases")
def list_purchases(auction_id: int, db: Session = Depends(get_db)):
    purchases = (
        db.query(Purchase)
        .filter(Purchase.auction_id == auction_id)
        .order_by(Purchase.created_at.desc())
        .all()
    )
    return [
        {
            "id": p.id,
            "player_id": p.player_id,
            "player_name": p.player.name if p.player else "?",
            "player_team": p.player.team if p.player else "",
            "player_role": p.player.role_classic if p.player else "",
            "team_id": p.team_id,
            "team_name": p.team.name if p.team else "?",
            "price": p.price,
        }
        for p in purchases
    ]


# ── Budget / Status ──────────────────────────────────────────────────────────


@app.get("/api/auctions/{auction_id}/budget")
def get_budget(auction_id: int, db: Session = Depends(get_db)):
    auction = db.query(Auction).get(auction_id)
    if not auction:
        raise HTTPException(404)
    user_team = db.query(Team).filter(
        Team.auction_id == auction_id, Team.is_user == True  # noqa: E712
    ).first()
    if not user_team:
        raise HTTPException(404, "Squadra utente non trovata")
    return budget_status(auction, user_team, db)


@app.get("/api/auctions/{auction_id}/teams/status")
def teams_status(auction_id: int, db: Session = Depends(get_db)):
    auction = db.query(Auction).get(auction_id)
    if not auction:
        raise HTTPException(404)
    teams = db.query(Team).filter(Team.auction_id == auction_id).all()
    slots = db.query(RosterSlot).filter(RosterSlot.auction_id == auction_id).all()
    total_slots = sum(s.count for s in slots)
    result = []
    for t in teams:
        purchases = db.query(Purchase).filter(
            Purchase.auction_id == auction_id, Purchase.team_id == t.id
        ).all()
        spent = sum(p.price for p in purchases)
        result.append({
            "id": t.id,
            "name": t.name,
            "is_user": t.is_user,
            "spent": spent,
            "remaining": auction.initial_credits - spent,
            "players_bought": len(purchases),
            "slots_remaining": total_slots - len(purchases),
        })
    return result


# ── Tier list ────────────────────────────────────────────────────────────────


@app.get("/api/auctions/{auction_id}/tiers")
def get_tiers(auction_id: int, db: Session = Depends(get_db)):
    return build_tier_map(auction_id, db)


# ── Watchlist ────────────────────────────────────────────────────────────────


@app.post("/api/auctions/{auction_id}/watchlist")
def add_to_watchlist(auction_id: int, data: WatchlistAdd, db: Session = Depends(get_db)):
    existing = (
        db.query(WatchlistEntry)
        .filter(WatchlistEntry.auction_id == auction_id, WatchlistEntry.player_id == data.player_id)
        .first()
    )
    if existing:
        existing.priority = data.priority
        existing.notes = data.notes
    else:
        db.add(WatchlistEntry(
            auction_id=auction_id,
            player_id=data.player_id,
            priority=data.priority,
            notes=data.notes,
        ))
    db.commit()
    return {"ok": True}


@app.get("/api/auctions/{auction_id}/watchlist")
def get_watchlist(auction_id: int, db: Session = Depends(get_db)):
    entries = (
        db.query(WatchlistEntry)
        .filter(WatchlistEntry.auction_id == auction_id)
        .order_by(WatchlistEntry.priority.desc())
        .all()
    )
    sold_ids = {
        p.player_id
        for p in db.query(Purchase).filter(Purchase.auction_id == auction_id).all()
    }
    return [
        {
            "id": e.id,
            "player_id": e.player_id,
            "player_name": e.player.name if e.player else "?",
            "player_role": e.player.role_classic if e.player else "",
            "player_team": e.player.team if e.player else "",
            "priority": e.priority,
            "notes": e.notes,
            "sold": e.player_id in sold_ids,
        }
        for e in entries
    ]


@app.delete("/api/auctions/{auction_id}/watchlist/{entry_id}")
def remove_from_watchlist(auction_id: int, entry_id: int, db: Session = Depends(get_db)):
    entry = db.query(WatchlistEntry).get(entry_id)
    if not entry or entry.auction_id != auction_id:
        raise HTTPException(404)
    db.delete(entry)
    db.commit()
    return {"ok": True}


# ── Import dati ──────────────────────────────────────────────────────────────


@app.post("/api/import/quotazioni")
async def import_quotazioni(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    if file.filename and file.filename.endswith((".xlsx", ".xls")):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(content)
            tmp.flush()
            count = parse_excel(tmp.name, db)
    else:
        count = parse_csv(content, db)
    return {"imported": count}


@app.post("/api/import/stats")
async def import_stats(
    file: UploadFile = File(...),
    season: str = Query(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    if file.filename and file.filename.endswith((".xlsx", ".xls")):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(content)
            tmp.flush()
            count = import_stats_excel(tmp.name, season, db)
    else:
        count = import_stats_csv(content, season, db)
    return {"imported": count}


# ── Serve frontend ───────────────────────────────────────────────────────────

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
