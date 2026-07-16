"""Small standalone smoke test for routing helpers."""

import importlib.util
from pathlib import Path

path = Path(__file__).parent / "custom_components" / "assist_router" / "routing.py"
spec = importlib.util.spec_from_file_location("assist_router_routing", path)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

keywords = "luz\naire\ncalefacción\nportón"
assert module.matches_domotics("Prendé la LUZ del living", keywords)
assert module.matches_domotics("Abrí el porton", keywords)
assert module.matches_domotics("Encendé la calefaccion", keywords)
assert not module.matches_domotics("Revisame los correos", keywords)
assert not module.matches_domotics("Buscá información sobre trasluz", keywords)
print("Routing smoke tests: OK")

legacy_default = "luz\nluces\naire"
current_default = "luz\nluces\naire\nclima"
assert module.migrate_default_keywords(
    legacy_default, legacy_default, current_default
) == module.canonicalize_keywords(current_default)
assert module.migrate_default_keywords(
    "luz\npersonalizada", legacy_default, current_default
) == "luz\npersonalizada"
