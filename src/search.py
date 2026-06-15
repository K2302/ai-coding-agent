
import json,sys
from collections import Counter

query=sys.argv[1].lower().split()

with open("retrieval_index/symbols.json") as fp:
    data=json.load(fp)

scores=[]

for item in data:
    text=" ".join(
        item["classes"]+
        item["methods"]+
        item["imports"]
    ).lower()

    score=sum(text.count(q) for q in query)

    if score:
        scores.append((score,item["file"]))

for s,f in sorted(scores,reverse=True)[:20]:
    print(s,f)
