#!/usr/bin/env python3
"""
Construit les données de la carte « Gare-toi au métro » pour toute l'île de Montréal.

Sortie :
  <dossier>/meta.json            règles (libellés interprétés), stations, liste des tuiles
  <dossier>/tiles/<ky>_<kx>.json tronçons et portions de bordure, tuiles d'environ 1 km,
                                 chargées à la demande par la page

Entrées (données ouvertes de la Ville de Montréal, CC BY 4.0) :
  - signalisation_stationnement.csv  (Signalisation, stationnement sur rue)
  - geobase.json                     (Géobase, réseau routier, GeoJSON)

Usage :
  python3 scripts/build_data.py signalisation_stationnement.csv geobase.json data

Pour ajouter des stations, modifier STATIONS ci-dessous puis relancer.
"""
import os, sys, re, json, math, unicodedata, collections
import pandas as pd

STATIONS = [
    {"n": "Honoré-Beaugrand", "lat": 45.59677, "lon": -73.53569},
    {"n": "Radisson",         "lat": 45.58915, "lon": -73.53943},
    {"n": "Langelier",        "lat": 45.58283, "lon": -73.54295},
    {"n": "Cadillac",         "lat": 45.57708, "lon": -73.54684},
    {"n": "L'Assomption",     "lat": 45.56960, "lon": -73.54690},
]
MAX_DIST_POTEAU = 35    # distance max poteau -> tronçon (m)
COUVERTURE_MIN = 15     # poteaux/km de rue locale : en deçà, la signalisation du secteur est jugée incomplète
TILE_LAT, TILE_LON = 0.009, 0.0128   # ~1 km x 1 km ; doit correspondre à index.html

K = 111320.0
LAT0, LON0 = 45.55, -73.65           # projection locale (île de Montréal)
COS = math.cos(math.radians(LAT0))
def P(lon, lat): return ((lon - LON0) * K * COS, (lat - LAT0) * K)
def INV(x, y): return (LON0 + x / (K * COS), LAT0 + y / K)
def tile_key(lon, lat): return f"{math.floor(lat / TILE_LAT)}_{math.floor(lon / TILE_LON)}"

# ---------- 1. Interprétation des libellés RPA ----------
DAYS = {'LUN':0,'LUNDI':0,'MAR':1,'MARDI':1,'MER':2,'MERCREDI':2,'JEU':3,'JEUDI':3,
        'VEN':4,'VENDREDI':4,'SAM':5,'SAMEDI':5,'DIM':6,'DIMANCHE':6}
DAYRX = r'(?:LUNDI|MARDI|MERCREDI|JEUDI|VENDREDI|SAMEDI|DIMANCHE|LUN|MAR|MER|JEU|VEN|SAM|DIM)'
def month(w):
    for k, v in (('JANV',1),('FEV',2),('MARS',3),('AVR',4),('MAI',5),('JUIN',6),('JUIL',7),
                 ('AOU',8),('SEP',9),('OCT',10),('NOV',11),('DEC',12)):
        if w.startswith(k): return v
    return None
TIME = r'(\d{1,2})\s*H(\d{2})?\s*(?:-|A|@|AU)\s*(\d{1,2})\s*H(\d{2})?'
ALL = list(range(7))

def norm(t):
    t = unicodedata.normalize('NFD', t)
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    t = t.upper().replace('\\\\', '\\').replace('`', "'")
    return re.sub(r'\s+', ' ', t).strip()

def category(t):
    """Catégorie d'un libellé normalisé (sans accents, majuscules)."""
    if re.search(r'AUX CAMIONS|AUX AUTOBUS|PLUS DE 2,3M|^P A ANGLE|^P EN FILE|REGLEMENT \d|^SORTIE|^RAPPEL|^REMORQUAGE|'
                 r'STAT MUNICIPAL|^PANONCEAU EXCEPTE|^EXCEPTE|^SAUF', t):
        return 'info'
    if re.search(r'TARIF|PARCOMETRE|PAYANT|PARCOJOUR', t): return 'tarife'
    interd = t.startswith(('\\A', '\\P', 'P\\', 'A\\')) or re.match(r'(ARRET|STATIONNEMENT) INTERDIT', t) \
        or re.match(r'A \d', t)
    if interd:
        if re.search(r'EXCEPTE S\d|EXCEPTE S3R|VIGNETTE|DETENTEURS? DE PERMIS|SECTEUR', t): return 'vignette'
        if re.search(r'EXCEPTE|RESERVE|POMPIER|LIVRAISON', t): return 'reserve'
        return 'interdit'
    if re.search(r'RESERVE|GARDERIE|SEULEMENT|COMMUNAUTO|DEBARCADERE|AUTOBUS|DETENTEURS? DE PERMIS|ESPACE|POMPIER|LIVRAISON|VISITEURS', t):
        return 'reserve'
    if re.match(r'P ?\d+\s*(MIN|H)', t) or re.match(r'\d+\s*MIN', t): return 'limite'
    if re.match(r'(DE )?\d{1,2}\s*H', t) or re.match(DAYRX + r'\b', t):
        return 'interdit'      # panonceau d'horaire seul : interdiction (prudent)
    return 'info'

def parse_rule(raw):
    t = norm(raw); r = {'c': category(t)}
    if r['c'] == 'limite':
        m = re.match(r'P ?(\d+)\s*(MIN|H)', t) or re.match(r'(\d+)\s*(MIN)', t)
        r['d'] = int(m.group(1)) * (1 if m.group(2) == 'MIN' else 60)
    if 'CLIGNOTANT' in t or 'EN TOUT TEMPS' in t:
        r['m'] = None; r['w'] = [[0, 1440, ALL]]; return r
    months = None
    m = re.search(r'(?:DU )?(\d{1,2})\s*(?:ER)?\s*([A-Z]{3,9})\.?\s*(?:-|AU|A)\s*(\d{1,2})\s*(?:ER)?\s*([A-Z]{3,9})\.?', t)
    if m and month(m.group(2)) and month(m.group(4)):
        months = [month(m.group(2)), int(m.group(1)), month(m.group(4)), int(m.group(3))]
        t = t[:m.start()] + ' ' + t[m.end():]
    m = re.search(r'SEPT\.? A JUIN', t)
    if m: months = [9, 1, 6, 30]; t = t[:m.start()] + ' ' + t[m.end():]
    if re.search(r"JOURS D'ECOLE|JOURS DE CLASSE", t):     # approximation : lun-ven, sept. à juin
        months = months or [9, 1, 6, 23]
        t = re.sub(r"JOURS D'ECOLE|JOURS DE CLASSE", ' LUN A VEN ', t)
    r['m'] = months
    t = re.sub(r'(' + DAYRX + r')\.?\s*-\s*(' + DAYRX + r')\b', r'\1 A \2', t)
    toks = []
    for m in re.finditer(TIME + r'|([A-Z]+)', t):
        if m.group(1) is not None:
            toks.append(('T', int(m.group(1))*60 + int(m.group(2) or 0),
                               int(m.group(3))*60 + int(m.group(4) or 0)))
        else: toks.append(('W', m.group(5)))
    groups, cur = [], None
    def new(): return {'t': [], 'd': [], 'pre': False}
    prev, rng = None, False
    for tok in toks:
        if tok[0] == 'T':
            if cur is None: cur = new()
            elif cur['t'] and cur['d']: groups.append(cur); cur = new()
            cur['t'].append((tok[1], tok[2])); prev = None
        else:
            w = tok[1]
            if w in DAYS:
                if cur is None: cur = new(); cur['pre'] = True
                elif cur['pre'] and cur['t'] and prev is None:
                    groups.append(cur); cur = new(); cur['pre'] = True
                elif not cur['t']: cur['pre'] = True
                d = DAYS[w]
                if rng and prev is not None:
                    x = prev
                    while x != d: x = (x + 1) % 7; cur['d'].append(x)
                else: cur['d'].append(d)
                prev, rng = d, False
            elif w in ('A', 'AU') and prev is not None: rng = True
            else: rng = False
    if cur: groups.append(cur)
    wins = []
    for g in groups:
        days = sorted(set(g['d'])) if g['d'] else ALL
        for a, b in (g['t'] or [(0, 1440)]):
            wins.append([a, 1440 if b == 1440 or (b == 0 and a > 0) else b, days])
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
        name = (pr.get('ODONYME') or '').strip() or (pr.get('NOM_VOIE') or '')
        T.append({'c': c, 'pts': pts, 'k': pr.get('CLASSE'), 'n': name, 'arr': pr.get('ARR_GCH') or 'N/A'})
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
    return [[round(v, 5) for v in INV(*p)] for p in out]

def main(csv_path, geo_path, out_dir):
    s = pd.read_csv(csv_path)
    s = s[(s.DESCRIPTION_REP == 'Réel') & (s.PAS_SUR_RUE.isna()) & s.Latitude.notna()]
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

    # couverture : densité de poteaux par km de rue locale ou collectrice, par arrondissement / ville
    narr = lambda a: re.sub(r'\s*[-–]\s*', '-', str(a)).strip().lower()
    poles = s.groupby('NOM_ARROND').POTEAU_ID_POT.nunique()
    poles = {narr(k): v for k, v in poles.items()}
    km = collections.Counter()
    for t in T:
        if t['k'] in (0, 5): km[narr(t['arr'])] += t['L'] / 1000
    couvert = {a for a, L in km.items() if L and poles.get(a, 0) / L >= COUVERTURE_MIN}
    print('Signalisation complète :', ', '.join(sorted(couvert)))

    tiles = collections.defaultdict(lambda: {'tr': [], 'f': []})
    for i, t in enumerate(T):
        mlon, mlat = sub_coords(t, t['L'] / 2, t['L'] / 2)[0]
        tile = tiles[tile_key(mlon, mlat)]
        j = len(tile['tr'])
        tile['tr'].append({'n': t['n'], 'e': t['e'], 'k': t['k'], 'ln': t['ln'], 'rn': t['rn'], 'L': round(t['L'], 1),
                           'cv': 1 if narr(t['arr']) in couvert else 0})
        for side in (1, -1):
            lst = sorted(bys[i][side], key=lambda z: z[0]) if i in bys else []
            if not lst:
                tile['f'].append([j, side, 0, round(t['L'], 1), [], 1, sub_coords(t, 0, t['L'])]); continue
            b = [0] + [z[0] for z in lst] + [t['L']]
            for k in range(len(b) - 1):
                if b[k+1] - b[k] < 0.5: continue
                rs = set()
                if k > 0: rs |= {r for r, a in lst[k-1][1] if 1 in dirs(a, side)}
                if k < len(lst): rs |= {r for r, a in lst[k][1] if -1 in dirs(a, side)}
                tile['f'].append([j, side, round(b[k], 1), round(b[k+1], 1), sorted(rs), 0, sub_coords(t, b[k], b[k+1])])

    os.makedirs(os.path.join(out_dir, 'tiles'), exist_ok=True)
    for old in os.listdir(os.path.join(out_dir, 'tiles')):
        if old.endswith('.json'): os.remove(os.path.join(out_dir, 'tiles', old))
    total = 0
    for key, tile in tiles.items():
        path = os.path.join(out_dir, 'tiles', key + '.json')
        json.dump(tile, open(path, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
        total += os.path.getsize(path)
    meta = {'generated': pd.Timestamp.now().strftime('%Y-%m-%d'), 'tile': [TILE_LAT, TILE_LON],
            'stations': STATIONS, 'rules': rules, 'tiles': sorted(tiles)}
    json.dump(meta, open(os.path.join(out_dir, 'meta.json'), 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    print(f"{len(rules)} libellés, {len(T)} tronçons, {len(tiles)} tuiles ({total/1e6:.1f} Mo) -> {out_dir}/")

if __name__ == '__main__':
    main(*sys.argv[1:4])
