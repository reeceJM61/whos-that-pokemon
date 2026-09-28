"""
Who's That Pokémon? — Flask version
-------------------------------------
A silhouette guessing game using live sprite data from PokéAPI, served as
a small web app instead of a tkinter GUI.

Requirements:
    pip install flask requests pillow

Run:
    python app.py
    # then open http://localhost:5000

Environment:
    FLASK_SECRET_KEY   - optional, used to sign the session cookie
"""

import io
import os
import random
from functools import lru_cache

import requests
from flask import Flask, session, render_template, request, redirect, url_for, send_file
from PIL import Image

POKEAPI_SPECIES_URL = "https://pokeapi.co/api/v2/pokemon-species/{id}/"
POKEAPI_POKEMON_URL = "https://pokeapi.co/api/v2/pokemon/{id}/"

# 1-151 = Gen 1 only. Change to (1, 1025) for all currently known Pokémon.
DEX_RANGE = (1, 151)
SPRITE_DISPLAY_SIZE = (300, 300)

# Resolve the templates folder relative to this file's location, so the
# app finds it regardless of the working directory it's launched from.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")


# ---------------------------------------------------------------------------
# PokéAPI helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=256)
def fetch_pokemon(dex_id: int):
    """Fetch (english_name, image_bytes) for a dex id. Cached process-wide
    since sprite artwork never changes."""
    species_resp = requests.get(POKEAPI_SPECIES_URL.format(id=dex_id), timeout=10)
    species_resp.raise_for_status()
    species_data = species_resp.json()

    english_name = next(
        entry["name"]
        for entry in species_data["names"]
        if entry["language"]["name"] == "en"
    )

    pokemon_resp = requests.get(POKEAPI_POKEMON_URL.format(id=dex_id), timeout=10)
    pokemon_resp.raise_for_status()
    pokemon_data = pokemon_resp.json()

    artwork_url = pokemon_data["sprites"]["other"]["official-artwork"]["front_default"]
    if not artwork_url:
        artwork_url = pokemon_data["sprites"]["front_default"]

    image_resp = requests.get(artwork_url, timeout=10)
    image_resp.raise_for_status()

    return english_name, image_resp.content


def make_silhouette(image_bytes: bytes) -> Image.Image:
    """Turn non-transparent pixels solid black, keep alpha channel."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img = img.resize(SPRITE_DISPLAY_SIZE, Image.LANCZOS)
    _, _, _, a = img.split()
    black = Image.new("RGBA", img.size, (0, 0, 0, 255))
    black.putalpha(a)
    return black


def make_reveal(image_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    return img.resize(SPRITE_DISPLAY_SIZE, Image.LANCZOS)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def start_new_round():
    dex_id = random.randint(*DEX_RANGE)
    name, _ = fetch_pokemon(dex_id)  # validates it resolves + warms cache
    session["dex_id"] = dex_id
    session["answer"] = name.lower()
    session["display_name"] = name
    session["revealed"] = False
    session.setdefault("score", 0)
    session.setdefault("streak", 0)
    session["feedback"] = None
    session["feedback_kind"] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    if "dex_id" not in session:
        start_new_round()
    return render_template(
        "index.html",
        score=session.get("score", 0),
        streak=session.get("streak", 0),
        revealed=session.get("revealed", False),
        display_name=session.get("display_name"),
        feedback=session.get("feedback"),
        feedback_kind=session.get("feedback_kind"),
    )


@app.route("/image")
def image():
    """Serves the silhouette (or the real artwork once revealed) as a PNG."""
    if "dex_id" not in session:
        start_new_round()

    _, image_bytes = fetch_pokemon(session["dex_id"])
    pil_img = make_reveal(image_bytes) if session.get("revealed") else make_silhouette(image_bytes)

    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/guess", methods=["POST"])
def guess():
    if "dex_id" not in session or session.get("revealed"):
        return redirect(url_for("index"))

    submitted = (request.form.get("guess") or "").strip().lower()
    answer = session.get("answer", "")

    if submitted and submitted == answer:
        session["score"] = session.get("score", 0) + 1
        session["streak"] = session.get("streak", 0) + 1
        session["revealed"] = True
        session["feedback"] = f"Correct! It's {session['display_name']}!"
        session["feedback_kind"] = "correct"
    else:
        session["streak"] = 0
        session["feedback"] = "Nope, try again!"
        session["feedback_kind"] = "wrong"

    return redirect(url_for("index"))


@app.route("/reveal", methods=["POST"])
def reveal():
    if "dex_id" in session and not session.get("revealed"):
        session["streak"] = 0
        session["revealed"] = True
        session["feedback"] = f"It was {session['display_name']}!"
        session["feedback_kind"] = "revealed"
    return redirect(url_for("index"))


@app.route("/next", methods=["POST"])
def next_round():
    start_new_round()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5000)