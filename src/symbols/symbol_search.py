import json, sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def load_index():
    with open(DATA_DIR / "symbol_index.json") as f:
        return json.load(f)


def search_symbols(query, limit=20):
    index = load_index()
    query_lower = query.lower().strip()
    tokens = [t for t in query_lower.replace(".", " ").replace("/", " ").split() if len(t) > 1]
    results = []

    for sym_list in index["by_name"].values():
        for sym in sym_list:
            name = sym["symbol_name"]
            name_lower = name.lower()

            if name_lower == query_lower:
                results.append((0, sym))  # exact match
            elif query_lower and name_lower.startswith(query_lower):
                results.append((1, sym))  # prefix match (full query)
            elif query_lower and query_lower in name_lower:
                results.append((2, sym))  # substring match (full query)
            else:
                # Multi-token: any word from query matches this symbol
                for tok in tokens:
                    if tok == name_lower:
                        results.append((1, sym))
                        break
                    if name_lower.startswith(tok):
                        results.append((2, sym))
                        break
                    if tok in name_lower:
                        results.append((3, sym))
                        break

    results.sort(key=lambda x: (x[0], x[1]["symbol_name"]))
    return [sym for _, sym in results[:limit]]


def main():
    if len(sys.argv) < 2:
        print("Usage: python symbol_search.py <query> [limit]")
        sys.exit(1)
    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    results = search_symbols(query, limit)
    print(f"Found {len(results)} symbols for '{query}':")
    print()
    for r in results:
        print(f"  {r['symbol_name']:40s} {r['type']:12s} {r['file']}")
        print(f"  {'':40s} {r['qualified_name']}")
        print()


if __name__ == "__main__":
    main()