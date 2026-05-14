"""
Stock image library — indexes DrawThings-generated PNGs by category.
Images live in  backend/stock_images/<category>/
Index lives in  backend/stock_images/index.json
"""
import base64
import json
import shutil
from pathlib import Path

STOCK_DIR = Path(__file__).parent.parent / "stock_images"
INDEX_FILE = STOCK_DIR / "index.json"

CATEGORIES = [
    "crypto", "finance", "technology", "politics",
    "war", "environment", "health", "general",
]

_CAT_KEYWORDS: dict[str, list[str]] = {
    "crypto": [
        "crypto", "bitcoin", "btc", "ethereum", "eth", "coin", "tiền số",
        "blockchain", "chứng khoán", "cổ phiếu", "token", "nft", "defi",
        "wallet", "altcoin", "market cap", "bull", "bear",
    ],
    "finance": [
        "tài chính", "kinh tế", "đầu tư", "lãi suất", "lạm phát", "ngân hàng",
        "gold", "vàng", "forex", "dollar", "usd", "gdp", "interest rate",
        "stock market", "bond", "hedge", "portfolio",
    ],
    "technology": [
        "công nghệ", "ai ", "artificial intelligence", "trí tuệ nhân tạo",
        "robot", "phần mềm", "chip", "bán dẫn", "tech", "software", "hardware",
        "digital", "cyber", "hack", "startup", "silicon", "data center",
        "server", "circuit", "fiber", "neural",
    ],
    "politics": [
        "chính trị", "chính phủ", "quốc hội", "bầu cử", "ngoại giao",
        "tổng thống", "thủ tướng", "law", "policy", "sanction", "treaty",
        "government", "election", "congress", "senate",
    ],
    "war": [
        "chiến tranh", "xung đột", "quân sự", "vũ khí", "tên lửa", "drone",
        "nato", "iran", "ukraine", "russia", "israel", "hamas", "military",
        "missile", "bomb", "tank", "troops", "battle",
    ],
    "environment": [
        "môi trường", "khí hậu", "biến đổi khí hậu", "thiên tai", "lũ lụt",
        "hạn hán", "năng lượng tái tạo", "solar", "wind", "carbon", "climate",
        "earthquake", "typhoon", "forest", "ocean",
    ],
    "health": [
        "sức khỏe", "y tế", "bệnh viện", "vaccine", "dịch bệnh", "thuốc",
        "ung thư", "covid", "virus", "bác sĩ", "health", "medicine",
        "disease", "hospital", "cancer", "drug", "pandemic",
    ],
}


def detect_category(text: str) -> str:
    t = text.lower()
    for cat, kws in _CAT_KEYWORDS.items():
        if any(kw in t for kw in kws):
            return cat
    return "general"


def _load_index() -> dict[str, list[str]]:
    if INDEX_FILE.exists():
        try:
            return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {cat: [] for cat in CATEGORIES}


def _save_index(index: dict[str, list[str]]) -> None:
    STOCK_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


def scan_and_index(projects_dir: Path) -> dict[str, int]:
    """
    Walk all project clips/ dirs, copy PNG files to stock_images/<category>/,
    and update index.json. Returns count of newly added images per category.
    """
    STOCK_DIR.mkdir(parents=True, exist_ok=True)
    for cat in CATEGORIES:
        (STOCK_DIR / cat).mkdir(exist_ok=True)

    index = _load_index()
    # Flatten existing relative paths for dedup
    existing: set[str] = set(p for paths in index.values() for p in paths)
    added: dict[str, int] = {cat: 0 for cat in CATEGORIES}

    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue

        # Read project topic from metadata
        topic = ""
        meta_path = project_dir / "metadata.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                topic = meta.get("topic", "")
            except Exception:
                pass

        # Read per-scene visual prompts from script for accurate category detection
        scene_cats: dict[int, str] = {}
        for sp in sorted(project_dir.glob("script_*.json")):
            try:
                script = json.loads(sp.read_text(encoding="utf-8"))
                for scene in script.get("scenes", []):
                    n = scene.get("scene_number", 0)
                    vp = scene.get("visual_prompt", "") or topic
                    scene_cats[n] = detect_category(vp)
            except Exception:
                pass

        clips_dir = project_dir / "clips"
        if not clips_dir.exists():
            continue

        for png in sorted(clips_dir.glob("scene_*.png")):
            # Skip generated overlay/subtitle/still variants
            if any(x in png.stem for x in ("_ovl", "_sub", "_still", "_subbed", "_raw")):
                continue
            if png.stat().st_size < 30_000:
                continue

            # Parse scene number from "scene_01.png" → 1
            try:
                n = int(png.stem.split("_")[1])
            except (IndexError, ValueError):
                n = 0

            cat = scene_cats.get(n) or detect_category(topic)
            dest_name = f"{project_dir.name}__{png.name}"
            dest_rel = f"{cat}/{dest_name}"

            if dest_rel in existing:
                continue

            dest = STOCK_DIR / cat / dest_name
            try:
                shutil.copy2(str(png), str(dest))
                index.setdefault(cat, []).append(dest_rel)
                existing.add(dest_rel)
                added[cat] += 1
            except Exception as e:
                print(f"[stock] copy failed {png}: {e}")

    _save_index(index)
    return added


def get_stock_image(category: str, photo_idx: int = 0) -> str | None:
    """
    Return a base64 data URI for a local stock image matching the category.
    Falls back to 'general' pool if category has no images.
    Returns None if library is empty.
    """
    index = _load_index()
    paths = index.get(category, [])
    if not paths:
        paths = index.get("general", [])
    if not paths:
        return None

    # Rotate through available images by photo_idx
    rel = paths[photo_idx % len(paths)]
    full = STOCK_DIR / rel
    if not full.exists():
        # Stale entry — remove and try next
        paths_clean = [p for p in paths if (STOCK_DIR / p).exists()]
        if not paths_clean:
            return None
        rel = paths_clean[photo_idx % len(paths_clean)]
        full = STOCK_DIR / rel

    img_bytes = full.read_bytes()
    b64 = base64.b64encode(img_bytes).decode()
    suffix = full.suffix.lower().lstrip(".")
    mime = "image/jpeg" if suffix in ("jpg", "jpeg") else "image/png"
    return f"data:{mime};base64,{b64}"


def library_stats() -> dict:
    """Return summary: total images, count per category."""
    index = _load_index()
    counts = {cat: len(paths) for cat, paths in index.items()}
    return {"total": sum(counts.values()), "by_category": counts}
