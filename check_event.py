import re

from retrieval import search_cjis_policy

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _normalize_action(action: str) -> str:
    """LOGIN_FAILED / loginFailed -> "login failed", para mejorar el matching semántico contra la prosa de la política."""
    spaced = _CAMEL_BOUNDARY.sub(" ", action)
    spaced = re.sub(r"[_\-]+", " ", spaced)
    return " ".join(spaced.split()).lower()


def _describe_event_for_search(event: dict) -> str:
    parts = [f"audit log event: {_normalize_action(event.get('action', ''))}"]
    if event.get("resource"):
        parts.append(f"resource: {event['resource']}")
    return ". ".join(parts)


# Chequeos de completitud estructural: elementos de contenido de audit record citados
# textualmente de controles de la familia AU. Solo incluimos acá controles donde el texto
# fuente describe campos concretos de UN registro (verificables por evento). AU-2 queda
# afuera a propósito: define qué *tipos* de evento hay que loguear a nivel organización,
# una decisión de catálogo, no un campo chequeable en un evento individual.
CONTROL_CONTENT_CHECKS = {
    "AU-3": {
        "source_page": 69,
        "elements": [
            {"label": "descripción/tipo de evento", "present": lambda e: bool(e.get("action"))},
            {"label": "timestamp", "present": lambda e: e.get("timestamp") is not None},
            {"label": "identificador de usuario o proceso", "present": lambda e: bool(e.get("userId"))},
            {"label": "direcciones de origen/destino", "present": lambda e: False},
            {"label": "indicación de éxito/fallo", "present": lambda e: False},
            {"label": "objeto/archivo involucrado", "present": lambda e: e.get("resource") is not None},
        ],
    },
    "AU-8": {
        "source_page": 73,
        "elements": [
            {"label": "timestamp presente", "present": lambda e: e.get("timestamp") is not None},
            {
                "label": "timestamp sin ambigüedad de zona horaria (epoch/UTC)",
                "present": lambda e: isinstance(e.get("timestamp"), int),
            },
        ],
    },
}


def check_audit_record_content(event: dict) -> list[dict]:
    """Completitud estructural del evento contra cada control registrado en CONTROL_CONTENT_CHECKS.

    No es un veredicto de compliance: indica presente/ausente por campo, con la fuente
    citada, para que un humano evalúe qué implica cada ausencia.
    """
    results = []
    for control, spec in CONTROL_CONTENT_CHECKS.items():
        elements = [{"element": el["label"], "present": el["present"](event)} for el in spec["elements"]]
        results.append({"control": control, "source_page": spec["source_page"], "elements": elements})
    return results


def find_candidate_controls(event: dict, k: int = 4) -> list[dict]:
    """Controles candidatos vía búsqueda semántica sobre el texto del evento (score de similitud, no correspondencia garantizada)."""
    return search_cjis_policy(_describe_event_for_search(event), k=k)


def check_event(event: dict) -> dict:
    return {
        "eventId": event["eventId"],
        "structural_checks": check_audit_record_content(event),
        "candidate_controls": find_candidate_controls(event),
    }


if __name__ == "__main__":
    sample_event = {
        "eventId": "evt-001",
        "userId": "jdoe",
        "action": "LOGIN_FAILED",
        "timestamp": 1752400000000,
        "resource": None,
    }

    result = check_event(sample_event)

    print(f"=== Evento {result['eventId']} ===\n")

    for sc in result["structural_checks"]:
        print(f"Completitud estructural vs. {sc['control']} (página {sc['source_page']}):")
        for el in sc["elements"]:
            mark = "OK" if el["present"] else "FALTA"
            print(f"  [{mark}] {el['element']}")
        print()

    print("Controles candidatos (por similitud semántica, no garantizada):")
    for hit in result["candidate_controls"]:
        print(f"  página {hit['page']}, sección/control {hit['section']}, score={hit['relevance_score']}")
        print(f"    {hit['text'][:150]}...")
