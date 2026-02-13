"""Game catalog: metadata for the 23 bundled legacy .siftapp games."""

from __future__ import annotations

from pathlib import Path

# Hand-curated metadata for each .siftapp bundle.
# Keys are the exact filename stems (without .siftapp).
GAMES: dict[str, dict] = {
    "3x3": {
        "display_name": "3x3",
        "category": "puzzle",
        "description": "Arrange cubes in a 3x3 grid to match patterns.",
    },
    "alphamatic": {
        "display_name": "Alphamatic",
        "category": "word",
        "description": "Spell words by linking letter cubes together.",
    },
    "bouncr": {
        "display_name": "Bouncr",
        "category": "action",
        "description": "Bounce and ricochet through colorful levels.",
    },
    "brainiac": {
        "display_name": "Brainiac",
        "category": "puzzle",
        "description": "Memory and logic challenges for your brain.",
    },
    "calculator": {
        "display_name": "Calculator",
        "category": "utility",
        "description": "Simple calculator using cube interactions.",
    },
    "chromalite_17": {
        "display_name": "Chromalite",
        "category": "puzzle",
        "description": "Match colors by tilting and neighboring cubes.",
    },
    "gems": {
        "display_name": "Gems",
        "category": "puzzle",
        "description": "Classic gem-matching puzzle game.",
    },
    "gestut": {
        "display_name": "Gestut",
        "category": "action",
        "description": "Gesture-based gameplay with tilt and shake.",
    },
    "gopherrun": {
        "display_name": "Gopher Run",
        "category": "action",
        "description": "Guide the gopher through obstacle courses.",
    },
    "LoopLoop": {
        "display_name": "Loop Loop",
        "category": "puzzle",
        "description": "Connect loops across cubes to complete circuits.",
    },
    "match": {
        "display_name": "Match",
        "category": "puzzle",
        "description": "Classic memory matching card game.",
    },
    "meatRummy": {
        "display_name": "Meat Rummy",
        "category": "card",
        "description": "A quirky rummy card game with a meaty twist.",
    },
    "MiamiHeist_20120305": {
        "display_name": "Miami Heist",
        "category": "action",
        "description": "Plan and execute heists in a Miami-themed adventure.",
    },
    "monsterbuds": {
        "display_name": "Monster Buds",
        "category": "action",
        "description": "Collect and battle adorable monster buddies.",
    },
    "oogors_story": {
        "display_name": "Oogor's Story",
        "category": "adventure",
        "description": "Guide Oogor through a storybook adventure.",
    },
    "Peano_2012_03_20": {
        "display_name": "Peano",
        "category": "puzzle",
        "description": "Mathematical puzzle inspired by Peano curves.",
    },
    "penguin": {
        "display_name": "Penguin",
        "category": "action",
        "description": "Help penguins slide across icy cube landscapes.",
    },
    "PlanetOfTunes": {
        "display_name": "Planet of Tunes",
        "category": "music",
        "description": "Create music by arranging cubes as instruments.",
    },
    "shaper": {
        "display_name": "Shaper",
        "category": "puzzle",
        "description": "Arrange cubes to form geometric shapes.",
    },
    "siftsays": {
        "display_name": "Sift Says",
        "category": "party",
        "description": "Simon Says-style party game for cubes.",
    },
    "tiles": {
        "display_name": "Tiles",
        "category": "puzzle",
        "description": "Slide tiles to solve classic sliding puzzles.",
    },
    "tiny": {
        "display_name": "Tiny",
        "category": "action",
        "description": "Tiny adventures on tiny cube screens.",
    },
    "wordplay": {
        "display_name": "Wordplay",
        "category": "word",
        "description": "Create words using letter cubes.",
    },
}


def _accent_color(name: str) -> str:
    """Generate a deterministic HSL accent color from a game name."""
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    hue = h % 360
    return f"hsl({hue}, 65%, 55%)"


def discover_games(siftapp_dir: Path) -> list[dict]:
    """Scan the Siftapps directory and return enriched game metadata.

    Returns a list of dicts sorted by display_name, each containing:
        name, display_name, category, description, color, path, size_kb
    """
    games = []
    for path in sorted(siftapp_dir.glob("*.siftapp"), key=lambda p: p.name.lower()):
        stem = path.stem
        meta = GAMES.get(stem, {})
        games.append({
            "name": stem,
            "display_name": meta.get("display_name", stem),
            "category": meta.get("category", "game"),
            "description": meta.get("description", ""),
            "color": _accent_color(stem),
            "path": str(path),
            "size_kb": path.stat().st_size // 1024,
        })
    games.sort(key=lambda g: g["display_name"].lower())
    return games
