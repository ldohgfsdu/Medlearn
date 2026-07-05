const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTypeScriptModule } = require('./loadTsModule')

const textbookStudy = loadTypeScriptModule(path.join(__dirname, '..', 'utils', 'textbookStudy.ts'))
const {
  extractWrongQuestionTerms,
  locateWrongQuestionCandidates,
} = loadTypeScriptModule(path.join(__dirname, '..', 'utils', 'wrongQuestionIntake.ts'), {
  '@/utils/textbookStudy': textbookStudy,
})

function detail(overrides = {}) {
  return {
    textbookTitle: 'Internal Medicine',
    systemTitle: 'Respiratory',
    partTitle: 'Respiratory Disease',
    section: {
      id: 'resp-pneumonia',
      sectionTitle: 'Pulmonary Infection',
      nodeCount: 2,
      organizedCount: 2,
      evidenceOnlyCount: 0,
      mergedCount: 0,
      groupedCount: 0,
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
      partTitle: 'Respiratory Disease',
      systemTitle: 'Respiratory',
    },
    nodes: [
      {
        id: 'pneumonia-treatment',
        title: 'Pneumonia treatment',
        content: 'Antimicrobial treatment should be selected from the textbook evidence.',
        renderType: 'normal',
        publicationState: 'organized',
        qualityBadges: [],
        listItems: [],
        evidenceItems: [{
          artifactId: 'pneumonia-treatment-ev',
          text: 'Pneumonia treatment source text with antimicrobial therapy guidance.',
          pageStart: 82,
          pageEnd: 82,
          sourceOrder: 1,
          pageLabel: 'p.82',
        }],
        evidenceExcerpt: 'Pneumonia treatment source text with antimicrobial therapy guidance.',
        evidenceFull: 'Pneumonia treatment source text with antimicrobial therapy guidance.',
        pageLabel: 'p.82',
        sourceHeading: 'Treatment',
        groupTopic: 'treatment',
        artifactIds: [],
        sourceNodeIds: ['pneumonia-treatment'],
      },
      {
        id: 'asthma-treatment',
        title: 'Asthma treatment',
        content: 'Asthma source text.',
        renderType: 'normal',
        publicationState: 'organized',
        qualityBadges: [],
        listItems: [],
        evidenceItems: [{
          artifactId: 'asthma-treatment-ev',
          text: 'Asthma treatment source text.',
          pageStart: 120,
          pageEnd: 120,
          sourceOrder: 2,
          pageLabel: 'p.120',
        }],
        evidenceExcerpt: 'Asthma treatment source text.',
        evidenceFull: 'Asthma treatment source text.',
        pageLabel: 'p.120',
        sourceHeading: 'Treatment',
        groupTopic: 'treatment',
        artifactIds: [],
        sourceNodeIds: ['asthma-treatment'],
      },
    ],
    ...overrides,
  }
}

function node(overrides) {
  return {
    id: overrides.id,
    title: overrides.title,
    content: overrides.content,
    renderType: 'normal',
    publicationState: 'organized',
    qualityBadges: [],
    listItems: [],
    evidenceItems: [{
      artifactId: `${overrides.id}-ev`,
      text: overrides.evidenceText ?? overrides.content,
      pageStart: overrides.pageStart,
      pageEnd: overrides.pageStart,
      sourceOrder: overrides.sourceOrder ?? 1,
      pageLabel: overrides.pageLabel,
    }],
    evidenceExcerpt: overrides.evidenceText ?? overrides.content,
    evidenceFull: overrides.evidenceText ?? overrides.content,
    pageLabel: overrides.pageLabel,
    sourceHeading: overrides.sourceHeading ?? overrides.title,
    groupTopic: overrides.groupTopic,
    artifactIds: [],
    sourceNodeIds: [overrides.id],
  }
}

test('extractWrongQuestionTerms keeps clinical cue terms and normalized tokens', () => {
  const terms = extractWrongQuestionTerms('肺炎 treatment antimicrobial therapy')

  assert.equal(terms.includes('肺炎'), true)
  assert.equal(terms.includes('treatment'), true)
  assert.equal(terms.includes('antimicrobial'), true)
})

test('extractWrongQuestionTerms ignores vital sign numbers as retrieval terms', () => {
  const terms = extractWrongQuestionTerms('30岁男性，发热39.5℃，胸痛咳嗽，右上肺叩诊浊音')

  assert.equal(terms.includes('30'), false)
  assert.equal(terms.includes('39'), false)
  assert.equal(terms.some((term) => /\d/.test(term)), false)
  assert.equal(terms.includes('肺炎'), false)
  assert.equal(terms.includes('胸痛'), true)
  assert.equal(terms.includes('叩诊'), true)
  assert.equal(terms.includes('浊音'), true)
})

test('locateWrongQuestionCandidates returns only grounded textbook evidence locations', () => {
  const candidates = locateWrongQuestionCandidates(
    'pneumonia antimicrobial treatment',
    [detail()],
  )

  assert.ok(candidates.length > 0)
  assert.equal(candidates[0].sectionId, 'resp-pneumonia')
  assert.equal(candidates[0].pageLabel, 'p.82')
  assert.match(candidates[0].evidenceExcerpt, /source text/)
  assert.doesNotMatch(candidates[0].evidenceExcerpt, /answer|diagnosis is/i)
  assert.equal(candidates.some((candidate) => /Asthma/.test(candidate.evidenceExcerpt)), false)
})

test('locateWrongQuestionCandidates ignores matches without evidence page labels', () => {
  const ungrounded = detail({
    nodes: [
      {
        id: 'ungrounded',
        title: 'Pneumonia treatment',
        content: 'Pneumonia treatment without page evidence.',
        renderType: 'normal',
        publicationState: 'organized',
        qualityBadges: [],
        listItems: [],
        evidenceItems: [],
        evidenceExcerpt: '',
        evidenceFull: '',
        pageLabel: '',
        sourceHeading: 'Treatment',
        groupTopic: 'treatment',
        artifactIds: [],
        sourceNodeIds: ['ungrounded'],
      },
    ],
  })

  assert.equal(locateWrongQuestionCandidates('pneumonia treatment', [ungrounded]).length, 0)
})

test('locateWrongQuestionCandidates does not let age or fever numbers outrank respiratory evidence', () => {
  const respiratory = detail({
    section: {
      id: 'resp-lobar-pneumonia',
      sectionTitle: '肺部感染性疾病',
      nodeCount: 1,
      organizedCount: 1,
      evidenceOnlyCount: 0,
      mergedCount: 0,
      groupedCount: 0,
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
      partTitle: '呼吸系统疾病',
      systemTitle: '呼吸系统疾病',
    },
    nodes: [
      node({
        id: 'lobar-pneumonia-signs',
        title: '大叶性肺炎体征',
        content: '大叶性肺炎可出现肺实变，查体可见支气管呼吸音，叩诊呈浊音。',
        evidenceText: '大叶性肺炎可出现肺实变，查体可见支气管呼吸音，叩诊呈浊音。',
        pageStart: 82,
        pageLabel: 'p.82',
        sourceHeading: '临床表现',
        groupTopic: 'clinical_manifestation',
      }),
    ],
  })
  const poisoning = detail({
    section: {
      id: 'poisoning',
      sectionTitle: '中毒',
      nodeCount: 1,
      organizedCount: 1,
      evidenceOnlyCount: 0,
      mergedCount: 0,
      groupedCount: 0,
      pageRange: '939',
      pageStart: 939,
      pageEnd: 939,
      partTitle: '理化因素所致疾病',
      systemTitle: '急诊医学',
    },
    nodes: [
      node({
        id: 'long-acting-drugs',
        title: '长效类药物',
        content: '长效类药物半衰期大于30小时，相关页码为939。',
        evidenceText: '长效类药物半衰期大于30小时，相关页码为939。',
        pageStart: 939,
        pageLabel: 'p.939',
        sourceHeading: '戒断综合征',
      }),
    ],
  })

  const candidates = locateWrongQuestionCandidates(
    '30岁男性，发热39.5℃，右侧胸痛咳嗽3天，右锁骨下支气管呼吸音，右上肺叩诊可能为浊音，考虑大叶性肺炎、肺实变。',
    [poisoning, respiratory],
  )

  assert.ok(candidates.length > 0)
  assert.equal(candidates[0].sectionId, 'resp-lobar-pneumonia')
  assert.equal(candidates.some((candidate) => candidate.sectionId === 'poisoning'), false)
})

test('locateWrongQuestionCandidates ignores answer option noise and uses explanation anchors', () => {
  const lobarPneumonia = detail({
    section: {
      id: 'resp-lobar-pneumonia',
      sectionTitle: '肺部感染性疾病',
      nodeCount: 1,
      organizedCount: 1,
      evidenceOnlyCount: 0,
      mergedCount: 0,
      groupedCount: 0,
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
      partTitle: '呼吸系统疾病',
      systemTitle: '呼吸系统疾病',
    },
    nodes: [
      node({
        id: 'lobar-pneumonia-signs',
        title: '大叶性肺炎体征',
        content: '大叶性肺炎可出现肺实变，查体可见支气管呼吸音，叩诊呈浊音。',
        evidenceText: '大叶性肺炎可出现肺实变，查体可见支气管呼吸音，叩诊呈浊音。',
        pageStart: 82,
        pageLabel: 'p.82',
        sourceHeading: '临床表现',
        groupTopic: 'clinical_manifestation',
      }),
    ],
  })
  const emphysema = detail({
    section: {
      id: 'resp-emphysema',
      sectionTitle: '肺气肿',
      nodeCount: 1,
      organizedCount: 1,
      evidenceOnlyCount: 0,
      mergedCount: 0,
      groupedCount: 0,
      pageRange: '58',
      pageStart: 58,
      pageEnd: 58,
      partTitle: '呼吸系统疾病',
      systemTitle: '呼吸系统疾病',
    },
    nodes: [
      node({
        id: 'emphysema-percussion',
        title: '触诊表现',
        content: '肺部过清音，心浊音界缩小。',
        evidenceText: '肺部过清音，心浊音界缩小。',
        pageStart: 58,
        pageLabel: 'p.58',
        sourceHeading: '体征',
      }),
    ],
  })

  const candidates = locateWrongQuestionCandidates(
    `题目：30岁男性，发热右侧胸痛咳嗽3天，右锁骨下可闻及支气管呼吸音。该患者右上肺叩诊音可能出现
A. 清音
B. 浊音
C. 实音
D. 鼓音
E. 过清音
正确答案：B
我的答案：E
参考解析：支气管呼吸音提示肺实变，考虑大叶性肺炎。大叶性肺炎由于肺部实变，叩诊为浊音。过清音常见于肺气肿。`,
    [emphysema, lobarPneumonia],
  )

  assert.ok(candidates.length > 0)
  assert.equal(candidates[0].sectionId, 'resp-lobar-pneumonia')
  assert.ok(candidates[0].score > (candidates.find((candidate) => candidate.sectionId === 'resp-emphysema')?.score ?? 0))
})

test('locateWrongQuestionCandidates supports pneumococcal pneumonia penicillin treatment questions', () => {
  const pneumococcalPneumonia = detail({
    section: {
      id: 'resp-pneumococcal-pneumonia',
      sectionTitle: '肺炎链球菌肺炎',
      nodeCount: 1,
      organizedCount: 1,
      evidenceOnlyCount: 0,
      mergedCount: 0,
      groupedCount: 0,
      pageRange: '77-81',
      pageStart: 77,
      pageEnd: 81,
      partTitle: '呼吸系统疾病',
      systemTitle: '呼吸系统疾病',
    },
    nodes: [
      node({
        id: 'pneumococcal-penicillin',
        title: '青霉素治疗',
        content: '肺炎链球菌肺炎首选青霉素，给药途径及剂量视病情轻重及有无并发症而定。',
        evidenceText: '肺炎链球菌肺炎首选青霉素，给药途径及剂量视病情轻重及有无并发症而定。',
        pageStart: 80,
        pageLabel: 'p.80',
        sourceHeading: '治疗',
        groupTopic: 'treatment',
      }),
    ],
  })
  const genericDrug = detail({
    section: {
      id: 'drug-allergy',
      sectionTitle: '药物过敏',
      nodeCount: 1,
      organizedCount: 1,
      evidenceOnlyCount: 0,
      mergedCount: 0,
      groupedCount: 0,
      pageRange: '900',
      pageStart: 900,
      pageEnd: 900,
      partTitle: '理化因素所致疾病',
      systemTitle: '急诊医学',
    },
    nodes: [
      node({
        id: 'penicillin-allergy',
        title: '青霉素过敏',
        content: '对青霉素过敏者不可使用此药。',
        evidenceText: '对青霉素过敏者不可使用此药。',
        pageStart: 900,
        pageLabel: 'p.900',
        sourceHeading: '药物过敏',
      }),
    ],
  })

  const candidates = locateWrongQuestionCandidates(
    `题目：在治疗肺炎球菌肺炎使用青霉素时，错误的方法是
A. 一般患者每次肌注80万单位，每8小时1次
B. 每日剂量800万单位，加在500ml输液中缓慢静滴
C. 每日剂量800万单位，分3次静脉滴注
D. 静脉滴药时每次用量应在1小时内滴完
E. 对青霉素过敏者不可使用此药
正确答案：B
我的答案：D
参考解析：对于肺炎链球菌的治疗，首选青霉素，用药途径及剂量视病情轻重及有无并发症而定。`,
    [genericDrug, pneumococcalPneumonia],
  )

  assert.ok(candidates.length > 0)
  assert.equal(candidates[0].sectionId, 'resp-pneumococcal-pneumonia')
  assert.equal(candidates.some((candidate) => candidate.sectionId === 'drug-allergy'), false)
})
