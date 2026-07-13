from datetime import datetime, timezone

from dotenv import load_dotenv
from langchain.agents import create_agent

from retrieval import search_cjis_policy

load_dotenv()

MODEL = "groq:llama-3.3-70b-versatile"

SYSTEM_PROMPT = """Sos un asistente que mapea eventos de auditoría a controles del \
CJIS Security Policy v6.0 usando la tool search_cjis_policy.

Reglas estrictas:
- NUNCA afirmes que un evento "cumple" o "no cumple" con un control. Tu única \
tarea es identificar qué controles podrían ser relevantes para el evento y citar \
su fuente exacta (sección y página).
- Toda afirmación sobre un control debe estar respaldada por un resultado de \
search_cjis_policy. No completes con conocimiento propio del modelo sobre CJIS.
- Si no encontrás evidencia suficiente en los resultados de la tool para vincular \
el evento a un control específico, decilo explícitamente en vez de adivinar.
- Citá siempre sección/control ID y página de cada control que menciones.
"""

agent = create_agent(model=MODEL, tools=[search_cjis_policy], system_prompt=SYSTEM_PROMPT)


def describe_event(event: dict) -> str:
    # timestamp asumido epoch millis, convención habitual en pipelines Avro/Kafka
    when = datetime.fromtimestamp(event["timestamp"] / 1000, tz=timezone.utc).isoformat()
    resource = event.get("resource") or "(sin recurso asociado)"
    return (
        f"Evento de auditoría:\n"
        f"- eventId: {event['eventId']}\n"
        f"- userId: {event['userId']}\n"
        f"- action: {event['action']}\n"
        f"- resource: {resource}\n"
        f"- timestamp: {when}\n\n"
        f"¿Qué controles del CJIS Security Policy v6.0 podrían aplicar a este evento?"
    )


def map_event_to_controls(event: dict) -> dict:
    """Analiza un evento de AuditEvent (schema Avro) y devuelve los controles que el agente considera relevantes, con cita."""
    result = agent.invoke({"messages": [{"role": "user", "content": describe_event(event)}]})
    final_message = result["messages"][-1]
    return {
        "eventId": event["eventId"],
        "analysis": final_message.content,
    }


if __name__ == "__main__":
    sample_event = {
        "eventId": "evt-001",
        "userId": "jdoe",
        "action": "LOGIN_FAILED",
        "timestamp": 1752400000000,
        "resource": None,
    }
    output = map_event_to_controls(sample_event)
    print(f"=== Evento {output['eventId']} ===")
    print(output["analysis"])
