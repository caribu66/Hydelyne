"""Test AI search capabilities with 50 natural language queries."""

import asyncio
import time

from app.database import get_session_factory
from app.services.crew_query import crew_query_service

QUERIES = [
    # Certification searches (1-10)
    "Find crew with BOSIET certification",
    "Who has STCW certification",
    "Show me crew with OGUK Medical",
    "List all crew with GWO Wind certification",
    "Find specialists with NEBOSH Diploma",
    "Who has IHO Cat A Hydrographer",
    "Show crew with IMCA Survey QC",
    "Find people with PAMGUARD Advanced",
    "List crew members with EOD Level 3",
    "Who holds JNCC MMO certification",
    # Availability searches (11-20)
    "Who is available immediately",
    "Show me available crew members",
    "Find crew who are on assignment",
    "List unavailable specialists",
    "Who can start work next week",
    "Show crew available for offshore work",
    "Find specialists who are not working",
    "Who is ready to mobilize",
    "Show me crew with immediate availability",
    "Find available hydrographers",
    # Experience-based searches (21-30)
    "Who has experience in offshore wind",
    "Find crew with 5 years experience",
    "Show me specialists with 10+ years experience",
    "Who has experience in seismic surveys",
    "Find crew with marine experience",
    "Show people with UXO experience",
    "Who has subsea experience",
    "Find crew with geotechnical experience",
    "Show me experienced HSE advisors",
    "Who has offshore construction experience",
    # Role/specialty searches (31-40)
    "Find hydrographers",
    "Show me marine mammal observers",
    "Who are the HSE advisors",
    "Find client representatives",
    "Show me survey QC specialists",
    "Who are the geophysical reps",
    "Find MMO certified crew",
    "Show me ROV operators",
    "Who are the safety advisors",
    "Find environmental specialists",
    # Compliance searches (41-45)
    "Who has expired certifications",
    "Show crew with expired medicals",
    "Find people with expiring BOSIET",
    "Who needs to renew their certification",
    "Show me non-compliant crew members",
    # Complex/mixed searches (46-50)
    "Find available crew with BOSIET and OGUK Medical",
    "Who has experience in marine surveys and is available",
    "Show me hydrographers with 5+ years experience",
    "Find crew with STCW certification who are available",
    "Show experienced HSE advisors with NEBOSH",
]


async def run_tests():
    factory = get_session_factory()
    results = []
    total_time = 0

    print("=" * 80)
    print("AI SEARCH CAPABILITY TEST - 50 NATURAL LANGUAGE QUERIES")
    print("=" * 80)
    print()

    async with factory() as session:
        for i, query in enumerate(QUERIES, 1):
            start = time.time()
            try:
                result = await crew_query_service.process_query(query, session)
                elapsed = time.time() - start
                total_time += elapsed

                intent = result.get("intent", "unknown")
                summary = result.get("summary", "")
                result_count = len(result.get("results", []))

                results.append(
                    {
                        "query": query,
                        "intent": intent,
                        "results": result_count,
                        "time": elapsed,
                        "success": True,
                    }
                )

                status = "OK" if result_count > 0 else "EMPTY"
                print(
                    f"[{i:2d}] {status} | {intent:12s} | {result_count:2d} results | {elapsed:.2f}s"
                )
                print(f"     Q: {query}")
                if summary:
                    print(f"     A: {summary[:100]}...")
                print()

            except Exception as e:
                elapsed = time.time() - start
                total_time += elapsed
                results.append(
                    {
                        "query": query,
                        "intent": "ERROR",
                        "results": 0,
                        "time": elapsed,
                        "success": False,
                        "error": str(e),
                    }
                )
                print(f"[{i:2d}] ERROR | {elapsed:.2f}s")
                print(f"     Q: {query}")
                print(f"     E: {str(e)[:100]}")
                print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    successful = sum(1 for r in results if r["success"])
    with_results = sum(1 for r in results if r["results"] > 0)
    avg_time = total_time / len(results) if results else 0

    print(f"Total queries:      {len(results)}")
    print(f"Successful:         {successful}")
    print(f"With results:       {with_results}")
    print(f"Errors:             {len(results) - successful}")
    print(f"Total time:         {total_time:.2f}s")
    print(f"Average time:       {avg_time:.2f}s")
    print()

    # Intent breakdown
    intents = {}
    for r in results:
        intent = r["intent"]
        intents[intent] = intents.get(intent, 0) + 1

    print("Intent breakdown:")
    for intent, count in sorted(intents.items(), key=lambda x: -x[1]):
        print(f"  {intent:15s}: {count}")

    # Result distribution
    print()
    print("Result distribution:")
    ranges = [(0, 0), (1, 5), (6, 10), (11, 20)]
    for low, high in ranges:
        count = sum(1 for r in results if low <= r["results"] <= high)
        label = f"{low}-{high}" if low > 0 else "0"
        print(f"  {label:8s} results: {count}")

    return results


if __name__ == "__main__":
    asyncio.run(run_tests())
