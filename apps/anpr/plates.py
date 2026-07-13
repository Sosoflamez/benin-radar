"""Normalisation des plaques d'immatriculation béninoises.

Format cible : deux lettres, quatre chiffres, deux lettres — ex. "AB 1234 RB".
Toute lecture OCR qui ne matche pas ce format est considérée illisible :
on ne corrige/devine jamais une plaque (voir CLAUDE.md).
"""

from __future__ import annotations

import re

PLATE_PATTERN = re.compile(r"^([A-Z]{2})\s*(\d{4})\s*([A-Z]{2})$")

# Caractères fréquemment confondus par l'OCR, corrigés uniquement dans les
# positions attendues (lettre <-> lettre, chiffre <-> chiffre), jamais entre les deux.
_LETTER_CONFUSIONS = {"0": "O", "1": "I", "5": "S", "8": "B"}
_DIGIT_CONFUSIONS = {"O": "0", "I": "1", "S": "5", "B": "8", "Z": "2"}


def _clean(raw: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", raw.upper())


def normalize_plate(raw: str) -> str | None:
    """Retourne la plaque normalisée "AB 1234 RB", ou None si illisible.

    Ne tente jamais de deviner un caractère hors des substitutions OCR
    classiques appliquées à une position typée (lettre ou chiffre).
    """
    cleaned = _clean(raw)
    if len(cleaned) != 8:
        return None

    chars = list(cleaned)
    for i in (0, 1, 6, 7):
        chars[i] = _DIGIT_CONFUSIONS.get(chars[i], chars[i])
    for i in (2, 3, 4, 5):
        chars[i] = _LETTER_CONFUSIONS.get(chars[i], chars[i])
    candidate = "".join(chars)

    match = PLATE_PATTERN.match(f"{candidate[:2]}{candidate[2:6]}{candidate[6:]}")
    if not match:
        return None

    letters_1, digits, letters_2 = match.groups()
    return f"{letters_1} {digits} {letters_2}"
