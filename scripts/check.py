"""
Wekelijkse check op nieuwe speeldata.
Leest de agenda's van de gezelschappen, vergelijkt met de speellijst
(Google Sheet CSV via SHEET_CSV_URL, anders speellijst.csv in de repo)
en schrijft nieuwe speelmomenten naar nieuw.csv.
"""
import csv, html, io, os, re, sys, urllib.request
from collections import OrderedDict
from datetime import date

UA = {"User-Agent": "Mozilla/5.0 (speellijst-check voor sofiejoanwouters.com)"}
MAAND = {m: i + 1 for i, m in enumerate(
    ["januari","februari","maart","april","mei","juni","juli","augustus","september","oktober","november","december"])}
MAAND.update({"jan":1,"feb":2,"mrt":3,"maa":3,"apr":4,"jun":6,"jul":7,"aug":8,"sep":9,"sept":9,"okt":10,"nov":11,"dec":12})
DAGEN = {"ma","di","wo","do","vr","vrij","za","zo"}

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8", "ignore")

def text_lines(raw, keep_links=False, inline=False):
    raw = re.sub(r"<script.*?</script>|<style.*?</style>", "", raw, flags=re.S)
    if keep_links:
        raw = re.sub(r'<a[^>]+href="([^"]+)"[^>]*>\s*(tickets?[^<]*)</a>', r"tickets{{\1}}", raw, flags=re.I)
    if inline:  # alleen <br>, </p> en </div> breken een regel; opmaaktags (<em>, <strong>) niet
        raw = re.sub(r"<br\s*/?>|</p>|</div>|</h\d>|</li>", "\n", raw, flags=re.I)
        raw = re.sub(r"<[^>]+>", "", raw)
    raw = re.sub(r"<[^>]+>", "\n", raw)
    return [l.strip() for l in html.unescape(raw).split("\n") if l.strip()]

def row(datum, voorstelling, gezelschap, link, zaal, stad, typ, tickets="", uur=""):
    return OrderedDict(datum=datum.isoformat(), uur=uur, voorstelling=voorstelling, gezelschap=gezelschap,
                       link=link, zaal=zaal, stad=stad, type=typ, tickets=tickets, status="check")

def is_school(times, d):
    """Dagvoorstelling op een weekdag = schoolvoorstelling."""
    if d.weekday() >= 5: return False
    if not times: return False
    return all(int(t.split(":")[0]) < 17 for t in times)

# ---------- 1. Hirngespinst (DEBUREN) ----------
def hirngespinst():
    lines = text_lines(get("https://hirngespinst.be/wanneer-herstel/"), keep_links=True, inline=True)
    out, jaar, maand = [], None, None
    for l in lines:
        m = re.match(r"^([A-Z]+) (20\d\d)$", l)
        if m and m.group(1).lower() in MAAND:
            maand, jaar = MAAND[m.group(1).lower()], int(m.group(2)); continue
        m = re.match(r"^(\d{1,2})\s*\|\|\s*(.+)$", l)
        if not (m and jaar): continue
        dag, rest = int(m.group(1)), m.group(2)
        if "DEBUREN" not in rest.upper().replace(" ", ""): continue
        parts = [p.strip(" ,*") for p in re.split(r",|–", rest)]
        parts = [p for p in parts if p and p.upper() != "DEBUREN"]
        premiere = any("première" in p for p in parts)
        parts = [p for p in parts if "première" not in p]
        tk = next((p for p in parts if p.startswith("tickets{{")), "")
        parts = [p for p in parts if not p.startswith("tickets{{") and "schoolvoorstelling" not in p]
        zaal = parts[0] if parts else ""; stad = parts[1] if len(parts) > 1 else ""
        if len(parts) > 2 and "nederland" in parts[2].lower(): stad += " (NL)"
        typ = "premiere" if premiere else ("tickets" if tk else "school")
        uur = "2x" if re.search(r"2\s*x", rest) else ""
        out.append(row(date(jaar, maand, dag), "DEBUREN", "Hirngespinst", "https://hirngespinst.be/wanneer-herstel/",
                       zaal, stad, typ, tk[9:-2] if tk else "", uur))
    return out

# ---------- 2. Meurman & de Rudy (PRIJSBEEST) ----------
def meurman():
    lines = text_lines(get("https://www.meurmanenderudy.com/kalender"))
    out = []
    for l in lines:
        m = re.match(r"^(\d{1,2})\s+([a-z]+)\s+(20\d\d)\s*-\s*(.+)$", l, re.I)
        if not m or "prijsbeest" not in l.lower(): continue
        d = date(int(m.group(3)), MAAND[m.group(2).lower()], int(m.group(1)))
        parts = [p.strip() for p in m.group(4).split(",")]
        parts = [p for p in parts if "prijsbeest" not in p.lower()]
        premiere = any(p.lower().startswith("première") for p in parts)
        parts = [re.sub(r"^première\s*", "", p, flags=re.I) for p in parts]
        zaal = parts[0] if parts else ""; stad = parts[1] if len(parts) > 1 else ""
        if len(parts) > 2 and parts[2].upper() == "NL": stad += " (NL)"
        out.append(row(d, "PRIJSBEEST", "Meurman & de Rudy", "https://www.meurmanenderudy.com/general-9",
                       zaal, stad, "premiere" if premiere else "tickets"))
    return out

# ---------- 3. Céline Timmerman (Bobbety) ----------
def bobbety():
    lines = text_lines(get("https://www.celinetimmerman.com/bobbety"))
    out, seizoen = [], None
    for l in lines:
        m = re.match(r"SEIZOEN (20\d\d)/(20\d\d)", l)
        if m: seizoen = (int(m.group(1)), int(m.group(2))); continue
        m = re.match(r"^(School|Familie|Première)\w*\s+(\d{1,2})\s+([a-z]+)\s*(20\d\d)?\s+(.+?)(?:\s+(\d{1,2}u\d{0,2}))?$", l, re.I)
        if not (m and seizoen): continue
        soort, dag, mnd, jaar, rest, uur = m.groups()
        mnd = MAAND[mnd.lower()]
        jaar = int(jaar) if jaar else (seizoen[0] if mnd >= 8 else seizoen[1])
        pm = re.match(r"^(.*?)\s*\(([^)]+)\)\s*(.*)$", rest)
        zaal, stad = (pm.group(1) + (" " + pm.group(3) if pm.group(3) else ""), pm.group(2)) if pm else (rest, "")
        typ = "school" if soort.lower().startswith("school") else ("premiere" if soort.lower().startswith("premi") else "tickets")
        out.append(row(date(jaar, mnd, int(dag)), "Bobbety", "FroeFroe / Céline Timmerman",
                       "https://www.celinetimmerman.com/bobbety", zaal.strip(), stad.strip(), typ, "", uur or ""))
    return out

# ---------- 4. Laika (WIER) ----------
def laika():
    lines = text_lines(get("https://www.laika.be/NL/wier"))
    out, jaar, buf, cur, stad, zaal = [], None, [], None, "", ""
    def flush():
        if cur: out.append(row(cur["d"], "WIER", "Laika", "https://www.laika.be/NL/wier", zaal, stad,
                               "school" if is_school(cur["t"], cur["d"]) else "tickets", "", " en ".join(cur["t"])))
    i = 0
    while i < len(lines):
        l = lines[i]
        m = re.match(r"^([A-Z][a-z]+) (20\d\d)$", l)
        if m and m.group(1).lower() in MAAND:
            flush(); cur = None; jaar = int(m.group(2)); buf = []; i += 1; continue
        if l.lower() in DAGEN and i + 1 < len(lines) and re.match(r"^\d\d/\d\d$", lines[i + 1]):
            flush(); cur = None
            if buf:
                stad = buf[0]; rest = [b for b in buf[1:] if not re.search(r"\b(AGB|vzw|bestuur|Lokaal|district|Vrije Tijd)\b", b, re.I)]
                zaal = rest[0] if rest else (buf[1] if len(buf) > 1 else "")
            buf = []
            dd, mm = lines[i + 1].split("/")
            if jaar: cur = {"d": date(jaar, int(mm), int(dd)), "t": []}
            i += 2; continue
        if cur and re.match(r"^,?\s*\d\d:\d\d$", l):
            cur["t"].append(l.strip(", ")); i += 1; continue
        if re.search(r"\d{2,3} ?\d{2} ?\d{2}", l) or l.lower() in ("premiere", "première"):
            i += 1; continue
        if jaar and not re.match(r"^(Educatie|Lesmap|Persmap|Pers|Affiche)", l):
            if cur: buf = []
            flush(); cur = None; buf.append(l)
        if re.match(r"^(Educatie|Lesmap)", l): break
        i += 1
    flush()
    return out

# ---------- 5. fABULEUS (Skin in the Game) ----------
def fabuleus():
    lines = text_lines(get("https://www.fabuleus.be/skin-in-the-game"))
    out = []
    for i, l in enumerate(lines):
        m = re.match(r"^(\d{1,2}) ([a-z]{3,4}) (20\d\d) [–-] (.+)$", l, re.I)
        if not m: continue
        d = date(int(m.group(3)), MAAND[m.group(2).lower()], int(m.group(1)))
        t = re.match(r"^(\d\d:\d\d)", lines[i + 1]) if i + 1 < len(lines) else None
        zaal = lines[i + 2] if i + 2 < len(lines) else ""
        out.append(row(d, "Skin In The Game", "fABULEUS", "https://www.fabuleus.be/skin-in-the-game",
                       zaal, m.group(4).title(), "school" if is_school([t.group(1)] if t else [], d) else "tickets",
                       "", t.group(1) if t else ""))
    return out

# ---------- samenvoegen en vergelijken ----------
def merge(rows):
    """Meerdere tijdstippen op dezelfde dag/zaal worden één regel."""
    seen = OrderedDict()
    for r in rows:
        k = (r["datum"], r["voorstelling"].lower(), r["zaal"].lower())
        if k in seen:
            if r["uur"] and r["uur"] not in seen[k]["uur"]:
                seen[k]["uur"] = (seen[k]["uur"] + " en " + r["uur"]).strip(" en ")
            if seen[k]["type"] == "school" and r["type"] != "school": seen[k]["type"] = r["type"]
        else: seen[k] = r
    return list(seen.values())

def norm(s): return re.sub(r"[^a-z0-9]", "", s.lower())

def bestaande():
    url = os.environ.get("SHEET_CSV_URL", "").strip()
    raw = get(url) if url else open(os.path.join(os.path.dirname(__file__), "..", "speellijst.csv"), encoding="utf-8").read()
    rows = list(csv.DictReader(io.StringIO(raw)))
    keys = {}
    for r in rows:
        d = (r.get("datum") or "").strip()
        m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$", d)
        if m:
            y = int(m.group(3)); y = y + 2000 if y < 100 else y
            d = f"{y:04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
        keys.setdefault((d, norm(r.get("voorstelling", ""))[:6]), []).append(norm(r.get("zaal", "")) + norm(r.get("stad", "")))
    return keys

def bekend(r, keys):
    plaatsen = keys.get((r["datum"], norm(r["voorstelling"])[:6]))
    if plaatsen is None: return False
    stad, zaal = norm(r["stad"]), norm(r["zaal"])
    return any((stad and stad in p) or (zaal and (zaal in p or p in zaal)) for p in plaatsen) or not (stad or zaal)

def main():
    gevonden, fouten = [], []
    for naam, fn in [("Hirngespinst", hirngespinst), ("Meurman & de Rudy", meurman), ("Céline Timmerman", bobbety),
                     ("Laika", laika), ("fABULEUS", fabuleus)]:
        try:
            r = fn(); gevonden += r; print(f"{naam}: {len(r)} speelmomenten gelezen")
        except Exception as e:
            fouten.append(f"{naam}: {e}"); print(f"{naam}: FOUT {e}", file=sys.stderr)
    vandaag = date.today().isoformat()
    gevonden = [r for r in merge(gevonden) if r["datum"] >= vandaag]
    keys = bestaande()
    nieuw = [r for r in gevonden if not bekend(r, keys)]
    nieuw.sort(key=lambda r: r["datum"])
    with open("nieuw.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row(date.today(), "", "", "", "", "", "").keys()))
        w.writeheader(); w.writerows(nieuw)
    with open("rapport.md", "w", encoding="utf-8") as f:
        f.write(f"{len(nieuw)} nieuwe speelmomenten gevonden op {vandaag}.\n\n")
        if nieuw:
            f.write("Plak deze regels onderaan in de sheet en zet status op `ok` als ze kloppen:\n\n```csv\n")
            f.write(open("nieuw.csv", encoding="utf-8").read()); f.write("```\n")
        if fouten: f.write("\nBronnen die niet gelezen konden worden:\n" + "\n".join(f"- {x}" for x in fouten) + "\n")
    print(f"{len(nieuw)} nieuw")

if __name__ == "__main__":
    main()
