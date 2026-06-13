"""Deprecated simple test. Use pipeline_v3_extract.py + tests/test_pipeline_v3_catalog.py instead."""
import ollama
import json

def test_extract():
    # 模拟一段教材原文（心力衰竭）
    sample_text = """
    心力衰竭（Heart Failure）简称心衰，是由于任何心脏结构或功能异常导致心室充盈或射血能力受损，
    最后导致心排血量不足以维持组织代谢需要的一组临床综合征。
    其基本机制是心肌收缩力减低和心室重构。
    左心衰竭常表现为肺淤血，引起呼吸困难；右心衰竭常表现为体循环淤血，引起下肢水肿和肝颈静脉回流征阳性。
    治疗上，利尿剂（如呋塞米）用于减轻容量负荷，ACEI/ARB 用于抑制心室重构。
    鉴别诊断需与支气管哮喘（心源性哮喘 vs 肺源性哮喘）相鉴别。
    """

    prompt = f"""你是严谨的医学专家。请从提供的【教材内容】中提取结构化知识。

### 提取规则：
1. 提取知识点（Nodes）：包含名称、类型（疾病/机制/症状/药物/检查）。
2. 提取关系（Edges）：连接节点，关系类型包括 (causes, characteristic_of, treated_by, differential)。
3. 医学思维：尝试识别 VINDICATE 标签（如 V-血管性, I-感染性等）。

### 返回格式：
严格返回 JSON，结构如下：
{{
  "nodes": [ {{"id": "id1", "label": "名称", "type": "类型", "definition": "简练定义"}} ],
  "edges": [ {{"source": "id1", "target": "id2", "relation": "关系"}} ]
}}

【教材内容】：
{sample_text}
"""

    print("--- 正在调用本地 Qwen2.5 提取中 ---")
    response = ollama.chat(
        model='qwen2.5:7b-instruct-q5_K_M',
        messages=[{'role': 'user', 'content': prompt}],
        options={'temperature': 0.1}
    )

    content = response['message']['content']
    print("\n--- LLM 返回原始结果 ---")
    print(content)

if __name__ == "__main__":
    test_extract()
