import json, sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def load_index():
    with open(DATA_DIR / "symbol_index.json") as f:
        return json.load(f)


def find_definition(qualified_name):
    index = load_index()
    sym = index["by_qualified"].get(qualified_name)
    if sym:
        return {"file": sym["file"], "line": sym["line"]}
    return None


def find_symbols_in_file(file_path):
    index = load_index()
    return index["by_file"].get(file_path, [])


def find_symbol_by_name(symbol_name):
    index = load_index()
    return index["by_name"].get(symbol_name, [])


def main():
    if len(sys.argv) < 2:
        print("Usage: python symbol_navigation.py <qualified_name>")
        print("  e.g. python symbol_navigation.py com.company.service.ApplicantService.generateDeepLink")
        sys.exit(1)
    qname = sys.argv[1]
    result = find_definition(qname)
    if result:
        print(f"Definition: {result['file']}:{result['line']}")
    else:
        print(f"Symbol not found: {qname}")
        sys.exit(1)


if __name__ == "__main__":
    main()