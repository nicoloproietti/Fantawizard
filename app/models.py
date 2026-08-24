"""SQLAlchemy models — tutto il dominio FantaWizard."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ────────────────────────────────────────────────────────────────────


class LeagueMode(str, enum.Enum):
    CLASSIC = "classic"
    MANTRA = "mantra"


class AuctionType(str, enum.Enum):
    CHIAMATA = "chiamata"
    BUSTA = "busta"


class ClassicRole(str, enum.Enum):
    P = "P"
    D = "D"
    C = "C"
    A = "A"


MANTRA_ROLES = [
    "Por", "Dc", "Dd", "Ds", "E", "M", "C", "T", "W", "A", "Pc",
]


# ── Asta (lega) ─────────────────────────────────────────────────────────────


class Auction(Base):
    __tablename__ = "auctions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    mode: Mapped[LeagueMode] = mapped_column(Enum(LeagueMode), default=LeagueMode.CLASSIC)
    auction_type: Mapped[AuctionType] = mapped_column(Enum(AuctionType), default=AuctionType.CHIAMATA)
    num_teams: Mapped[int] = mapped_column(Integer, default=8)
    initial_credits: Mapped[int] = mapped_column(Integer, default=500)
    num_matchdays: Mapped[int] = mapped_column(Integer, default=38)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    roster_slots: Mapped[list[RosterSlot]] = relationship(back_populates="auction", cascade="all, delete-orphan")
    bonus_rules: Mapped[list[BonusRule]] = relationship(back_populates="auction", cascade="all, delete-orphan")
    modifiers: Mapped[list[Modifier]] = relationship(back_populates="auction", cascade="all, delete-orphan")
    budget_splits: Mapped[list[BudgetSplit]] = relationship(back_populates="auction", cascade="all, delete-orphan")
    teams: Mapped[list[Team]] = relationship(back_populates="auction", cascade="all, delete-orphan")
    purchases: Mapped[list[Purchase]] = relationship(back_populates="auction", cascade="all, delete-orphan")


# ── Composizione rosa ───────────────────────────────────────────────────────


class RosterSlot(Base):
    __tablename__ = "roster_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id"))
    role: Mapped[str] = mapped_column(String(10))
    count: Mapped[int] = mapped_column(Integer)

    auction: Mapped[Auction] = relationship(back_populates="roster_slots")

    __table_args__ = (UniqueConstraint("auction_id", "role"),)


# ── Bonus / Malus ───────────────────────────────────────────────────────────

BONUS_DEFAULTS: list[dict] = [
    {"code": "GOL",              "label": "Gol segnato",            "default_value":  3.0, "roles": "P,D,C,A", "advanced": False},
    {"code": "GOL_SUBITO",       "label": "Gol subito",             "default_value": -1.0, "roles": "P",       "advanced": False},
    {"code": "ASSIST",           "label": "Assist",                 "default_value":  1.0, "roles": "P,D,C,A", "advanced": False},
    {"code": "ASSIST_FERMO",     "label": "Assist da fermo",        "default_value":  1.0, "roles": "P,D,C,A", "advanced": False},
    {"code": "RIGORE_SEGNATO",   "label": "Rigore segnato",         "default_value":  3.0, "roles": "P,D,C,A", "advanced": False},
    {"code": "RIGORE_SBAGLIATO", "label": "Rigore sbagliato",       "default_value": -3.0, "roles": "P,D,C,A", "advanced": False},
    {"code": "RIGORE_PARATO",    "label": "Rigore parato",          "default_value":  3.0, "roles": "P",       "advanced": False},
    {"code": "AMMONIZIONE",      "label": "Ammonizione",            "default_value": -0.5, "roles": "P,D,C,A", "advanced": False},
    {"code": "ESPULSIONE",       "label": "Espulsione",             "default_value": -1.0, "roles": "P,D,C,A", "advanced": False},
    {"code": "AUTOGOL",          "label": "Autogol",                "default_value": -2.0, "roles": "P,D,C,A", "advanced": False},
    {"code": "PORTA_INVIOLATA",  "label": "Clean sheet 90 min",     "default_value":  0.0, "roles": "P",       "advanced": True},
    {"code": "GOL_VITTORIA",     "label": "Gol vittoria",           "default_value":  0.0, "roles": "P,D,C,A", "advanced": True},
    {"code": "GOL_PAREGGIO",     "label": "Gol pareggio",           "default_value":  0.0, "roles": "P,D,C,A", "advanced": True},
    {"code": "PALO_TRAVERSA",    "label": "Palo / traversa",        "default_value":  0.0, "roles": "P,D,C,A", "advanced": True},
    {"code": "RIGORE_CONQUISTATO", "label": "Rigore conquistato",   "default_value":  0.0, "roles": "P,D,C,A", "advanced": True},
    {"code": "RIGORE_CAUSATO",   "label": "Rigore causato",         "default_value":  0.0, "roles": "P,D,C,A", "advanced": True},
    {"code": "SALVATAGGIO",      "label": "Salvataggio decisivo",   "default_value":  0.0, "roles": "D,C",     "advanced": True},
    {"code": "ERRORE_DECISIVO",  "label": "Errore decisivo",        "default_value":  0.0, "roles": "P,D,C,A", "advanced": True},
    {"code": "GOL_FUORI_AREA",   "label": "Gol da fuori area",      "default_value":  0.0, "roles": "P,D,C,A", "advanced": True},
]


class BonusRule(Base):
    __tablename__ = "bonus_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id"))
    code: Mapped[str] = mapped_column(String(30))
    label: Mapped[str] = mapped_column(String(60))
    value: Mapped[float] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    roles: Mapped[str] = mapped_column(String(30))
    advanced: Mapped[bool] = mapped_column(Boolean, default=False)

    auction: Mapped[Auction] = relationship(back_populates="bonus_rules")

    __table_args__ = (UniqueConstraint("auction_id", "code"),)


# ── Modificatori ─────────────────────────────────────────────────────────────

MODIFIER_DEFAULTS: list[dict] = [
    {"code": "MOD_DIFESA",   "label": "Modificatore difesa",   "enabled": False},
    {"code": "MOD_PORTIERE", "label": "Modificatore portiere", "enabled": False},
    {"code": "MOD_CC",       "label": "Modificatore C.campo",  "enabled": False},
    {"code": "MOD_FAIRPLAY", "label": "Modificatore fairplay", "enabled": False},
    {"code": "MOD_CAPITANO", "label": "Capitano",              "enabled": False},
]


class Modifier(Base):
    __tablename__ = "modifiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id"))
    code: Mapped[str] = mapped_column(String(30))
    label: Mapped[str] = mapped_column(String(60))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    auction: Mapped[Auction] = relationship(back_populates="modifiers")

    __table_args__ = (UniqueConstraint("auction_id", "code"),)


# ── Budget split per reparto ────────────────────────────────────────────────


class BudgetSplit(Base):
    __tablename__ = "budget_splits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id"))
    role: Mapped[str] = mapped_column(String(10))
    percentage: Mapped[float] = mapped_column(Float)

    auction: Mapped[Auction] = relationship(back_populates="budget_splits")

    __table_args__ = (UniqueConstraint("auction_id", "role"),)


# ── Squadre partecipanti ────────────────────────────────────────────────────


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id"))
    name: Mapped[str] = mapped_column(String(80))
    is_user: Mapped[bool] = mapped_column(Boolean, default=False)

    auction: Mapped[Auction] = relationship(back_populates="teams")
    purchases: Mapped[list[Purchase]] = relationship(back_populates="team")


# ── Giocatori ────────────────────────────────────────────────────────────────


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    team: Mapped[str] = mapped_column(String(40))
    role_classic: Mapped[str] = mapped_column(String(4))
    role_mantra: Mapped[str | None] = mapped_column(String(20), nullable=True)
    initial_price: Mapped[int] = mapped_column(Integer, default=1)
    current_price: Mapped[int] = mapped_column(Integer, default=1)
    is_penalty_taker: Mapped[bool] = mapped_column(Boolean, default=False)
    is_freekick_taker: Mapped[bool] = mapped_column(Boolean, default=False)
    is_captain: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── Statistiche per stagione ─────────────────────────────────────────────────


class PlayerSeason(Base):
    __tablename__ = "player_seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    season: Mapped[str] = mapped_column(String(10))
    appearances: Mapped[int] = mapped_column(Integer, default=0)
    minutes: Mapped[int] = mapped_column(Integer, default=0)
    avg_rating: Mapped[float] = mapped_column(Float, default=0.0)
    fanta_avg: Mapped[float] = mapped_column(Float, default=0.0)
    goals: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    penalties_taken: Mapped[int] = mapped_column(Integer, default=0)
    penalties_scored: Mapped[int] = mapped_column(Integer, default=0)
    penalties_saved: Mapped[int] = mapped_column(Integer, default=0)
    yellow_cards: Mapped[int] = mapped_column(Integer, default=0)
    red_cards: Mapped[int] = mapped_column(Integer, default=0)
    own_goals: Mapped[int] = mapped_column(Integer, default=0)
    clean_sheets: Mapped[int] = mapped_column(Integer, default=0)
    goals_conceded: Mapped[int] = mapped_column(Integer, default=0)
    saves_decisive: Mapped[int] = mapped_column(Integer, default=0)
    errors_decisive: Mapped[int] = mapped_column(Integer, default=0)
    shots_on_post: Mapped[int] = mapped_column(Integer, default=0)
    penalties_won: Mapped[int] = mapped_column(Integer, default=0)
    penalties_caused: Mapped[int] = mapped_column(Integer, default=0)
    goals_outside_box: Mapped[int] = mapped_column(Integer, default=0)
    winning_goals: Mapped[int] = mapped_column(Integer, default=0)
    equalizing_goals: Mapped[int] = mapped_column(Integer, default=0)
    assists_set_piece: Mapped[int] = mapped_column(Integer, default=0)
    starter_pct: Mapped[float] = mapped_column(Float, default=0.0)

    player: Mapped[Player] = relationship()

    __table_args__ = (UniqueConstraint("player_id", "season"),)


# ── Acquisti asta ────────────────────────────────────────────────────────────


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    price: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    auction: Mapped[Auction] = relationship(back_populates="purchases")
    team: Mapped[Team] = relationship(back_populates="purchases")
    player: Mapped[Player] = relationship()

    __table_args__ = (UniqueConstraint("auction_id", "player_id"),)


# ── Watchlist ────────────────────────────────────────────────────────────────


class WatchlistEntry(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    player: Mapped[Player] = relationship()

    __table_args__ = (UniqueConstraint("auction_id", "player_id"),)
