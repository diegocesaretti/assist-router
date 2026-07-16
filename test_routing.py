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

closing = "chau\ngracias\nok\nbueno\nhasta luego"
assert module.matches_end_phrase("¡Chau!", closing)
assert module.matches_end_phrase("Hasta luego", closing)
assert not module.matches_end_phrase("Bueno, prendé la luz", closing)
assert not module.matches_end_phrase("Gracias por apagar la luz", closing)
assert module.canonicalize_phrases("Chau; Hasta luego") == "chau\nhasta luego"

forced = "openclaw\npor whatsapp\nmis archivos\nen mi pc"
assert module.matches_phrase_in_text("Usá OpenClaw para revisar esto", forced)
assert module.matches_phrase_in_text("Mandámelo por WhatsApp cuando termines", forced)
assert module.matches_phrase_in_text("Buscá esto en mi PC", forced)
assert not module.matches_phrase_in_text("¿Qué es una computadora personal?", forced)
