import fs from 'fs';
import path from 'path';

const TAXONOMY_PATH = path.resolve('src/data/taxonomy.json');

const RULES = [
  {
    name: 'no-chronic-under-acute',
    check(parent, child) {
      return parent.label?.includes('急性') && child.label?.includes('慢性');
    },
    message(parent, child) {
      return `"${child.label}" 不应挂在 "${parent.label}"（急性父节点）下`;
    },
  },
  {
    name: 'no-upper-under-lower-respiratory',
    check(parent, child) {
      return (
        (parent.label?.includes('上呼吸道') && child.label?.includes('支气管')) ||
        (parent.label?.includes('上呼吸道') && child.label?.includes('肺'))
      );
    },
    message(parent, child) {
      return `"${child.label}" 是下呼吸道疾病，不应挂在 "${parent.label}" 下`;
    },
  },
  {
    name: 'no-infectious-under-non-infectious',
    check(parent, child) {
      const infectiousKeywords = ['感染', '炎症', '脓肿', '结核', '肺炎'];
      const cleanLabels = [
        '肿瘤', '癌症', '癌',
      ];
      const parentIsClean = cleanLabels.some(k => parent.label?.includes(k));
      const childIsInfectious = infectiousKeywords.some(k => child.label?.includes(k));
      return parentIsClean && childIsInfectious;
    },
    message(parent, child) {
      return `感染性疾病 "${child.label}" 不应挂在肿瘤类父节点 "${parent.label}" 下`;
    },
  },
  {
    name: 'chapter-must-have-children',
    check(parent) {
      return (
        parent.children &&
        parent.children.length === 0 &&
        !parent.knowledgeNodeIds
      );
    },
    message(parent) {
      return `叶子节点 "${parent.label}" 缺少 knowledgeNodeIds`;
    },
  },
  {
    name: 'orphan-knowledge-node-ids',
    check(node) {
      return (
        node.knowledgeNodeIds &&
        node.knowledgeNodeIds.length === 0
      );
    },
    message(node) {
      return `叶子节点 "${node.label}" 的 knowledgeNodeIds 为空数组`;
    },
  },
];

function validateTaxonomy() {
  if (!fs.existsSync(TAXONOMY_PATH)) {
    console.error(`❌ 找不到 taxonomy 文件: ${TAXONOMY_PATH}`);
    process.exit(1);
  }

  const raw = fs.readFileSync(TAXONOMY_PATH, 'utf-8');
  let taxonomy;
  try {
    taxonomy = JSON.parse(raw);
  } catch {
    console.error('❌ taxonomy.json 不是有效的 JSON');
    process.exit(1);
  }

  const errors = [];
  const allNodes = [];

  function walk(nodes, parent = null) {
    for (const node of nodes) {
      allNodes.push({ id: node.id, label: node.label });

      if (parent) {
        for (const rule of RULES) {
          if (rule.check.length >= 2) {
            if (rule.check(parent, node)) {
              errors.push(`${rule.name}: ${rule.message(parent, node)}`);
            }
          } else if (rule.check.length === 1) {
            if (rule.check(node)) {
              errors.push(`${rule.name}: ${rule.message(node)}`);
            }
          }
        }
      }

      if (node.children && node.children.length > 0) {
        walk(node.children, node);
      }
    }
  }

  walk(taxonomy);

  for (let i = 0; i < allNodes.length; i++) {
    for (let j = i + 1; j < allNodes.length; j++) {
      if (allNodes[i].id === allNodes[j].id) {
        errors.push(`duplicate-node-id: 节点 ID "${allNodes[i].id}" 重复`);
      }
    }
  }

  if (errors.length > 0) {
    console.error(`❌ taxonomy 校验失败，发现 ${errors.length} 个错误：`);
    for (const err of errors) {
      console.error(`  - ${err}`);
    }
    process.exit(1);
  } else {
    console.log('✅ taxonomy 校验通过。');
  }
}

validateTaxonomy();
