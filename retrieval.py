from langchain_chroma import Chroma

COLLECTION_NAME = "cjis_security_policy_v6"
PERSIST_DIR = "./chroma_db"


def get_vectorstore() -> Chroma:
    return Chroma(persist_directory=PERSIST_DIR, collection_name=COLLECTION_NAME)


def search_cjis_policy(query: str, k: int = 4) -> list[dict]:
    """
    Busca en el CJIS Security Policy v6.0 y devuelve los fragmentos más relevantes
    con su cita (página y sección, cuando esté disponible).
    """
    vectorstore = get_vectorstore()
    results = vectorstore.similarity_search_with_score(query, k=k)

    hits = []
    for doc, score in results:
        hits.append({
            "text": doc.page_content,
            "page": doc.metadata.get("page"),
            "section": doc.metadata.get("section"),
            "relevance_score": round(float(score), 4),
        })
    return hits


if __name__ == "__main__":
    # Prueba manual rápida — corré esto directo para validar antes de conectar el agente
    test_queries = [
        "audit record content requirements",
        "password complexity requirements",
        "incident response reporting",
    ]
    for q in test_queries:
        print(f"\n=== Query: {q!r} ===")
        for hit in search_cjis_policy(q, k=2):
            print(f"  página {hit['page']}, sección {hit['section']}, score={hit['relevance_score']}")
            print(f"  {hit['text'][:150]}...")