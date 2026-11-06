#!/usr/bin/env python3
"""Télécharge les deux jeux de données sources via l'API CKAN de Données Québec."""
import json, sys, urllib.request

API = "https://www.donneesquebec.ca/recherche/api/3/action/resource_show?id="
SOURCES = {
    # Signalisation (stationnement sur rue), CSV
    "signalisation_stationnement.csv": "7f1d4ae9-1a12-46d7-953e-6b9c18c78680",
    # Géobase, réseau routier, GeoJSON
    "geobase.json": "9d3d60d8-4e7f-493e-8d6a-dcd040319d8d",
}
UA = {"User-Agent": "stationnement-metro/1.0 (GitHub Actions)"}

for fname, rid in SOURCES.items():
    with urllib.request.urlopen(urllib.request.Request(API + rid, headers=UA), timeout=60) as r:
        res = json.load(r)["result"]
    url = res["url"]
    print(f"{fname} <- {res.get('name')} ({url})")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r, open(fname, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
