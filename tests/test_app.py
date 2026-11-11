import io

from PIL import Image

import app as app_module


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def test_make_silhouette_is_black_where_opaque():
    sprite = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
    buf = io.BytesIO()
    sprite.save(buf, format="PNG")

    result = app_module.make_silhouette(buf.getvalue())

    assert result.size == app_module.SPRITE_DISPLAY_SIZE
    r, g, b, a = result.getpixel((0, 0))
    assert (r, g, b) == (0, 0, 0)
    assert a == 255


def test_make_silhouette_preserves_transparency():
    sprite = Image.new("RGBA", (10, 10), (255, 0, 0, 0))
    buf = io.BytesIO()
    sprite.save(buf, format="PNG")

    result = app_module.make_silhouette(buf.getvalue())

    _, _, _, a = result.getpixel((0, 0))
    assert a == 0


def test_make_reveal_resizes_and_keeps_colors():
    sprite = Image.new("RGBA", (10, 10), (10, 20, 30, 255))
    buf = io.BytesIO()
    sprite.save(buf, format="PNG")

    result = app_module.make_reveal(buf.getvalue())

    assert result.size == app_module.SPRITE_DISPLAY_SIZE
    assert result.getpixel((0, 0)) == (10, 20, 30, 255)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def test_index_starts_a_round_and_returns_200(client, mock_fetch_pokemon):
    resp = client.get("/")

    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert sess["answer"] == "bulbasaur"
        assert sess["display_name"] == "Bulbasaur"
        assert sess["revealed"] is False


def test_image_endpoint_returns_png(client, mock_fetch_pokemon):
    resp = client.get("/image")

    assert resp.status_code == 200
    assert resp.mimetype == "image/png"


def test_correct_guess_updates_score_and_reveals(client, mock_fetch_pokemon):
    client.get("/")

    resp = client.post("/guess", data={"guess": "Bulbasaur"})

    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess["score"] == 1
        assert sess["streak"] == 1
        assert sess["revealed"] is True
        assert sess["feedback_kind"] == "correct"


def test_correct_guess_is_case_insensitive(client, mock_fetch_pokemon):
    client.get("/")

    client.post("/guess", data={"guess": "  bulbaSAUR  "})

    with client.session_transaction() as sess:
        assert sess["revealed"] is True


def test_wrong_guess_resets_streak_without_revealing(client, mock_fetch_pokemon):
    client.get("/")
    with client.session_transaction() as sess:
        sess["streak"] = 3

    client.post("/guess", data={"guess": "charmander"})

    with client.session_transaction() as sess:
        assert sess["streak"] == 0
        assert sess["revealed"] is False
        assert sess["feedback_kind"] == "wrong"


def test_guess_without_active_round_redirects_to_index(client, mock_fetch_pokemon):
    resp = client.post("/guess", data={"guess": "bulbasaur"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


def test_guess_after_already_revealed_redirects_without_scoring(client, mock_fetch_pokemon):
    client.get("/")
    with client.session_transaction() as sess:
        sess["revealed"] = True
        sess["score"] = 5

    client.post("/guess", data={"guess": "bulbasaur"})

    with client.session_transaction() as sess:
        assert sess["score"] == 5


def test_reveal_sets_feedback_and_resets_streak(client, mock_fetch_pokemon):
    client.get("/")
    with client.session_transaction() as sess:
        sess["streak"] = 2

    resp = client.post("/reveal")

    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess["revealed"] is True
        assert sess["streak"] == 0
        assert sess["feedback_kind"] == "revealed"
        assert sess["display_name"] in sess["feedback"]


def test_reveal_is_noop_once_already_revealed(client, mock_fetch_pokemon):
    client.get("/")
    with client.session_transaction() as sess:
        sess["revealed"] = True
        sess["feedback"] = "existing"
        sess["feedback_kind"] = "correct"

    client.post("/reveal")

    with client.session_transaction() as sess:
        assert sess["feedback"] == "existing"
        assert sess["feedback_kind"] == "correct"


def test_next_round_starts_fresh_round_and_keeps_score(client, mock_fetch_pokemon):
    client.get("/")
    with client.session_transaction() as sess:
        sess["score"] = 4
        sess["revealed"] = True

    resp = client.post("/next")

    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess["revealed"] is False
        assert sess["score"] == 4
