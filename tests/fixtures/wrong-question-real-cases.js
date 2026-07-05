const REAL_WRONG_QUESTION_CASES = [
  {
    id: 'rq-resp-001',
    title: 'Respiratory percussion after pneumonia-like stem',
    risk: 'standard_source_navigation',
    input: `题目：30岁，男性，因发热右侧胸痛咳嗽3天入院。三天来每日体温最低为39.2℃，最高39.8℃。入院后查体T39.5℃，右锁骨下可闻及支气管呼吸音。该患者右上肺叩诊音可能出现
A. 清音
B. 浊音
C. 实音
D. 鼓音
E. 过清音

正确答案：B
我的答案：E

参考解析

患者为青年男性（大叶性肺炎的好发年龄），因发热、胸痛、咳嗽入院，起病急骤，热型为稽留热，右锁骨下可闻及支气管呼吸音提示肺实变（大叶性肺炎的典型表现和体征），考虑诊断为大叶性肺炎。大叶性肺炎由于肺部实变，叩诊为浊音（B对）。清音（A错）为正常肺部的叩诊音。实音（C错）见于叩诊心、肝等实质脏器。鼓音（D错）正常情况下可见于胃泡区和腹部，病理状态下可见于肺内空洞、气胸、气腹。过清音（E错）常见于肺气肿。`,
    expected: {
      sectionTitle: '第六章 肺部感染性疾病',
      unitTitle: '肺炎 · 社区获得性肺炎和医院获得性肺炎',
      catalogTitle: '第一节 肺炎概述',
      itemTitle: '临床表现',
      pageLabel: 'p.78',
      evidenceIncludes: ['肺实变', '叩诊呈浊音', '支气管呼吸音'],
    },
  },
  {
    id: 'rq-resp-002',
    title: 'Pneumococcal pneumonia penicillin treatment lookup',
    risk: 'high_risk_source_navigation_only',
    input: `题目：在治疗肺炎球菌肺炎使用青霉素时，错误的方法是
A. 一般患者每次肌注80万单位，每8小时1次
B. 每日剂量800万单位，加在500ml输液中缓慢静滴
C. 每日剂量800万单位，分3次静脉滴注
D. 静脉滴药时每次用量应在1小时内滴完
E. 对青霉素过敏者不可使用此药

正确答案：B
我的答案：D

参考解析

对于肺炎链球菌的治疗，首选青霉素，用药途径及剂量视病情轻重及有无并发症而定。对于成年轻症患者，可用240万U/d，分3次肌肉注射（A对），病情稍重者，用240万～480万U/d，分次静脉注射，每6～8小时一次，重症及并发脑膜炎者，可增至1000万～3000万U/d，分4次静脉滴注（C对）。青霉素的使用原则就是现配现用，分次配制，分次输入。每日剂量800万单位，加在500ml输液中缓慢静滴（B错，为本题正确答案），导致静滴的时间过长，使药物浓度降低，而且增加了青霉素水解和发生过敏反应的机会。`,
    expected: {
      sectionTitle: '第六章 肺部感染性疾病',
      unitTitle: '肺炎链球菌肺炎',
      catalogTitle: '第二节 细菌性肺炎',
      itemTitle: '抗菌药物治疗',
      groupTitle: '治疗',
      pageLabel: 'p.83',
      evidenceIncludes: ['青霉素G', '用药途径及剂量'],
    },
    safetyNote:
      'Dose, route, infusion, allergy, and treatment-priority content is high risk; this fixture verifies source navigation only, not publication approval or medical advice.',
  },
  {
    id: 'rq-resp-003',
    title: 'Viral pneumonia IgM serology and leukopenia lookup',
    risk: 'standard_source_navigation',
    input: `题目：
女，24岁。一周前从外地旅游返家，发热咳嗽呼吸困难，全身酸痛，倦怠，实验室检查：WBC3.2×10⁹/L，血清学检测特异性IgM抗体阳性。患者可能是
A. 衣原体肺炎
B. 病毒性肺炎
C. 真菌性肺炎
D. 细菌性肺炎
E. 传染病

正确答案：B
我的答案：A

参考解析
患者为青年女性，一周前从外地旅游返家，发热咳嗽呼吸困难，全身酸痛，倦怠，WBC3.2×10⁹/L（正常值为4～10×10⁹/L），血清学检测特异性IgM抗体阳性，症状与实验室检查符合病毒性肺炎（B对）的诊断。衣原体肺炎（A错）起病缓慢，临床症状与肺炎支原体相似，表现为咽痛、咳嗽、咳痰、发热等，一般症状较轻。真菌性肺炎（C错）表现为畏寒、高热，咳白色黏痰，痰量多似白泡沫塑料，偶带血丝，随病情进展憋喘、气短加重，尤以夜间为甚。细菌性肺炎（D错）起病急、寒战、高热、呼吸困难、胸痛严重，胸片较典型，但一般血清学检测无特异性抗体。传染病（E错）是一个总的概念，有多种多样的临床表现，最佳选项为病毒性肺炎。`,
    expected: {
      sectionTitle: '第六章 肺部感染性疾病',
      unitTitle: '病毒性肺炎',
      catalogTitle: '第三节 病毒性肺炎',
      groupTitle: '病毒性肺炎',
      itemTitle: '诊断与鉴别诊断',
      pageLabel: 'p.85',
      evidenceIncludes: ['血清检测病毒的特异性IgM', '有助于早期诊断'],
    },
  },
]

module.exports = { REAL_WRONG_QUESTION_CASES }
