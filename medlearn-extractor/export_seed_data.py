import json
import time

with open("output/extractedKnowledgeNodes.json", "r", encoding="utf-8") as f:
    nodes = json.load(f)

ts = int(time.time() * 1000)
for n in nodes:
    n["createdAt"] = ts
    n["updatedAt"] = ts
    n["generatedAt"] = ts

out = 'import type { KnowledgeNode } from "../types/knowledge";\n\n'
out += "// Auto-generated from medlearn-extractor pipeline\n"
out += f"// Total: {len(nodes)} knowledge nodes\n"
out += f"// Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
out += "export const seedKnowledgeNodes: KnowledgeNode[] = "
out += json.dumps(nodes, ensure_ascii=False, indent=2)
out += ";\n"

with open("../mini-program/src/data/seedKnowledgeNodes.ts", "w", encoding="utf-8") as f:
    f.write(out)

print(f"Written {len(nodes)} nodes to seedKnowledgeNodes.ts")
