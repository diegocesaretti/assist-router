"""Static checks for the multi-page options configuration."""

from __future__ import annotations

import importlib.util
import json
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
strings = json.loads((PACKAGE_ROOT / "strings.json").read_text())
translations = json.loads((PACKAGE_ROOT / "translations" / "es.json").read_text())

menu = strings["options"]["step"]["init"]["menu_options"]
source = (PACKAGE_ROOT / "config_flow.py").read_text()

for definition in view_routing.VIEW_DEFINITIONS:
    step = f"view_{definition.slug}"
    assert step in menu
    assert step in strings["options"]["step"]
    assert step in translations["options"]["step"]
    data = strings["options"]["step"][step]["data"]
    assert definition.enabled_key in data
    assert definition.path_key in data
    assert definition.keywords_key in data
    assert f'async_step_view_{definition.slug}' in source or "_make_view_step" in source

assert "conversation" in menu
assert "conversation" in strings["options"]["step"]
assert "end_phrases" in strings["options"]["step"]["conversation"]["data"]
assert "view_rules" not in menu
assert "categoria | /ruta | palabras" not in json.dumps(strings, ensure_ascii=False)

print("Configuration structure tests: OK")
