"""Standalone tests for the per-view routing model."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).parent
PACKAGE_ROOT = ROOT / "custom_components" / "assist_router"

package = types.ModuleType("custom_components.assist_router")
package.__path__ = [str(PACKAGE_ROOT)]
sys.modules["custom_components.assist_router"] = package

for module_name in ("routing", "view_routing"):
    path = PACKAGE_ROOT / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"custom_components.assist_router.{module_name}", path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

view_routing = sys.modules["custom_components.assist_router.view_routing"]

settings = view_routing.view_defaults()

# The final response takes priority.
match = view_routing.match_view(
    "Está nublado y hay probabilidad de lluvia",
    "Decime cómo está afuera",
    settings,
)
assert match and match.slug == "weather"
assert "lluvia" in match.response_hits

# Terse responses fall back to the original STT request.
match = view_routing.match_view(
    "Listo",
    "Prendé la luz del living",
    settings,
)
assert match and match.slug == "domotics"
assert "luz" in match.request_hits

# Disabled optional views do not steal a match.
match = view_routing.match_view(
    "La calefacción quedó en 22 grados",
    "Subí la calefacción",
    settings,
)
assert match is None
settings["view_climate_enabled"] = True
match = view_routing.match_view(
    "La calefacción quedó en 22 grados",
    "Subí la calefacción",
    settings,
)
assert match and match.slug == "climate"

# Relative paths use the actual dashboard base advertised by the satellite.
class State:
    attributes = {"dashboard": "/panel-cocina"}

assert view_routing.resolve_view_path("weather", State()) == "/panel-cocina/weather"
assert (
    view_routing.resolve_view_path("/view-assist/camera", State())
    == "/view-assist/camera"
)

class HomeState:
    attributes = {"home_screen": "/mi-dashboard/clock"}

assert view_routing.resolve_view_path("music", HomeState()) == "/mi-dashboard/music"

# Legacy 0.1.x combined rules are migrated into the separate fields.
legacy = {
    "view_rules": "clima|/custom/weather|lluvia, nublado\n"
    "domotica|/custom/intent|luz, encendida",
    "openclaw_view_path": "/custom/info",
}
migrated = view_routing.apply_legacy_view_settings(legacy)
assert migrated["view_weather_path"] == "/custom/weather"
assert "lluvia" in migrated["view_weather_keywords"]
assert migrated["view_openclaw_path"] == "/custom/info"

print("Per-view routing tests: OK")
