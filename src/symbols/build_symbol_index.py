import json, sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"

# Class annotation → symbol type mapping
ANNOT_TYPE_MAP = {
    "@Controller": "CONTROLLER",
    "@RestController": "CONTROLLER",
    "@Service": "SERVICE",
    "@Repository": "REPOSITORY",
}


def _infer_class_type(class_entry):
    annotations = class_entry.get("annotations", [])
    for ann in annotations:
        t = ANNOT_TYPE_MAP.get(ann)
        if t:
            return t
    name = class_entry["class_name"]
    if name.endswith("Controller"):
        return "CONTROLLER"
    if name.endswith("Service"):
        return "SERVICE"
    if name.endswith("Repository") or name.endswith("DAO") or name.endswith("Dao"):
        return "REPOSITORY"
    return "CLASS"


def build_symbol_index():
    with open(DATA_DIR / "classes.json") as f:
        classes = json.load(f)
    with open(DATA_DIR / "methods.json") as f:
        methods = json.load(f)

    symbols = []
    class_pkg_map = {}  # class_name -> package
    class_file_map = {}  # class_name -> file

    for c in classes:
        pkg = c.get("package", "")
        cn = c["class_name"]
        f = c["file"]
        class_pkg_map[cn] = pkg
        class_file_map[cn] = f

        sym_type = _infer_class_type(c)
        qualified = f"{pkg}.{cn}" if pkg else cn
        symbols.append({
            "symbol_id": qualified,
            "symbol_name": cn,
            "qualified_name": qualified,
            "type": sym_type,
            "file": f,
            "line": 1,
        })

    for m in methods:
        cn = m["class"]
        mn = m["method"]
        pkg = class_pkg_map.get(cn, "")
        f = m.get("file", class_file_map.get(cn, ""))
        qualified = f"{pkg}.{cn}.{mn}" if pkg else f"{cn}.{mn}"
        symbols.append({
            "symbol_id": qualified,
            "symbol_name": mn,
            "qualified_name": qualified,
            "type": "METHOD",
            "file": f,
            "line": m.get("start_line", 1),
        })

    # Write symbols.json
    with open(DATA_DIR / "symbols.json", "w") as fp:
        json.dump(symbols, fp, indent=2)
    print(f"Written {len(symbols)} symbols to data/symbols.json")

    # Build lookup maps
    name_map = {}
    qualified_map = {}
    file_map = {}

    for sym in symbols:
        name = sym["symbol_name"]
        name_map.setdefault(name, []).append(sym)
        qualified_map[sym["qualified_name"]] = sym
        file_map.setdefault(sym["file"], []).append(sym)

    index = {
        "by_name": name_map,
        "by_qualified": qualified_map,
        "by_file": file_map,
    }

    with open(DATA_DIR / "symbol_index.json", "w") as fp:
        json.dump(index, fp, indent=2)
    print(f"Written symbol index to data/symbol_index.json")
    print(f"  {len(name_map)} unique symbol names")
    print(f"  {len(qualified_map)} qualified names")
    print(f"  {len(file_map)} files")


if __name__ == "__main__":
    build_symbol_index()