"""
The Daily Lemon — Scraper Module
Pulls AI data centre fitout jobs and tenders from Australian sources.
"""

import re
import time
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
}

# ── Keyword lists ─────────────────────────────────────────────────────────────

DC_KEYWORDS = [
    "data centre", "data center", "datacentre", "datacenter",
    "ai campus", "hyperscale", "colocation", "colo facility",
    "server room", "server hall", "data hall", "ai factory",
    "hpc facility", "gpu cluster", "ai infrastructure", "supernode",
    "nextdc", "airtrunk", "equinix", "goodman digital", "quinbrook",
    "digico", "firmus", "macquarie data", "vocus", "dc fitout",
    "data centre fitout", "data center fitout"
]

TRADE_KEYWORDS = [
    "cnc", "joinery", "bulkhead", "access floor", "raised floor",
    "partition", "ceiling", "fitout", "fit-out", "fit out",
    "carpentry", "cabinetry", "kitchen", "noc room", "interior fitout",
    "doors and frames", "epoxy floor", "flooring", "linings",
    "shopfitting", "millwork", "timber machining", "cabinet making"
]

PRIORITY_AREAS = {
    "CQ": [
        "rockhampton", "gladstone", "mackay", "yeppoon", "biloela",
        "emerald", "central queensland", "central qld", "capricornia",
        "fitzroy", "blackwater", "moura", "clermont", "alpha", "barcaldine",
        "longreach", "bundaberg", "maryborough", "hervey bay"
    ],
    "CASINO NSW": [
        "casino nsw", "casino, nsw", "richmond valley",
        "lismore", "northern rivers", "ballina", "kyogle", "evans head"
    ]
}

STATE_MAP = {
    "QLD": [
        "queensland", " qld", "(qld)", ", qld", "brisbane", "gold coast",
        "sunshine coast", "cairns", "townsville", "toowoomba", "rockhampton",
        "mackay", "gladstone", "ipswich", "logan", "brendale", "geebung",
        "acacia ridge", "yatala", "coomera", "paget"
    ],
    "NSW": [
        "new south wales", " nsw", "(nsw)", ", nsw", "sydney", "newcastle",
        "wollongong", "casino", "kemps creek", "ultimo", "western sydney",
        "penrith", "blacktown", "marsden park", "rouse hill", "hornsby",
        "wetherill park", "eastern creek", "prospect"
    ],
    "VIC": [
        "victoria", " vic", "(vic)", ", vic", "melbourne", "geelong",
        "ballarat", "bendigo", "dandenong", "clayton", "tullamarine",
        "port melbourne", "laverton"
    ],
    "SA": ["south australia", " sa ", "(sa)", ", sa", "adelaide", "port augusta"],
    "WA": ["western australia", " wa ", "(wa)", ", wa", "perth", "fremantle", "jandakot"],
    "TAS": ["tasmania", " tas", "(tas)", ", tas", "hobart", "launceston", "devonport"],
    "NT": ["northern territory", " nt ", "(nt)", ", nt", "darwin", "alice springs"],
    "ACT": ["australian capital territory", " act", "(act)", ", act", "canberra"],
}


# ── Helper functions ──────────────────────────────────────────────────────────

def clean_html(raw: str) -> str:
    """Strip HTML tags from a string."""
    return re.sub(r"<[^>]+>", " ", raw).strip()


def is_dc_relevant(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in DC_KEYWORDS)


def has_trade_match(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in TRADE_KEYWORDS)


def detect_state(text: str) -> str:
    text_lower = text.lower()
    for state, patterns in STATE_MAP.items():
        if any(p.lower() in text_lower for p in patterns):
            return state
    return "AU"


def detect_region(text: str) -> str:
    """Return locality name for grouping within a state."""
    text_lower = text.lower()

    # Check priority areas first
    for label, terms in PRIORITY_AREAS.items():
        if any(t in text_lower for t in terms):
            return label

    # Generic city extraction — crude but effective
    cities = [
        "Brisbane", "Gold Coast", "Sunshine Coast", "Cairns", "Townsville",
        "Toowoomba", "Rockhampton", "Mackay", "Gladstone", "Ipswich",
        "Brendale", "Geebung",
        "Sydney", "Newcastle", "Wollongong", "Western Sydney", "Kemps Creek",
        "Ultimo", "Penrith",
        "Melbourne", "Geelong", "Ballarat",
        "Adelaide", "Perth", "Darwin", "Hobart", "Launceston", "Canberra",
    ]
    for city in cities:
        if city.lower() in text_lower:
            return city
    return "General"


def is_priority(text: str) -> str | None:
    """Returns priority label or None."""
    text_lower = text.lower()
    for label, terms in PRIORITY_AREAS.items():
        if any(t in text_lower for t in terms):
            return label
    return None


def days_until(date_str: str) -> int | None:
    """Parse various date formats and return days until closing."""
    formats = ["%d/%m/%Y", "%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y"]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return (dt.date() - datetime.today().date()).days
        except ValueError:
            continue
    return None


def urgency_tag(close_date: str) -> str:
    days = days_until(close_date)
    if days is None:
        return ""
    if days <= 0:
        return "CLOSED"
    if days <= 3:
        return f"URGENT — {days}D"
    if days <= 7:
        return f"CLOSING — {days}D"
    return f"{days} days"


# ── Source scrapers ───────────────────────────────────────────────────────────

def scrape_austender() -> list[dict]:
    """Scrape AusTender open ATMs containing data centre keywords."""
    results = []
    search_terms = ["data centre fitout", "data center", "hyperscale", "colocation fitout"]

    for term in search_terms:
        try:
            url = (
                "https://www.tenders.gov.au/Search/ATMSearch"
                f"?StatusId=Active&Keywords={requests.utils.quote(term)}"
            )
            resp = requests.get(url, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(resp.text, "html.parser")

            for row in soup.select("table.search-results tbody tr"):
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue
                title = cells[1].get_text(strip=True)
                agency = cells[2].get_text(strip=True)
                close = cells[4].get_text(strip=True)
                link_tag = cells[1].find("a")
                href = ("https://www.tenders.gov.au" + link_tag["href"]) if link_tag else url

                combined = f"{title} {agency}"
                if not is_dc_relevant(combined):
                    continue

                results.append({
                    "source": "AusTender",
                    "title": title,
                    "agency": agency,
                    "close_date": close,
                    "urgency": urgency_tag(close),
                    "url": href,
                    "state": detect_state(combined),
                    "region": detect_region(combined),
                    "trade_match": has_trade_match(combined),
                    "priority": is_priority(combined),
                    "summary": f"{agency} | Close: {close}",
                    "value": "",
                    "status": "TENDER OPEN",
                })
            time.sleep(1.5)
        except Exception as e:
            print(f"[AusTender] Error: {e}")

    return results


def scrape_qtenders() -> list[dict]:
    """Scrape QTenders (Queensland) for data centre tenders."""
    results = []
    try:
        url = "https://qtenders.epw.qld.gov.au/qtenders/tender/list.action"
        params = {"keyword": "data centre", "tenderStatus": "OPEN"}
        resp = requests.get(url, params=params, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")

        for item in soup.select(".tender-item, .result-item, tr.tender-row"):
            title = item.get_text(strip=True)
            if is_dc_relevant(title):
                link = item.find("a")
                results.append({
                    "source": "QTenders",
                    "title": title[:120],
                    "agency": "",
                    "close_date": "",
                    "urgency": "",
                    "url": ("https://qtenders.epw.qld.gov.au" + link["href"]) if link else url,
                    "state": "QLD",
                    "region": detect_region(title),
                    "trade_match": has_trade_match(title),
                    "priority": is_priority(title),
                    "summary": title[:200],
                    "value": "",
                    "status": "TENDER OPEN",
                })
    except Exception as e:
        print(f"[QTenders] Error: {e}")
    return results


def scrape_nsw_etender() -> list[dict]:
    """Scrape NSW eTendering for data centre tenders."""
    results = []
    try:
        url = "https://tenders.nsw.gov.au/tenders/tender/search.do"
        params = {"action": "search", "keyword": "data centre", "status": "open"}
        resp = requests.get(url, params=params, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")

        for row in soup.select("table.tenderResultTable tr, .tender-result"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            title = cells[0].get_text(strip=True)
            if not is_dc_relevant(title):
                continue
            agency = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            close = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            link = cells[0].find("a")
            href = ("https://tenders.nsw.gov.au" + link["href"]) if link else url

            results.append({
                "source": "NSW eTendering",
                "title": title,
                "agency": agency,
                "close_date": close,
                "urgency": urgency_tag(close),
                "url": href,
                "state": "NSW",
                "region": detect_region(title + " " + agency),
                "trade_match": has_trade_match(title),
                "priority": is_priority(title + " " + agency),
                "summary": f"{agency} | Close: {close}",
                "value": "",
                "status": "TENDER OPEN",
            })
    except Exception as e:
        print(f"[NSW eTendering] Error: {e}")
    return results


def scrape_news_rss() -> list[dict]:
    """
    Scrape Google News RSS and industry feeds for AI data centre
    announcements, project updates, and subcontractor calls.
    """
    results = []

    feeds = [
        # Google News – specific queries (AU locale)
        (
            "https://news.google.com/rss/search"
            "?q=AI+data+centre+Australia+fitout+tender&hl=en-AU&gl=AU&ceid=AU:en",
            "Google News"
        ),
        (
            "https://news.google.com/rss/search"
            "?q=hyperscale+data+centre+construction+Australia&hl=en-AU&gl=AU&ceid=AU:en",
            "Google News"
        ),
        (
            "https://news.google.com/rss/search"
            "?q=%22data+centre%22+fitout+Queensland+OR+NSW+OR+Victoria&hl=en-AU&gl=AU&ceid=AU:en",
            "Google News"
        ),
        (
            "https://news.google.com/rss/search"
            "?q=NEXTDC+OR+AirTrunk+OR+Equinix+OR+Goodman+Digital+construction+Australia&hl=en-AU&gl=AU&ceid=AU:en",
            "Google News"
        ),
        (
            "https://news.google.com/rss/search"
            "?q=%22Central+Queensland%22+OR+%22Casino+NSW%22+data+centre&hl=en-AU&gl=AU&ceid=AU:en",
            "Google News"
        ),
        # Industry RSS
        ("https://www.datacenterdynamics.com/en/rss/", "Data Centre Dynamics"),
        ("https://www.itnews.com.au/rss/latest", "iTnews"),
        ("https://www.zdnet.com/topic/data-centers/rss.xml", "ZDNet AU"),
    ]

    cutoff = datetime.now() - timedelta(days=3)  # Only last 3 days

    for feed_url, source_label in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:
                title = entry.get("title", "")
                summary = clean_html(entry.get("summary", ""))
                combined = f"{title} {summary}"

                if not is_dc_relevant(combined):
                    continue

                # Date filter
                pub = entry.get("published_parsed")
                if pub:
                    pub_dt = datetime(*pub[:6])
                    if pub_dt < cutoff:
                        continue

                results.append({
                    "source": source_label,
                    "title": title,
                    "agency": source_label,
                    "close_date": "",
                    "urgency": "",
                    "url": entry.get("link", ""),
                    "state": detect_state(combined),
                    "region": detect_region(combined),
                    "trade_match": has_trade_match(combined),
                    "priority": is_priority(combined),
                    "summary": summary[:280],
                    "value": extract_value(combined),
                    "status": classify_status(combined),
                })
        except Exception as e:
            print(f"[RSS:{source_label}] Error: {e}")

    return results


def scrape_estimateone_public() -> list[dict]:
    """
    EstimateOne public search — no login required for browsing.
    Searches for data centre fitout projects.
    """
    results = []
    try:
        url = "https://www.estimateone.com/app/tenders"
        params = {"q": "data centre", "status": "open", "country": "au"}
        resp = requests.get(url, params=params, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")

        for card in soup.select(".project-card, .tender-card, article.tender"):
            title = card.get_text(separator=" ", strip=True)[:150]
            link = card.find("a")
            href = link["href"] if link else url
            if not href.startswith("http"):
                href = "https://www.estimateone.com" + href

            if not is_dc_relevant(title):
                continue

            results.append({
                "source": "EstimateOne",
                "title": title,
                "agency": "",
                "close_date": "",
                "urgency": "",
                "url": href,
                "state": detect_state(title),
                "region": detect_region(title),
                "trade_match": has_trade_match(title),
                "priority": is_priority(title),
                "summary": title[:280],
                "value": "",
                "status": "TENDER OPEN",
            })
    except Exception as e:
        print(f"[EstimateOne] Error: {e}")
    return results


# ── Value and status extraction ───────────────────────────────────────────────

VALUE_RE = re.compile(
    r"\$\s*([\d,]+(?:\.\d+)?)\s*(million|billion|m|b|k)\b",
    re.IGNORECASE
)

def extract_value(text: str) -> str:
    m = VALUE_RE.search(text)
    if not m:
        return ""
    num, unit = m.group(1).replace(",", ""), m.group(2).lower()
    if unit in ("billion", "b"):
        return f"A${float(num):.1f}B"
    if unit in ("million", "m"):
        return f"A${float(num):.0f}M"
    return f"A${num}K"


def classify_status(text: str) -> str:
    text_lower = text.lower()
    if any(w in text_lower for w in ["under construction", "construction underway", "commenced", "breaking ground"]):
        return "UNDER CONSTRUCTION"
    if any(w in text_lower for w in ["fitout", "packages", "procurement", "subcontractor"]):
        return "FITOUT PACKAGES ACTIVE"
    if any(w in text_lower for w in ["planning", "approved", "da approved", "development approval"]):
        return "APPROVED"
    if any(w in text_lower for w in ["proposed", "planned", "announced"]):
        return "ANNOUNCED"
    return "ACTIVE"


# ── Deduplication ─────────────────────────────────────────────────────────────

def deduplicate(leads: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for lead in leads:
        key = re.sub(r"\s+", " ", lead["title"].lower().strip())[:80]
        if key not in seen:
            seen.add(key)
            unique.append(lead)
    return unique


# ── Master runner ─────────────────────────────────────────────────────────────

def run_all_scrapers() -> list[dict]:
    print("  → AusTender...")
    a = scrape_austender()
    print(f"     {len(a)} results")

    print("  → QTenders...")
    b = scrape_qtenders()
    print(f"     {len(b)} results")

    print("  → NSW eTendering...")
    c = scrape_nsw_etender()
    print(f"     {len(c)} results")

    print("  → News RSS feeds...")
    d = scrape_news_rss()
    print(f"     {len(d)} results")

    print("  → EstimateOne...")
    e = scrape_estimateone_public()
    print(f"     {len(e)} results")

    combined = a + b + c + d + e
    combined = deduplicate(combined)

    # Sort: priority first, then trade matches, then by state
    combined.sort(key=lambda x: (
        0 if x.get("priority") else 1,
        0 if x.get("trade_match") else 1,
        x.get("state", "ZZ"),
    ))

    print(f"  ✓ {len(combined)} unique leads after dedup")
    return combined
