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

fixed_sections = ("routing", "general", "conversation", "openclaw", "view_assist")
for section in fixed_sections:
    edit_step = f"edit_{section}"
    assert section in menu
    section_menu = strings["options"]["step"][section]["menu_options"]
    assert edit_step in section_menu
    assert "init" in section_menu
    assert edit_step in strings["options"]["step"]
    assert edit_step in translations["options"]["step"]

for definition in view_routing.VIEW_DEFINITIONS:
    step = f"view_{definition.slug}"
    edit_step = f"edit_view_{definition.slug}"
    assert step in menu
    section_menu = strings["options"]["step"][step]["menu_options"]
    assert edit_step in section_menu
    assert "init" in section_menu
    assert edit_step in strings["options"]["step"]
    assert edit_step in translations["options"]["step"]
    data = strings["options"]["step"][edit_step]["data"]
    assert definition.enabled_key in data
    assert definition.path_key in data
    assert definition.keywords_key in data
    assert "_make_view_menu_step" in source
    assert "_make_view_edit_step" in source

routing = strings["options"]["step"]["edit_routing"]["data"]
assert "general_agent" in routing
assert "end_phrases" in strings["options"]["step"]["edit_conversation"]["data"]
assert "general_router_instruction" in strings["options"]["step"]["edit_general"]["data"]
assert "force_openclaw_phrases" in strings["options"]["step"]["edit_general"]["data"]
assert "view_rules" not in menu

general = strings["options"]["step"]["edit_view_assist"]["data"]
assert "view_response_enabled" in general
assert "view_response_path" in general
assert "view_response_min_time" in general
assert "view_response_seconds_per_word" in general
assert "view_response_max_time" in general
assert "view_related_display_time" in general
assert "categoria | /ruta | palabras" not in json.dumps(strings, ensure_ascii=False)

print("Configuration structure tests: OK")
