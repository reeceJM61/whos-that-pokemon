import io
import os
import sys

import pytest
from PIL import Image

SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC_DIR)

os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key")

import app as app_module  # noqa: E402


def make_png_bytes(size=(50, 50), color=(255, 0, 0, 255)):
    img = Image.new("RGBA", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def clear_pokemon_cache():
    app_module.fetch_pokemon.cache_clear()
    yield
    app_module.fetch_pokemon.cache_clear()


@pytest.fixture
def client():
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def mock_fetch_pokemon(monkeypatch):
    """Stubs fetch_pokemon so tests never hit the real PokéAPI."""
    sprite_bytes = make_png_bytes()

    def _fake_fetch(dex_id):
        return "Bulbasaur", sprite_bytes

    monkeypatch.setattr(app_module, "fetch_pokemon", _fake_fetch)
    return "bulbasaur", sprite_bytes
