import io
import sys
import json
from pathlib import Path

# Ensure UTF-8 output on Windows console
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")
if isinstance(sys.stderr, io.TextIOWrapper):
    sys.stderr.reconfigure(encoding="utf-8")

# Add src to python path
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from sahibhav_ai.intent_extractor import IntentExtractor

def test_queries():
    extractor = IntentExtractor()
    sample_queries = [
        # Valid grocery cases
        "mujhe doodh aur atta chahiye",
        "2 packet amul toned milk, 5kg aashirvaad select atta aur 1 pack butter jaldi chahiye",
        "aadha kilo paneer aur 250 gm dahi",
        "मुझे 2 पैकेट दूध और 1 किलो चीनी चाहिए",

        # Guardrail test 1: Coding request (Must be rejected)
        "write a python script to reverse a string and sort a list",

        # Guardrail test 2: General Knowledge / Trivia (Must be rejected)
        "who is the prime minister of india and what is the capital of France?",

        # Guardrail test 3: Mixed request (Grocery + off-topic coding request)
        "mujhe 2 packet doodh chahiye aur write a python loop for factorial"
    ]

    print("=" * 65)
    print("Testing SahiBhav AI Intent Extractor (With Guardrails & LangChain)")
    print("=" * 65)

    for i, query in enumerate(sample_queries, 1):
        print(f"\n[Test {i}] User Query: \"{query}\"")
        result = extractor.extract_intent(query)
        print("Structured Result:")
        print(result.model_dump_json(indent=2))
        print("-" * 55)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        custom_query = " ".join(sys.argv[1:])
        extractor = IntentExtractor()
        result = extractor.extract_intent(custom_query)
        print(result.model_dump_json(indent=2))
    else:
        test_queries()
