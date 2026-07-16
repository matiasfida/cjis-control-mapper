import sys

from check_event import find_candidate_controls
from eval_set import EVAL_CASES

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

K = 5


def run_case(case: dict) -> dict:
    hits = find_candidate_controls(case["event"], k=K)
    rank = None
    for i, hit in enumerate(hits, start=1):
        if hit["section"] == case["expected_control"]:
            rank = i
            break
    return {
        "id": case["id"],
        "expected_control": case["expected_control"],
        "expected_page": case["expected_page"],
        "hit": rank is not None,
        "rank": rank,
        "top_hit": hits[0] if hits else None,
    }


def run_eval() -> list[dict]:
    return [run_case(case) for case in EVAL_CASES]


if __name__ == "__main__":
    results = run_eval()

    print(f"=== Eval set: {len(results)} casos, k={K} ===\n")
    for r in results:
        mark = "OK" if r["hit"] else "MISS"
        rank_info = f"rank={r['rank']}" if r["hit"] else "no encontrado en top-k"
        print(f"[{mark}] {r['id']}: esperado {r['expected_control']} (pág. {r['expected_page']}) -> {rank_info}")
        if not r["hit"] and r["top_hit"]:
            top = r["top_hit"]
            print(f"       top hit real: sección={top['section']}, página={top['page']}, score={top['relevance_score']}")

    hits = sum(1 for r in results if r["hit"])
    total = len(results)
    hit_rate = 100 * hits / total
    mrr = sum(1 / r["rank"] for r in results if r["hit"]) / total

    print(f"\nHit@{K}: {hits}/{total} ({hit_rate:.0f}%)")
    print(f"MRR: {mrr:.2f}")
    print(
        "\nNota: esto mide calidad de retrieval, no compliance. Los misses esperables "
        "caen en el borde entre secciones/controles consecutivos (ver limitación conocida en CLAUDE.md)."
    )