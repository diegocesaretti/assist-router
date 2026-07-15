"""Standalone tests for response-to-view classification."""

import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).parent
PACKAGE_ROOT = ROOT / "custom_components" / "assist_router"

# Load the package modules without importing Home Assistant.
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

a = sys.modules["custom_components.assist_router.view_routing"]

rules = """clima|/view-assist/weather|clima, lluvia, nublado
termostato|/view-assist/thermostat|aire, calefacción, termostato
domotica|/view-assist/intent|luz, persiana, encendida, apagada"""

match = a.match_view_rule("Está nublado y puede llover", rules)
assert match and match.category == "clima"
assert match.path == "/view-assist/weather"

match = a.match_view_rule("Dejé la luz encendida", rules)
assert match and match.category == "domotica"

match = a.match_view_rule("Encendí la calefaccion", rules)
assert match and match.category == "termostato"

assert a.match_view_rule("Listo, tarea completada", rules) is None

canonical = a.canonicalize_view_rules(rules)
assert "calefaccion" in canonical

try:
    a.parse_view_rules("regla sin separadores")
except ValueError:
    pass
else:
    raise AssertionError("Invalid rules should raise ValueError")

print("View routing tests: OK")
