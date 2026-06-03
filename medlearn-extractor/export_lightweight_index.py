"""Export a lightweight index for the main package (no full content)."""
import json

with open("output/extractedKnowledgeNodes.json", "r", encoding="utf-8") as f:
    nodes = json.load(f)

index = []
detail_map = {}

for n in nodes:
    idx_entry = {
        "id": n["id"],
        "type": n["type"],
        "title": n["title"],
        "subject": n["subject"],
        "chapter": n.get("chapter", ""),
        "tags": n.get("tags", [])[:5],
    }
    index.append(idx_entry)
    detail_map[n["id"]] = n

# Write index
with open("../mini-program/src/data/knowledgeIndex.ts", "w", encoding="utf-8") as f:
    f.write('import type { KnowledgeNodeIndex } from "../types/knowledge";\n\n')
    f.write(f"// Lightweight index: {len(index)} entries, no full content\n\n")
    f.write("export const knowledgeIndex: KnowledgeNodeIndex[] = ")
    f.write(json.dumps(index, ensure_ascii=False, indent=2))
    f.write(";\n")

# Write detail map to subpackage
out = 'import type { KnowledgeNode } from "../../types/knowledge";\n\n'
out += f"// Full knowledge nodes: {len(detail_map)} entries\n"
out += f"// This file is in the pagesA subpackage\n\n"
out += "export const knowledgeDetailMap: Record<string, KnowledgeNode> = "
out += json.dumps(detail_map, ensure_ascii=False, indent=2)
out += ";\n"

with open("../mini-program/src/pagesA/knowledgeDetailData.ts", "w", encoding="utf-8") as f:
    f.write(out)

print(f"Index: {len(index)} entries")
print(f"Detail map: {len(detail_map)} entries")
print("Done!")
