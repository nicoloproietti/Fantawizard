"""Fuzzy matching nomi giocatori tra fonti diverse."""
from __future__ import annotations

import re
import unicodedata


def normalize(name: str) -> str:
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9 ]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name


def similarity(a: str, b: str) -> float:
    a_n, b_n = normalize(a), normalize(b)
    if a_n == b_n:
        return 1.0
    if a_n in b_n or b_n in a_n:
        return 0.9

    tokens_a = set(a_n.split())
    tokens_b = set(b_n.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def best_match(
    name: str,
    candidates: list[tuple[int, str]],
    threshold: float = 0.6,
) -> int | None:
    best_id = None
    best_score = 0.0
    for cid, cname in candidates:
        score = similarity(name, cname)
        if score > best_score:
            best_score = score
            best_id = cid
    if best_score >= threshold:
        return best_id
    return None
