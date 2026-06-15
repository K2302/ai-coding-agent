
import json,re,subprocess,sys,time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import javalang
import xml.etree.ElementTree as ET

START_OVERALL = time.perf_counter()
times={}

repo=Path(sys.argv[1]).resolve()
if not repo.exists():
    print(f"Error: Repository path does not exist: {repo}")
    sys.exit(1)
symbols=[]
graph=[]

# Phase 2 outputs
files_metadata=[]
classes_list=[]
methods_list=[]
entrypoints_list=[]
sql_list=[]
nodes_dict={}
edges_list=[]

# Supported file extensions
SUPPORTED_EXTENSIONS={".java",".xml",".sql",".properties",".yml"}

# Task 1: Parse Repository - Extract file metadata
t0=time.perf_counter()
for ext in SUPPORTED_EXTENSIONS:
    for f in repo.rglob(f"*{ext}"):
        try:
            size=f.stat().st_size
            files_metadata.append({
                "path":str(f.relative_to(repo)),
                "language":ext[1:],
                "size":size
            })
        except Exception:
            pass
times["file_metadata"]=time.perf_counter()-t0

# ============================================================
# Worker function for parallel Java parsing (ProcessPoolExecutor)
# ============================================================
SPRING_ENDPOINT_ANNOT_G={"RestController","Controller","GetMapping","PostMapping","PutMapping","DeleteMapping","RequestMapping"}
EJB_ANNOT_G={"Stateless","Stateful","Singleton","Local","Remote"}
SOAP_ANNOT_G={"WebService","WebMethod"}
SCHEDULER_ANNOT_G={"Schedule","Scheduled"}
MESSAGE_ANNOT_G={"MessageDriven"}
HTTP_METHOD_MAP_G={"GetMapping":"GET","PostMapping":"POST","PutMapping":"PUT","DeleteMapping":"DELETE","RequestMapping":"GET"}
_STRIP_CHARS_G=str.maketrans("","","'\"")
SQL_TABLE_RE_G=re.compile(r"(?:FROM|INTO|UPDATE)\s+(\w+)",re.IGNORECASE)

def _get_ann_value_g(ann):
    if not (hasattr(ann,'element') and ann.element):
        return ""
    if isinstance(ann.element,list):
        for e in ann.element:
            if hasattr(e,'value'):
                return str(e.value).translate(_STRIP_CHARS_G)
    elif hasattr(ann.element,'value'):
        return str(ann.element.value).translate(_STRIP_CHARS_G)
    return ""

def _get_annot_names_g(node):
    if not hasattr(node,'annotations') or not node.annotations:
        return set()
    return {a.name for a in node.annotations}

def _parse_single_java(file_path_str, repo_path_str):
    """Parse a single .java file and return structured results for merging."""
    import javalang, re
    from pathlib import Path
    results={
        "classes_list":[], "methods_list":[], "entrypoints_list":[], "sql_list":[],
        "nodes_dict":{}, "edges_list":[], "symbols_entry":{}, "graph_entries":[],
        "rel_path":"", "parse_ok":False
    }
    try:
        f=Path(file_path_str)
        repo=Path(repo_path_str)
        code=f.read_text(errors="ignore")
        tree=javalang.parse.parse(code)
        code_upper=code.upper()
        has_sql_file="@Query" in code or "jdbcTemplate" in code or "SELECT" in code_upper or "INSERT" in code_upper

        imports=[i.path for i in tree.imports]
        package_name=tree.package.name if tree.package else ""
        rel_path=str(f.relative_to(repo))
        results["rel_path"]=rel_path

        classes=[]
        methods=[]
        file_node_id=f"FILE:{rel_path}"
        results["nodes_dict"][file_node_id]={"type":"FILE","path":rel_path}
        seen_tables=set()

        for type_path,type_node in tree:
            if not isinstance(type_node,javalang.tree.ClassDeclaration):
                continue
            class_name=type_node.name
            classes.append(class_name)
            class_ann_names=_get_annot_names_g(type_node)

            results["classes_list"].append({
                "class_name":class_name,"package":package_name,
                "file":rel_path,
                "annotations":[f"@{a}" for a in class_ann_names]
            })
            class_node_id=f"CLASS:{package_name}.{class_name}"
            results["nodes_dict"][class_node_id]={
                "type":"CLASS","name":class_name,
                "package":package_name,"file":rel_path
            }

            class_methods=list(type_node.filter(javalang.tree.MethodDeclaration))

            # --- methods, SQL ---
            for _,method_node in class_methods:
                m_name=method_node.name
                methods.append(m_name)
                m_ann_names=_get_annot_names_g(method_node)

                ret_type=str(method_node.return_type) if hasattr(method_node,'return_type') and method_node.return_type else "void"
                params=[f"{str(p.type)} {p.name}" for p in method_node.parameters] if hasattr(method_node,'parameters') else []

                m_start_line=method_node.position.line if hasattr(method_node,'position') and method_node.position else 0
                body_source=""
                m_end_line=m_start_line
                calls=[]
                if m_start_line>0:
                    all_lines=code.split('\n')
                    brace_count=0
                    start_found=False
                    for i in range(m_start_line-1,len(all_lines)):
                        for ch in all_lines[i]:
                            if ch=='{':
                                brace_count+=1
                                start_found=True
                            elif ch=='}':
                                brace_count-=1
                        if start_found and brace_count==0:
                            m_end_line=i+1
                            break
                    body_source='\n'.join(all_lines[m_start_line-1:m_end_line])
                for path,node in method_node:
                    if isinstance(node,javalang.tree.MethodInvocation):
                        calls.append(node.member)

                results["methods_list"].append({
                    "method":m_name,"class":class_name,
                    "return_type":ret_type,"parameters":params,
                    "file":rel_path,"body":body_source,
                    "start_line":m_start_line,"end_line":m_end_line,
                    "calls":calls
                })
                method_node_id=f"METHOD:{package_name}.{class_name}.{m_name}"
                results["nodes_dict"][method_node_id]={
                    "type":"METHOD","name":m_name,
                    "class":class_name,"package":package_name,"file":rel_path
                }
                results["edges_list"].append({"source":class_node_id,"target":method_node_id,"type":"CONTAINS"})

                if has_sql_file:
                    m_start=method_node.position.line if hasattr(method_node,'position') and method_node.position else 0
                    snippet=code[m_start*80:m_start*80+2000] if m_start else code
                    for m in SQL_TABLE_RE_G.finditer(snippet):
                        tbl=m.group(1)
                        key=(class_node_id,tbl)
                        if key not in seen_tables:
                            seen_tables.add(key)
                            results["edges_list"].append({"source":class_node_id,"target":f"TABLE:{tbl}","type":"USES"})
                            results["sql_list"].append({"table":tbl,"file":rel_path,"method":m_name,"class":class_name})

            # --- entry points ---
            is_spring=bool(class_ann_names&SPRING_ENDPOINT_ANNOT_G)
            if is_spring:
                base_path=""
                for ann in type_node.annotations:
                    if ann.name=="RequestMapping":
                        base_path=_get_ann_value_g(ann)
                        break
                for _,mn in class_methods:
                    mn_anns=_get_annot_names_g(mn)
                    mapping_anns=mn_anns&{"GetMapping","PostMapping","PutMapping","DeleteMapping"}
                    if mapping_anns:
                        method_path=""
                        http_m="GET"
                        for a in mn.annotations:
                            if a.name in mapping_anns:
                                method_path=_get_ann_value_g(a)
                                http_m=HTTP_METHOD_MAP_G.get(a.name,"GET")
                                break
                        endpoint=base_path+method_path if base_path else method_path
                        results["entrypoints_list"].append({
                            "type":"SPRING","endpoint":endpoint,"http_method":http_m,
                            "handler":f"{class_name}.{mn.name}","source_file":rel_path
                        })

            if class_ann_names&EJB_ANNOT_G:
                for _,mn in class_methods:
                    results["entrypoints_list"].append({"type":"EJB","name":class_name,"method":mn.name,"source_file":rel_path})

            if class_ann_names&SOAP_ANNOT_G:
                for _,mn in class_methods:
                    results["entrypoints_list"].append({"type":"SOAP","service":class_name,"operation":mn.name,"source_file":rel_path})

            if "WebServlet" in class_ann_names:
                results["entrypoints_list"].append({"type":"SERVLET","servlet":class_name,"url_pattern":"/*","source_file":rel_path})

            if class_ann_names&SCHEDULER_ANNOT_G:
                for _,mn in class_methods:
                    results["entrypoints_list"].append({"type":"SCHEDULER","class":class_name,"method":mn.name,"source_file":rel_path})

            if "MessageDriven" in class_ann_names:
                results["entrypoints_list"].append({"type":"JMS","consumer":class_name,"source_file":rel_path})

        results["symbols_entry"]={"file":rel_path,"classes":classes,"methods":methods,"imports":imports}
        for imp in imports:
            results["graph_entries"].append({"source":rel_path,"target":imp,"type":"import"})
            results["edges_list"].append({"source":file_node_id,"target":f"IMPORT:{imp}","type":"IMPORTS"})

        results["parse_ok"]=True
    except Exception:
        pass
    return results

# ============================================================
# Task 2 & 3: Parse Java files in parallel with ProcessPoolExecutor
# ============================================================
t0=time.perf_counter()
java_files=list(repo.rglob("*.java"))
java_count=len(java_files)
repo_str=str(repo)

# Merge results from all workers
with ProcessPoolExecutor(max_workers=None) as executor:
    futures={executor.submit(_parse_single_java, str(f), repo_str): f for f in java_files}
    for fut in as_completed(futures):
        res=fut.result()
        if not res["parse_ok"]:
            continue
        # Merge lists
        classes_list.extend(res["classes_list"])
        methods_list.extend(res["methods_list"])
        entrypoints_list.extend(res["entrypoints_list"])
        sql_list.extend(res["sql_list"])
        edges_list.extend(res["edges_list"])
        graph.extend(res["graph_entries"])
        nodes_dict.update(res["nodes_dict"])
        # Symbols
        if res["symbols_entry"]:
            symbols.append(res["symbols_entry"])

times["parse_java"]=time.perf_counter()-t0

# Task 6: Extract JSP entry pages
t0=time.perf_counter()
for f in repo.rglob("*.jsp"):
    rel_path=str(f.relative_to(repo))
    entrypoints_list.append({
        "type":"JSP",
        "page":rel_path,
        "source_file":rel_path
    })

for f in repo.rglob("*.jspx"):
    rel_path=str(f.relative_to(repo))
    entrypoints_list.append({
        "type":"JSP",
        "page":rel_path,
        "source_file":rel_path
    })

# Task 6: Extract Struts configuration from struts-config.xml
for f in repo.rglob("struts-config.xml"):
    try:
        tree=ET.parse(f)
        root=tree.getroot()
        for action in root.findall(".//action"):
            path=action.get("path","")
            action_type=action.get("type","")
            if path and action_type:
                entrypoints_list.append({
                    "type":"STRUTS",
                    "path":path,
                    "action":action_type,
                    "source_file":str(f.relative_to(repo))
                })
    except Exception:
        pass

times["entrypoints_jsp"]=time.perf_counter()-t0

# Task 6: Extract Struts configuration from struts-config.xml
t0=time.perf_counter()
for f in repo.rglob("struts-config.xml"):
    try:
        tree=ET.parse(f)
        root=tree.getroot()
        for action in root.findall(".//action"):
            path=action.get("path","")
            action_type=action.get("type","")
            if path and action_type:
                entrypoints_list.append({
                    "type":"STRUTS",
                    "path":path,
                    "action":action_type,
                    "source_file":str(f.relative_to(repo))
                })
    except Exception:
        pass

# Task 6: Extract Servlet mappings from web.xml
for f in repo.rglob("web.xml"):
    try:
        tree=ET.parse(f)
        root=tree.getroot()
        ns={'web':'http://java.sun.com/xml/ns/javaee'}
        for mapping in root.findall(".//web:servlet-mapping",ns)+root.findall(".//servlet-mapping"):
            servlet_name=mapping.findtext("web:servlet-name",default=mapping.findtext("servlet-name",""))
            url_pattern=mapping.findtext("web:url-pattern",default=mapping.findtext("url-pattern",""))
            if servlet_name and url_pattern:
                entrypoints_list.append({
                    "type":"SERVLET",
                    "url_pattern":url_pattern,
                    "servlet":servlet_name,
                    "source_file":str(f.relative_to(repo))
                })
    except Exception:
        pass

times["entrypoints_xml"]=time.perf_counter()-t0

# Task 8: Add endpoint nodes
t0=time.perf_counter()
for ep in entrypoints_list:
    ep_id=f"ENDPOINT:{ep.get('name',ep.get('endpoint',ep.get('service',ep.get('path',ep.get('page',ep.get('servlet',ep.get('class','')))))))}"
    nodes_dict[ep_id]={
        "type":"ENDPOINT",
        "endpoint_type":ep.get("type"),
        "details":ep
    }

# Task 8: Add table nodes (merge files list if table already seen)
for sql_item in sql_list:
    table_id=f"TABLE:{sql_item['table']}"
    if table_id not in nodes_dict:
        nodes_dict[table_id]={"type":"TABLE","name":sql_item['table'],"files":[]}
    f_list=nodes_dict[table_id]["files"]
    if sql_item['file'] not in f_list:
        f_list.append(sql_item['file'])

times["build_graph"]=time.perf_counter()-t0

# Create retrieval_index directory for all outputs
t0=time.perf_counter()
(repo/"retrieval_index").mkdir(exist_ok=True)

# Store Phase 2 outputs
with open(repo/"retrieval_index/files.json","w") as fp:
    json.dump(files_metadata,fp,indent=2)

with open(repo/"retrieval_index/classes.json","w") as fp:
    json.dump(classes_list,fp,indent=2)

with open(repo/"retrieval_index/methods.json","w") as fp:
    json.dump(methods_list,fp,indent=2)

# Task 6: Store entry points
with open(repo/"retrieval_index/entrypoints.json","w") as fp:
    json.dump(entrypoints_list,fp,indent=2)

# Task 7: Store SQL information
with open(repo/"retrieval_index/sql.json","w") as fp:
    json.dump(sql_list,fp,indent=2)

# Task 8: Store graph
graph_output={
    "nodes":list(nodes_dict.values()),
    "edges":edges_list
}
with open(repo/"retrieval_index/graph.json","w") as fp:
    json.dump(graph_output,fp,indent=2)

with open(repo/"retrieval_index/symbols.json","w") as fp:
    json.dump(symbols,fp,indent=2)

with open(repo/"retrieval_index/dependency_graph.json","w") as fp:
    json.dump(graph,fp,indent=2)

times["write_json"]=time.perf_counter()-t0

t0=time.perf_counter()
git_data=[]

try:
    out=subprocess.check_output(
        ["git","log","--pretty=format:%H|%s","-n","500"],
        cwd=repo,
        text=True
    )

    for line in out.splitlines():
        parts=line.split("|",1)
        if len(parts)!=2:
            continue

        jira=re.findall(r"[A-Z]+-\d+",parts[1])

        git_data.append({
            "commit":parts[0],
            "message":parts[1],
            "jira":jira
        })
except Exception:
    pass

times["git_log"]=time.perf_counter()-t0

t0=time.perf_counter()
with open(repo/"retrieval_index/git_index.json","w") as fp:
    json.dump(git_data,fp,indent=2)

times["write_git"]=time.perf_counter()-t0

END_OVERALL=time.perf_counter()
total=END_OVERALL-START_OVERALL

print(f"Index built successfully")
print(f"Java files found: {java_count}")
print(f"Classes extracted: {len(classes_list)}")
print(f"Methods extracted: {len(methods_list)}")
print(f"Entry points found: {len(entrypoints_list)}")
print(f"SQL queries found: {len(sql_list)}")
print(f"Graph nodes: {len(nodes_dict)}")
print(f"Graph edges: {len(edges_list)}")
print("========================================")
print("Build Index Timing")
print("========================================")
for step,elapsed in sorted(times.items()):
    print(f"  {step:25s}: {elapsed:.3f}s")
print("  "+"-"*38)
print(f"  {'TOTAL':25s}: {total:.3f}s")
print("========================================")
