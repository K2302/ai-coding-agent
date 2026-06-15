
import json

with open("retrieval_index/git_index.json") as fp:
    data=json.load(fp)

mapping={}

for item in data:
    for jira in item["jira"]:
        mapping.setdefault(jira,[]).append(item["commit"])

print(mapping)
