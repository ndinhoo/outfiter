import random
import re
import pandas as pd
import streamlit as st

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(page_title="Outfiter", page_icon="👕", layout="centered")
st.title("Outfiter")

from pathlib import Path
CSV_PATH = Path(__file__).with_name("fits.csv")

NEUTRALS = {"black", "white", "grey", "gray", "beige", "cream", "navy", "brown"}

# -----------------------------
# LOAD + NORMALIZE
# -----------------------------
@st.cache_data
def load_df(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    # Column normalization (ton CSV a "Style " avec un espace)
    df.columns = [c.strip() for c in df.columns]

    # Ensure required columns exist
    needed = ["CLOTHES NAME", "Category", "Style", "Style Jean", "Temp", "Season", "Colors", "Brand"]
    # Ton fichier a "Style " (avec espace). On gère les 2 cas.
    if "Style " in df.columns and "Style" not in df.columns:
        df = df.rename(columns={"Style ": "Style"})
    if "Style" not in df.columns and "Style " in df.columns:
        df = df.rename(columns={"Style ": "Style"})
    if "Style " not in df.columns and "Style" in df.columns:
        pass

    for c in ["CLOTHES NAME", "Category", "Style", "Style Jean", "Temp", "Season", "Colors", "Brand"]:
        if c not in df.columns:
            df[c] = ""

    # Clean text fields
    for c in ["CLOTHES NAME", "Category", "Style", "Style Jean", "Temp", "Season", "Colors", "Brand"]:
        df[c] = df[c].fillna("").astype(str).str.strip()

    return df

try:
    DF = load_df(CSV_PATH)
except Exception as e:
    st.error(f"Impossible de lire {CSV_PATH}: {e}")
    st.stop()

# -----------------------------
# PARSING HELPERS
# -----------------------------
def norm(s: str) -> str:
    return (s or "").strip().lower()

def split_tokens(s: str):
    if not s:
        return []
    return [norm(x) for x in re.split(r"[,\|/]+", s) if norm(x)]

def primary_color(colors: str) -> str:
    toks = split_tokens(colors)
    return toks[0] if toks else ""

def category_tokens(cat: str):
    # Ex: "Layer, Top" => ["layer", "top"]
    return split_tokens(cat)

def style_tokens(style: str):
    return split_tokens(style)

def season_tokens(season: str):
    return split_tokens(season)

def temp_tokens(temp: str):
    # ton CSV contient """ -20° """, """ +20° """
    t = norm(temp)
    tokens = set()
    if "+20" in t:
        tokens.add("warm")
    if "-20" in t:
        tokens.add("cold")
    # si vide => on considère OK tout le temps
    if not tokens:
        tokens = {"warm", "cold"}
    return tokens

def is_short_name(name: str) -> bool:
    return "short" in norm(name)

def is_baggy_row(row: pd.Series) -> bool:
    # Style Jean = Baggy
    return norm(row.get("Style Jean", "")) == "baggy"

def is_erl_vamp(name: str) -> bool:
    return "erl vamp" in norm(name)

def item_to_dict(row: pd.Series) -> dict:
    return {
        "name": row.get("CLOTHES NAME", ""),
        "category": row.get("Category", ""),
        "style": row.get("Style", ""),
        "style_jean": row.get("Style Jean", ""),
        "temp": row.get("Temp", ""),
        "season": row.get("Season", ""),
        "colors": row.get("Colors", ""),
        "brand": row.get("Brand", ""),
        "primary_color": primary_color(row.get("Colors", "")),
        "cat_tokens": category_tokens(row.get("Category", "")),
        "style_tokens": style_tokens(row.get("Style", "")),
        "season_tokens": season_tokens(row.get("Season", "")),
        "temp_tokens": temp_tokens(row.get("Temp", "")),
        "is_short": is_short_name(row.get("CLOTHES NAME", "")),
        "is_baggy": is_baggy_row(row),
    }

ITEMS = [item_to_dict(r) for _, r in DF.iterrows()]

# -----------------------------
# FILTER POOLS
# -----------------------------
def matches_style(item: dict, style_choice: str) -> bool:
    if style_choice == "any":
        return True
    return norm(style_choice) in item["style_tokens"]

def matches_season(item: dict, season_choice: str) -> bool:
    # Ton CSV a "Others, Summer"
    if season_choice == "any":
        return True
    return norm(season_choice) in item["season_tokens"]

def matches_temp(item: dict, temp_value: int) -> bool:
    # On ne bloque vraiment que dans les extrêmes.
    # - Très chaud (>=25): on privilégie warm
    # - Très froid (<=0): on privilégie cold
    # - Entre 1 et 24: on accepte tout (sinon tu perds trop de pièces)
    if temp_value >= 25:
        return "warm" in item["temp_tokens"] or "cold" in item["temp_tokens"]
    if temp_value <= 0:
        return "cold" in item["temp_tokens"] or "warm" in item["temp_tokens"]
    return True

def pool_for(cat: str, temp_value: int, style_choice: str, season_choice: str):
    cat = norm(cat)
    out = []
    for it in ITEMS:
        if cat in it["cat_tokens"]:
            if matches_style(it, style_choice) and matches_season(it, season_choice) and matches_temp(it, temp_value):
                out.append(it)
    return out

def color_score(base: str, item_color: str) -> int:
    base = norm(base); item_color = norm(item_color)
    if not base or not item_color:
        return 1
    if base in NEUTRALS or item_color in NEUTRALS:
        return 2
    if base == item_color:
        return 3
    return 1

def weighted_pick(items: list[dict], base_color: str):
    if not items:
        return None
    weights = [color_score(base_color, it.get("primary_color","")) for it in items]
    return random.choices(items, weights=weights, k=1)[0]

def pick_one(items: list[dict]):
    return random.choice(items) if items else None

# -----------------------------
# UI INPUTS
# -----------------------------
# styles disponibles depuis le CSV
all_styles = sorted({s for it in ITEMS for s in it["style_tokens"] if s})
all_seasons = sorted({s for it in ITEMS for s in it["season_tokens"] if s})
all_colors = sorted({c for it in ITEMS for c in split_tokens(it["colors"]) if c})

col1, col2 = st.columns(2)
with col1:
    temp = st.number_input("Température (°C)", value=10, step=1)
    occasion = st.selectbox("Occasion", ["casual", "soiree", "entretien"])
with col2:
    style_choice = st.selectbox("Style", ["any"] + all_styles)
    season_choice = st.selectbox("Saison", ["any"] + all_seasons)

color_pref = st.selectbox("Couleur", ["any"] + all_colors)

must_have = st.multiselect(
    "Vêtement(s) imposé(s)",
    options=sorted([it["name"] for it in ITEMS])
)

st.divider()

# -----------------------------
# CORE GENERATOR
# -----------------------------
def generate_outfit(temp_value: int, style_choice: str, season_choice: str, color_pref: str, must_have: list[str]):
    warnings = []

    # Pools
    tops = pool_for("top", temp_value, style_choice, season_choice)
    bottoms = pool_for("bottom", temp_value, style_choice, season_choice)
    shoes = pool_for("shoes", temp_value, style_choice, season_choice)

    # layers = catégorie "layer" OU pièces "layer, top"
    layers = pool_for("layer", temp_value, style_choice, season_choice)

    # Color pref (soft)
    if color_pref != "any":
        def keep_color(lst):
            return [x for x in lst if color_pref in split_tokens(x["colors"])]
        tops_c = keep_color(tops) or tops
        bottoms_c = keep_color(bottoms) or bottoms
        shoes_c = keep_color(shoes) or shoes
        layers_c = keep_color(layers) or layers
    else:
        tops_c, bottoms_c, shoes_c, layers_c = tops, bottoms, shoes, layers

    # Shorts rule: proposer shorts seulement si ≥25
    if temp_value < 25:
        bottoms_c = [b for b in bottoms_c if not b["is_short"]]
        if not bottoms_c:
            bottoms_c = [b for b in bottoms if not b["is_short"]]

    # Must-have placement
    must_items = [it for it in ITEMS if it["name"] in must_have]
    forced = {"top": None, "bottom": None, "shoes": None, "layer": None}
    extras = []

    for it in must_items:
        cats = it["cat_tokens"]
        if "shoes" in cats and not forced["shoes"]:
            forced["shoes"] = it
        elif "bottom" in cats and not forced["bottom"]:
            forced["bottom"] = it
        elif "layer" in cats and not forced["layer"]:
            forced["layer"] = it
        elif "top" in cats and not forced["top"]:
            forced["top"] = it
        else:
            extras.append(it)

    # Pick shoes
    shoe = forced["shoes"] or pick_one(shoes_c)
    if not shoe:
        return None, ["Aucune chaussure trouvée (Category=Shoes)."], []

    # ERL VAMP => baggy bottom
    need_baggy = is_erl_vamp(shoe["name"])

    # Pick bottom
    bottom_pool = bottoms_c
    if need_baggy:
        bottom_pool = [b for b in bottom_pool if b["is_baggy"]]
        if not bottom_pool:
            # fallback: baggy dans tout bottoms (même si style/season/temp filtres trop strict)
            bottom_pool = [b for b in ITEMS if ("bottom" in b["cat_tokens"] and b["is_baggy"])]

    bottom = forced["bottom"] or pick_one(bottom_pool)
    if not bottom:
        return None, ["Impossible de choisir un bottom (check baggy/short)."], []

    # If forced bottom violates rules, override (règles > imposé)
    if need_baggy and not bottom["is_baggy"]:
        warnings.append("ERL VAMP détecté → bottom baggy obligatoire. J’ai remplacé ton bottom par un baggy.")
        bottom = pick_one(bottom_pool)
        if not bottom:
            return None, ["ERL VAMP exige un baggy, mais aucun baggy dispo."], []

    if temp_value < 25 and bottom["is_short"]:
        warnings.append("Temp < 25°C → shorts désactivés. J’ai remplacé le short par un pantalon.")
        # replace by non-short
        non_short = [b for b in bottoms if "bottom" in b["cat_tokens"] and not b["is_short"]]
        bottom = pick_one(non_short) or bottom

    base_color = bottom.get("primary_color") or ""

    # Pick top (match bottom)
    top = forced["top"] or weighted_pick(tops_c, base_color) or pick_one(tops_c)
    if not top:
        return None, ["Aucun top trouvé (Category=Top)."], []

    # Layer rule: temp < 20 => layer obligatoire
    layer = forced["layer"]
    if temp_value < 20 and not layer:
        layer = weighted_pick(layers_c, base_color) or pick_one(layers_c)
        if not layer:
            warnings.append("Temp < 20°C → layer demandé, mais aucun item Category=Layer trouvé dans le CSV.")

    # Extra: si user impose une 2e pièce Top et qu’on a besoin d’un layer, on peut l’utiliser
    if temp_value < 20 and not layer:
        for ex in extras:
            if "top" in ex["cat_tokens"] and ("layer" in ex["cat_tokens"] or True):
                layer = ex
                extras = [x for x in extras if x != ex]
                break

    outfit = {"TOP": top, "BOTTOM": bottom, "SHOES": shoe, "LAYER": layer}
    return outfit, warnings, extras

from typing import Optional, Dict

def fmt(it: Optional[Dict]) -> str:
    if not it:
        return "—"
    extra = " · ".join([x for x in [it.get("brand",""), it.get("colors","")] if x])
    return f"**{it.get('name','')}**" + (f"  \n_{extra}_" if extra else "")

# -----------------------------
# BUTTON
# -----------------------------
if st.button("🎲 Générer l'outfit", use_container_width=True):
    best = None
    best_score = -1
    best_warnings = []
    best_extras = []

    # On tente plusieurs fois pour mieux satisfaire les items imposés + couleurs
    for _ in range(40):
        outfit, warnings, extras = generate_outfit(int(temp), style_choice, season_choice, color_pref, must_have)
        if not outfit:
            continue
        included = {outfit[k]["name"] for k in outfit if outfit[k]}
        included |= {x["name"] for x in extras}
        score = sum(1 for x in must_have if x in included)
        if score > best_score:
            best = outfit
            best_score = score
            best_warnings = warnings
            best_extras = extras
        if score == len(must_have):
            break

    if not best:
        st.error("Impossible de générer un outfit. Vérifie tes catégories (Top/Bottom/Shoes/Layer) dans le CSV.")
    else:
        st.subheader("✅ TON OUTFIT")

        st.write("### 🧥 LAYER ")
        st.write(fmt(best["LAYER"]))

        st.write("### 👕 TOP")
        st.write(fmt(best["TOP"]))

        st.write("### 👖 BOTTOM")
        st.write(fmt(best["BOTTOM"]))

        st.write("### 👟 SHOES")
        st.write(fmt(best["SHOES"]))

        # Extras (si tu imposes 2 tops etc.)
        if best_extras:
            st.write("### ➕ Pièces imposées en plus")
            for ex in best_extras:
                st.write(fmt(ex))

        if best_warnings:
            for w in best_warnings:
                st.warning(w)
