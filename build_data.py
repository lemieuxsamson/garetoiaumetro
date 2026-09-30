#!/usr/bin/env python3
"""
Construit data.json pour la carte « Stationnement gratuit probable près du métro ».

Entrées (données ouvertes de la Ville de Montréal, CC BY 4.0) :
  - signalisation_stationnement.csv  (Signalisation, stationnement sur rue)
  - geobase.json                     (Géobase, réseau routier, GeoJSON)

Usage :
  python3 scripts/build_data.py signalisation_stationnement.csv geobase.json data.json

Pour ajouter des stations, modifier STATIONS ci-dessous puis relancer.
"""
import sys, re, json, math, unicodedata, collections
import pandas as pd

STATIONS = [
    {"n": "Honoré-Beaugrand", "lat": 45.59677, "lon": -73.53569},
    {"n": "Radisson",         "lat": 45.58915, "lon": -73.53943},
    {"n": "Langelier",        "lat": 45.58283, "lon": -73.54295},
    {"n": "Cadillac",         "lat": 45.57708, "lon": -73.54684},
    {"n": "L'Assomption",     "lat": 45.56960, "lon": -73.54690},
]
RAYON_M = 1050          # rayon de découpe autour des stations
MAX_DIST_POTEAU = 35    # distance max poteau -> tronçon (m)

K = 111320.0
LAT0 = sum(s["lat"] for s in STATIONS) / len(STATIONS)
LON0 = sum(s["lon"] for s in STATIONS) / len(STATIONS)
COS = math.cos(math.radians(LAT0))
def P(lon, lat): return ((lon - LON0) * K * COS, (lat - LAT0) * K)
def INV(x, y): return (LON0 + x / (K * COS), LAT0 + y / K)
SP = [P(s["lon"], s["lat"]) for s in STATIONS]
def near(x, y, r): return any(math.hypot(x - a, y - b) < r for a, b in SP)

# ---------- 1. Interprétation des libellés RPA ----------
DAYS = {'LUN':0,'LUNDI':0,'MAR':1,'MARDI':1,'MER':2,'MERCREDI':2,'JEU':3,'JEUDI':3,
        'VEN':4,'VENDREDI':4,'SAM':5,'SAMEDI':5,'DIM':6,'DIMANCHE':6}
MON = {'JANV':1,'FEV':2,'MARS':3,'AVRIL':4,'AVR':4,'MAI':5,'JUIN':6,'JUIL':7,'AOUT':8,
       'SEPT':9,'OCT':10,'NOV':11,'DEC':12}
TIME = r'(\d{1,2})\s*H(\d{2})?'
ALL = list(range(7))

def norm(t):
    t = unicodedata.normalize('NFD', t)
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    t = t.upper().replace('\\\\', '\\').replace('`', "'")
    return re.sub(r'\s+', ' ', t).strip()

def parse_rule(raw):
    t = norm(raw); r = {}
    if t.startswith('\\A') or t.startswith('\\P'):
        if 'EXCEPTE S3R' in t: cat = 'vignette'
        elif re.search(r'AUX AUTOBUS|AUX CAMIONS|PLUS DE 2,3M', t): cat = 'info'
        elif re.search(r'EXCEPTE|RESERVE|POMPIER', t): cat = 'reserve'
        else: cat = 'interdit'
    elif t.startswith('STATIONNEMENT TARIFE'): cat = 'tarife'
    elif re.match(r'P \d', t):
        cat = 'reserve' if re.search(r'GARDERIE|RESERVE', t) else 'limite'
        m = re.match(r'P (\d+)\s*(MIN|H)', t)
        if m: r['d'] = int(m.group(1)) * (1 if m.group(2) == 'MIN' else 60)
    elif t.startswith('P DEBARCADERE'): cat = 'reserve'
    else: cat = 'info'
    r['c'] = cat
    if 'CLIGNOTANT' in t:
        r['m'] = None; r['w'] = [[0, 1440, ALL]]; return r
    months = None
    m = re.search(r'(\d{1,2})\s*([A-Z]+)\.? AU (\d{1,2})\s*([A-Z]+)', t)
    if m and m.group(2) in MON and m.group(4) in MON:
        months = [MON[m.group(2)], int(m.group(1)), MON[m.group(4)], int(m.group(3))]
        t = t[:m.start()] + t[m.end():]
    m = re.search(r'SEPT\.? A JUIN', t)
    if m: months = [9, 1, 6, 30]; t = t[:m.start()] + t[m.end():]
    if "JOURS D'ECOLE" in t:           # approximation : lun-ven, sept. à juin
        months = [9, 1, 6, 23]; t = t.replace("JOURS D'ECOLE", ' LUN A VEN ')
    r['m'] = months
    toks = []
    for m in re.finditer(TIME + r'\s*-\s*' + TIME + r'|([A-Z]+)\.?', t):
        if m.group(1) is not None:
            toks.append(('T', int(m.group(1))*60 + int(m.group(2) or 0),
                               int(m.group(3))*60 + int(m.group(4) or 0)))
        elif m.group(5): toks.append(('W', m.group(5)))
    wins, pend, days = [], [], []
    prev, rng = None, False
    def flush():
        nonlocal pend, days
        for a, b in pend: wins.append([a, b, sorted(set(days)) if days else ALL])
        pend, days = [], []
    for tok in toks:
        if tok[0] == 'T':
            if days: flush()
            pend.append((tok[1], tok[2]))
        else:
            w = tok[1]
            if w in DAYS and pend:
                d = DAYS[w]
                if rng and prev is not None:
                    x = prev
                    while x != d: x = (x + 1) % 7; days.append(x)
                else: days.append(d)
                prev, rng = d, False
            elif w in ('A', 'AU') and prev is not None: rng = True
            else: rng = False
    flush()
    r['w'] = wins or [[0, 1440, ALL]]
    return r

def clean(t):
    t = ' '.join(t.replace('\\\\', '\\').split())
    return t.replace('\\P', 'Stationnement interdit').replace('\\A', 'Arrêt interdit')

# ---------- 2. Géobase ----------
def load_geobase(path):
    G = json.load(open(path, encoding='utf-8'))
    T = []
    for f in G['features']:
        g = f['geometry']
        if not g or g['type'] != 'LineString': continue
        c, pr = g['coordinates'], f['properties']
        if pr.get('CLASSE') in (1, 3, 9): continue          # piétonnier, quai, projeté
        pts = [P(*p) for p in c]
        if not any(near(x, y, RAYON_M) for x, y in pts[::max(1, len(pts)//4)] + [pts[-1]]): continue
        name = (pr.get('ODONYME') or '').strip() or (pr.get('NOM_VOIE') or '')
        T.append({'c': c, 'pts': pts, 'k': pr.get('CLASSE'), 'n': name})
    ends = collections.defaultdict(set)
    key = lambda p: (round(p[0], 5), round(p[1], 5))
    for t in T:
        for p in (t['c'][0], t['c'][-1]): ends[key(p)].add(t['n'])
    for t in T:
        e = []
        for p in (t['c'][0], t['c'][-1]):
            o = sorted(n for n in ends[key(p)] if n and n != t['n'])
            e.append(o[0] if o else None)
        t['e'] = e
        cum = [0.0]
        for a, b in zip(t['pts'], t['pts'][1:]): cum.append(cum[-1] + math.hypot(b[0]-a[0], b[1]-a[1]))
        t['cum'] = cum; t['L'] = cum[-1]
        gx, gy = t['pts'][-1][0]-t['pts'][0][0], t['pts'][-1][1]-t['pts'][0][1]
        ang = math.degrees(math.atan2(gx, -gy)) % 360        # normale gauche (-gy, gx)
        nm = lambda a: ['est', 'nord', 'ouest', 'sud'][int(((a + 45) % 360) // 90)]
        t['ln'], t['rn'] = nm(ang), nm(ang + 180)
    return T

def proj(t, x, y):
    best = (1e9, 0, 0)
    for j, (a, b) in enumerate(zip(t['pts'], t['pts'][1:])):
        dx, dy = b[0]-a[0], b[1]-a[1]; L2 = dx*dx + dy*dy
        u = 0 if L2 == 0 else max(0, min(1, ((x-a[0])*dx + (y-a[1])*dy) / L2))
        d = math.hypot(x-a[0]-u*dx, y-a[1]-u*dy)
        if d < best[0]:
            cr = dx*(y-a[1]) - dy*(x-a[0])
            best = (d, t['cum'][j] + u*math.sqrt(L2), 1 if cr > 0 else -1)
    return best

def sub_coords(t, t0, t1):
    def at(tm):
        cum, pts = t['cum'], t['pts']
        for j in range(1, len(cum)):
            if cum[j] >= tm:
                f = (tm - cum[j-1]) / ((cum[j] - cum[j-1]) or 1)
                return (pts[j-1][0] + f*(pts[j][0]-pts[j-1][0]), pts[j-1][1] + f*(pts[j][1]-pts[j-1][1]))
        return pts[-1]
    out = [at(t0)] + [t['pts'][j] for j in range(1, len(t['cum'])-1) if t0 < t['cum'][j] < t1] + [at(t1)]
    return [[round(v, 6) for v in INV(*p)] for p in out]

def main(csv_path, geo_path, out_path):
    s = pd.read_csv(csv_path)
    s = s[(s.DESCRIPTION_REP == 'Réel') & (s.PAS_SUR_RUE.isna())]
    xy = [P(lo, la) for lo, la in zip(s.Longitude, s.Latitude)]
    s = s[[near(x, y, RAYON_M) for x, y in xy]]
    keys = list(dict.fromkeys(s.DESCRIPTION_RPA))
    idx = {k: i for i, k in enumerate(keys)}
    rules = []
    for k in keys:
        r = parse_rule(k); r['t'] = clean(k); rules.append(r)

    T = load_geobase(geo_path)
    grid = collections.defaultdict(set)
    for i, t in enumerate(T):
        for x, y in t['pts']: grid[(int(x//60), int(y//60))].add(i)

    bys = collections.defaultdict(lambda: {1: [], -1: []})
    for pid, g in s.groupby('POTEAU_ID_POT'):
        x, y = P(g.Longitude.iloc[0], g.Latitude.iloc[0])
        cand = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1): cand |= grid.get((int(x//60)+dx, int(y//60)+dy), set())
        best = None
        for i in cand:
            d, tm, side = proj(T[i], x, y)
            if best is None or d < best[0]: best = (d, i, tm, side)
        if not best or best[0] > MAX_DIST_POTEAU: continue
        panels = sorted({(idx[r], int(a)) for r, a in zip(g.DESCRIPTION_RPA, g.FLECHE_PAN)})
        bys[best[1]][best[3]].append((best[2], panels))

    # flèche : 0 ou 8 = deux sens ; 2 = gauche ; 3 = droite (vu de la rue, face au panneau)
    def dirs(arrow, side):
        if arrow not in (2, 3): return (1, -1)
        g = 1 if side == -1 else -1
        return (g,) if arrow == 2 else (-g,)

    feats, tr = [], []
    for i, t in enumerate(T):
        tr.append({'n': t['n'], 'e': t['e'], 'k': t['k'], 'ln': t['ln'], 'rn': t['rn'], 'L': round(t['L'], 1)})
        for side in (1, -1):
            lst = sorted(bys[i][side], key=lambda z: z[0]) if i in bys else []
            if not lst:
                feats.append([i, side, 0, round(t['L'], 1), [], 1, sub_coords(t, 0, t['L'])]); continue
            b = [0] + [z[0] for z in lst] + [t['L']]
            for k in range(len(b) - 1):
                if b[k+1] - b[k] < 0.5: continue
                rs = set()
                if k > 0: rs |= {r for r, a in lst[k-1][1] if 1 in dirs(a, side)}
                if k < len(lst): rs |= {r for r, a in lst[k][1] if -1 in dirs(a, side)}
                feats.append([i, side, round(b[k], 1), round(b[k+1], 1), sorted(rs), 0, sub_coords(t, b[k], b[k+1])])
    out = {'generated': pd.Timestamp.now().strftime('%Y-%m-%d'), 'stations': STATIONS,
           'rules': rules, 'tr': tr, 'f': feats}
    json.dump(out, open(out_path, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    print(f"{len(rules)} libellés, {len(tr)} tronçons, {len(feats)} portions -> {out_path}")

if __name__ == '__main__':
    main(*sys.argv[1:4])
