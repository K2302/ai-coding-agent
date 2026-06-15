# Performance Optimizations — `build_index.py`

Below are the optimizations applied to `build_index.py` to handle ~200k Java files faster.

---

## 1. Single-Pass AST Traversal

**Before:** Separate `tree.filter(javalang.tree.ClassDeclaration)` and multiple `type_node.filter(javalang.tree.MethodDeclaration)` calls per class — each `filter()` walks the entire AST subtree.

**After:** A single `for type_path, type_node in tree:` loop collects everything in one pass. Method declarations are gathered once per class via `list(type_node.filter(...))` and reused across all sections (metadata, SQL, entry points).

**Impact:** Eliminates redundant AST walks. For a file with N classes each having M methods, this saves ~(N × 2) full-subtree traversals.

---

## 2. Pre-computed Annotation Name Sets

**Before:** Repeated `hasattr(node, 'annotations')` checks and list membership tests (`"GetMapping" in [a.name for a in node.annotations]`).

**After:** `_get_annot_names(node)` returns a `set()` for O(1) membership tests. All annotation lookups use set intersection (`&`) or `in` checks.

**Impact:** O(n) → O(1) per annotation check. Each class and method benefits from this.

---

## 3. Pre-computed SQL Keyword Check (Per-File)

**Before:** Inside the per-method loop:
```python
if "@Query" in code or "jdbcTemplate" in code or "SELECT" in code_upper or "INSERT" in code_upper:
```
This ran for **every method** in a file, repeatedly scanning the entire file string.

**After:** Computed once per file before entering the method loop:
```python
has_sql_file = "@Query" in code or "jdbcTemplate" in code or "SELECT" in code_upper or "INSERT" in code_upper
```
Methods just check `if has_sql_file:` — a single boolean test.

**Impact:** For a file with 100 methods, saves ~99 redundant string scans of the full source code.

---

## 4. Deduplicated SQL USES Edges

**Before:** Every method that matched a SQL table added a duplicate `USES` edge and `sql_list` entry for the same class+table pair.

**After:** A `seen_tables` set `(class_node_id, table_name)` prevents duplicate entries. Only the first method in a class to reference a table creates the edge and SQL entry.

**Impact:** Eliminates O(methods × tables) duplicate edges. For classes where 20 methods all reference the same `applicant` table, saves 19 redundant edges and SQL entries.

---

## 5. Fixed TABLE Node Files-List Bug

**Before:** The post-processing loop overwrote the `files` list for each table:
```python
nodes_dict[table_id] = {"type":"TABLE", "name":sql_item['table'], "files":[sql_item['file']]}
```
If two different files referenced `TABLE:applicant`, only the last file was kept.

**After:** Merges instead of overwrites:
```python
if table_id not in nodes_dict:
    nodes_dict[table_id] = {"type":"TABLE", "name":sql_item['table'], "files":[]}
if sql_item['file'] not in f_list:
    f_list.append(sql_item['file'])
```

**Impact:** Data correctness fix — all files referencing a table are now preserved.

---

## 6. Pre-compiled Regex

**Before:** `re.compile(...)` inside a helper function or inline.

**After:** `SQL_TABLE_RE = re.compile(r"(?:FROM|INTO|UPDATE)\s+(\w+)", re.IGNORECASE)` is compiled once at module level.

**Impact:** Avoids recompilation overhead on every file.

---

## Summary

| Optimization | Fixes | Token Cost |
|---|---|---|
| Single-pass traversal | Redundant AST walks | Low |
| Annotation sets | O(n) → O(1) lookups | Low |
| Pre-computed SQL flag | Redundant string scans × methods | Low |
| Dedup SQL edges | Duplicate edges/entries | Low |
| TABLE node merge | Data loss bug | Low |
| Pre-compiled regex | Recompilation per file | Negligible |

**Next-level speedups** (not yet applied, would cost more tokens):
- `multiprocessing.Pool` — parallelize across CPU cores
- ~~`concurrent.futures.ProcessPoolExecutor` — I/O + CPU parallelism~~ ✅ **Applied below**
- `mmap` + incremental parsing — skip files that haven't changed

---

## 7. ProcessPoolExecutor — Parallel Java Parsing

**Before:** Sequential `for f in repo.rglob("*.java"):` loop — each file parsed one at a time, single-threaded.

**After:** A module-level worker function `_parse_single_java(file_path_str, repo_path_str)` is submitted to a `ProcessPoolExecutor`. Each worker process independently parses a `.java` file and returns a structured dict. Results are merged back in the main process via `extend`/`update`.

**Implementation details:**
- Worker function re-imports `javalang`/`re` internally (required for pickling across processes on Linux).
- Global constants are duplicated with a `_G` suffix (e.g. `SPRING_ENDPOINT_ANNOT_G`) so worker processes can access them.
- `max_workers=None` lets the executor use all available CPU cores.

**Benchmark — `altcommon` (8,921 Java files, 228k methods):**

| Metric | Before (Sequential) | After (ProcessPoolExecutor) | Speedup |
|---|---|---|---|
| `parse_java` time | 364.7s | 21.9s | **~16.6×** |
| Total build time | 375.5s | 26.7s | **~14.1×** |
| Java files/sec | ~24.5 files/s | ~406.5 files/s | **~16.6×** |

**Impact:** Near-linear speedup proportional to CPU core count. On a machine with enough cores, the `parse_java` bottleneck is reduced from ~97% of runtime to ~82%, and the total build time drops from ~6.3 minutes to ~27 seconds.



# Build Index Benchmarks

## altrecruitrpservice (558 java files)
- TOTAL: 32.98s | Script: 33.11s
- parse_java: 32.2s (~97% of total)
- write_json: 0.57s
- Others: < 0.11s each

## altcommon (8,921 java files, 228k methods)
- TOTAL: 375.5s (~6.3 min) | Script: 377.85s
- parse_java: 364.7s (~97%)
- write_json: 8.46s
- Others: < 1.3s each

## Key insight
`parse_java` (javalang AST parsing + annotation walking) is the dominant bottleneck at ~97% of runtime.
## Implementation note
- `parse_java` now uses `ProcessPoolExecutor` for parallel Java parsing via `_parse_single_java` worker function
- Worker function re-imports `javalang`/`re` inside (required for pickling across processes)
- Global constants for the worker are prefixed with `_G` suffix (e.g. `SPRING_ENDPOINT_ANNOT_G`)
- Results are merged back via `extend`/`update` in `as_completed` order
