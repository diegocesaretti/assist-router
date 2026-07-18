"""Standalone tests for deterministic Stremio voice parsing."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).parent
path = ROOT / "custom_components" / "assist_router" / "stremio.py"
spec = importlib.util.spec_from_file_location("assist_router_stremio", path)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)

aliases = module.parse_tv_aliases(
    "living, sala principal = media_player.tv_living\n"
    "dormitorio, pieza = media_player.tv_dormitorio\n"
    "quincho = media_player.tv_quincho"
)
assert aliases["living"] == "media_player.tv_living"
assert aliases["sala principal"] == "media_player.tv_living"

movie = module.parse_stremio_request(
    "Poné Matrix en la tele del living", aliases=aliases
)
assert movie is not None
assert movie.query == "Matrix"
assert movie.media_type == "all"
assert movie.media_player == "media_player.tv_living"
assert movie.target_label == "living"
assert movie.strong is False

latin = module.parse_stremio_request(
    "Poné la película Dune de 2021 en latino en la tele",
    aliases=aliases,
)
assert latin is not None
assert latin.query == "Dune"
assert latin.media_type == "movie"
assert latin.profile == "latin"
assert latin.year == 2021
assert latin.disable_subtitles is True

series = module.parse_stremio_request(
    "Poné Breaking Bad temporada dos capítulo tres en la pieza",
    aliases=aliases,
)
assert series is not None
assert series.query == "Breaking Bad"
assert series.media_type == "series"
assert series.season == 2
assert series.episode == 3
assert series.media_player == "media_player.tv_dormitorio"

reversed_episode = module.parse_stremio_request(
    "Poné Breaking Bad segunda temporada tercer capítulo en la pieza",
    aliases=aliases,
)
assert reversed_episode is not None
assert reversed_episode.season == 2
assert reversed_episode.episode == 3

numbered_title = module.parse_stremio_request(
    "Poné la película 2001 odisea del espacio en la tele",
    aliases=aliases,
)
assert numbered_title is not None
assert numbered_title.query == "2001 odisea del espacio"
assert numbered_title.year is None

room_only = module.parse_stremio_request(
    "Poné Matrix en el quincho", aliases=aliases
)
assert room_only is not None
assert room_only.query == "Matrix"
assert room_only.media_player == "media_player.tv_quincho"

assert module.parse_stremio_request("Prendé el aire a 22", aliases=aliases) is None
assert module.parse_stremio_request("Apagá la tele", aliases=aliases) is None
assert module.parse_stremio_request("Poné la tele", aliases=aliases) is None
assert (
    module.parse_stremio_request(
        "¿Quién actuó en la película Matrix?", aliases=aliases
    )
    is None
)

weak_music = module.parse_stremio_request(
    "Poné Calamaro en la tele", aliases=aliases
)
assert weak_music is not None
assert weak_music.query == "Calamaro"
assert weak_music.strong is False

natural_default = module.parse_stremio_request(
    "Quiero ver Matrix", aliases=aliases, default_player="media_player.tv_living"
)
assert natural_default is not None
assert natural_default.query == "Matrix"
assert natural_default.media_player == "media_player.tv_living"

assert module.parse_follow_up_episode("temporada dos capítulo tres") == (2, 3)
assert module.parse_follow_up_episode("dos tres") == (2, 3)
assert module.parse_single_number("el tercero") == 3

results = [
    {"media_id": "old", "media_type": "movie", "title": "Dune", "year": 1984},
    {"media_id": "new", "media_type": "movie", "title": "Dune", "year": 2021},
]
assert module.select_result_from_follow_up("la segunda", results)["media_id"] == "new"
assert module.select_result_from_follow_up("la de 2021", results)["media_id"] == "new"
assert module.select_result_from_follow_up("Dune", results) is None

assert module.canonicalize_tv_aliases(
    " living,sala= media_player.tv_living \n\n pieza =media_player.tv_room"
) == (
    "living, sala = media_player.tv_living\n"
    "pieza = media_player.tv_room"
)

print("Stremio parsing tests: OK")
