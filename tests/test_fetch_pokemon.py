import app as app_module


class _FakeResponse:
    def __init__(self, json_data=None, content=b""):
        self._json_data = json_data
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


def test_fetch_pokemon_parses_english_name_and_artwork(monkeypatch):
    species_json = {
        "names": [
            {"name": "Bulbizarre", "language": {"name": "fr"}},
            {"name": "Bulbasaur", "language": {"name": "en"}},
        ]
    }
    pokemon_json = {
        "sprites": {
            "front_default": "http://example.test/fallback.png",
            "other": {"official-artwork": {"front_default": "http://example.test/art.png"}},
        }
    }
    responses = {
        app_module.POKEAPI_SPECIES_URL.format(id=1): _FakeResponse(json_data=species_json),
        app_module.POKEAPI_POKEMON_URL.format(id=1): _FakeResponse(json_data=pokemon_json),
        "http://example.test/art.png": _FakeResponse(content=b"artwork-bytes"),
    }

    def fake_get(url, timeout=10):
        return responses[url]

    monkeypatch.setattr(app_module.requests, "get", fake_get)
    app_module.fetch_pokemon.cache_clear()

    name, image_bytes = app_module.fetch_pokemon(1)

    assert name == "Bulbasaur"
    assert image_bytes == b"artwork-bytes"


def test_fetch_pokemon_falls_back_to_front_default_when_no_artwork(monkeypatch):
    species_json = {"names": [{"name": "Bulbasaur", "language": {"name": "en"}}]}
    pokemon_json = {
        "sprites": {
            "front_default": "http://example.test/fallback.png",
            "other": {"official-artwork": {"front_default": None}},
        }
    }
    responses = {
        app_module.POKEAPI_SPECIES_URL.format(id=1): _FakeResponse(json_data=species_json),
        app_module.POKEAPI_POKEMON_URL.format(id=1): _FakeResponse(json_data=pokemon_json),
        "http://example.test/fallback.png": _FakeResponse(content=b"fallback-bytes"),
    }

    def fake_get(url, timeout=10):
        return responses[url]

    monkeypatch.setattr(app_module.requests, "get", fake_get)
    app_module.fetch_pokemon.cache_clear()

    _, image_bytes = app_module.fetch_pokemon(1)

    assert image_bytes == b"fallback-bytes"


def test_fetch_pokemon_is_cached(monkeypatch):
    species_json = {"names": [{"name": "Bulbasaur", "language": {"name": "en"}}]}
    pokemon_json = {
        "sprites": {
            "front_default": None,
            "other": {"official-artwork": {"front_default": "http://example.test/art.png"}},
        }
    }
    responses = {
        app_module.POKEAPI_SPECIES_URL.format(id=1): _FakeResponse(json_data=species_json),
        app_module.POKEAPI_POKEMON_URL.format(id=1): _FakeResponse(json_data=pokemon_json),
        "http://example.test/art.png": _FakeResponse(content=b"art-bytes"),
    }
    call_count = {"n": 0}

    def fake_get(url, timeout=10):
        call_count["n"] += 1
        return responses[url]

    monkeypatch.setattr(app_module.requests, "get", fake_get)
    app_module.fetch_pokemon.cache_clear()

    app_module.fetch_pokemon(1)
    app_module.fetch_pokemon(1)

    assert call_count["n"] == 3  # species + pokemon + image, only on the first call
