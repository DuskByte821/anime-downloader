"""Parse a Lucifer series page (HTML) into structured metadata.

Pure function: takes HTML text, returns a dict. No HTTP, no cache,
no network. Testable in isolation.
"""

import re
from typing import Dict

from bs4 import BeautifulSoup


def parse_series_metadata(html: str) -> Dict:
    """
    Parse HTML from a Lucifer series page.

    Returns a dict with keys:
        title (str|None), alt_titles (list[str]), description (str),
        status, network, studio, released, duration, season,
        country, type, episodes, fansub, genres (list[str]).

    Missing fields are None or [].
    """
    result = {
        "title": None,
        "alt_titles": [],
        "description": "",
        "status": None,
        "network": None,
        "studio": None,
        "released": None,
        "duration": None,
        "season": None,
        "country": None,
        "type": None,
        "episodes": None,
        "fansub": None,
        "genres": [],
    }

    soup = BeautifulSoup(html, "html.parser")

    # ---- Title (h1.entry-title) -------------------------------------
    h1 = soup.select_one("h1.entry-title")
    if h1:
        result["title"] = h1.get_text(strip=True)

    # ---- Alt titles (span.alter) ------------------------------------
    alter = soup.select_one("span.alter")
    if alter:
        raw = alter.get_text(",", strip=True)
        result["alt_titles"] = [t.strip() for t in raw.split(",") if t.strip()]

    # ---- Short description (div.mindesc) ----------------------------
    mindesc = soup.select_one("div.mindesc")
    if mindesc:
        result["description"] = mindesc.get_text(" ", strip=True)

    # ---- Long synopsis (div.synp .entry-content) --------------------
    synp = soup.select_one("div.synp .entry-content")
    if synp:
        long_desc = synp.get_text(" ", strip=True)
        if len(long_desc) > len(result["description"]):
            result["description"] = long_desc

    # ---- The .spe info block ----------------------------------------
    spe = soup.select_one("div.spe")
    if spe:
        fields = {
            "status": "Status",
            "network": "Network",
            "studio": "Studio",
            "released": "Released",
            "duration": "Duration",
            "country": "Country",
            "type": "Type",
            "episodes": "Episodes",
            "fansub": "Fansub",
        }
        text = spe.get_text("|", strip=True)
        for key, label in fields.items():
            m = re.search(rf"{label}:\s*([^|]+)", text)
            if m:
                val = m.group(1).strip()
                if val:
                    result[key] = val

        # Season comes as a link: <span><b>Season:</b> <a>1</a></span>
        for span in spe.find_all("span"):
            b = span.find("b")
            if b and "Season" in b.get_text():
                a = span.find("a")
                if a:
                    try:
                        result["season"] = int(a.get_text(strip=True))
                    except ValueError:
                        pass

        # Episodes: <span><b>Episodes:</b> 24</span>
        for span in spe.find_all("span"):
            b = span.find("b")
            if b and "Episodes" in b.get_text():
                m = re.search(r"(\d+)", span.get_text())
                if m:
                    try:
                        result["episodes"] = int(m.group(1))
                    except ValueError:
                        pass

    # ---- Genres (div.genxed a) --------------------------------------
    genxed = soup.select_one("div.genxed")
    if genxed:
        result["genres"] = [a.get_text(strip=True) for a in genxed.find_all("a")]

    # ---- Fallback for description: meta name=description ------------
    if not result["description"]:
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            result["description"] = meta["content"]

    # ---- Fallback title: meta og:title ------------------------------
    if not result["title"]:
        meta = soup.find("meta", attrs={"property": "og:title"})
        if meta and meta.get("content"):
            result["title"] = meta["content"].split(" - ")[0].strip()

    return result