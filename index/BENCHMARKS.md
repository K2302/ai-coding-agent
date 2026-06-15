# Build Index Benchmarks

## Test 1: `~/Setup17/altrecruitrpservice/`
**Date:** 7 June 2026  
**Java files:** 558  
**Classes:** 537  
**Methods:** 10,148  
**Entry points:** 674  
**SQL queries:** 93  
**Graph nodes:** 11,193  
**Graph edges:** 22,159  

| Step | Time |
|------|-----:|
| `build_graph` | 0.001s |
| `entrypoints_jsp` | 0.050s |
| `entrypoints_xml` | 0.027s |
| `file_metadata` | 0.106s |
| `git_log` | 0.018s |
| `parse_java` | 32.207s |
| `write_git` | 0.006s |
| `write_json` | 0.566s |
| **TOTAL** | **32.981s** (script: 33.11s) |

---

## Test 2: `~/Setup17/altcommon`
**Date:** 7 June 2026  
**Java files:** 8,921  
**Classes:** 9,176  
**Methods:** 228,050  
**Entry points:** 29,630  
**SQL queries:** 2,345  
**Graph nodes:** 246,635  
**Graph edges:** 283,752  

| Step | Time |
|------|-----:|
| `build_graph` | 0.040s |
| `entrypoints_jsp` | 0.634s |
| `entrypoints_xml` | 0.380s |
| `file_metadata` | 1.284s |
| `git_log` | 0.033s |
| `parse_java` | 364.665s |
| `write_git` | 0.005s |
| `write_json` | 8.459s |
| **TOTAL** | **375.501s** (script: 377.85s) |

---

## Observations

- **`parse_java`** is the dominant bottleneck (~97% of total time). It scales roughly linearly with file count.
- **`write_json`** is the second most expensive step, driven by serializing large graph structures to disk.
- All other steps (`build_graph`, `entrypoints_*`, `git_log`, `write_git`, `file_metadata`) are negligible (< 1.5s even for 9k files).