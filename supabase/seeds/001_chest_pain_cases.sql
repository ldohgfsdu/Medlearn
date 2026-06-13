-- 胸痛病例种子数据
-- 基于 PRD 第 60 章和第 71 章的病例标准

INSERT INTO case_templates (id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, demographics, patient_world, ground_truth, scoring_rubric) VALUES

-- ============================================
-- 病例 1: STEMI（初级）
-- ============================================
(
    'CC_CP_001',
    'CC_CP_001',
    '急性胸痛 — 65岁男性',
    'chest_pain',
    'cardiology',
    'beginner',
    15,

    -- demographics (Layer 2a)
    '{
        "age": 65,
        "gender": "male",
        "occupation": "退休教师",
        "education": "大学",
        "emotion": "焦虑",
        "presentationContext": "因胸痛3小时来急诊"
    }',

    -- patient_world (Layer 2)
    '{
        "chiefComplaint": "胸口疼了3个小时",
        "history": {
            "presentIllness": [
                {
                    "id": "hpi_onset",
                    "field": "发病时间",
                    "answer": "今天早上7点左右开始的，吃早饭的时候突然疼起来的",
                    "patientVoice": "今天早上吃早饭的时候，突然胸口就疼起来了",
                    "importance": "critical",
                    "category": "hpi"
                },
                {
                    "id": "hpi_duration",
                    "field": "持续时间",
                    "answer": "已经3个小时了，一直没停",
                    "patientVoice": "一直疼，3个小时了，没停过",
                    "importance": "critical",
                    "category": "hpi"
                },
                {
                    "id": "hpi_character",
                    "field": "疼痛性质",
                    "answer": "压榨样疼痛，像有东西压在胸口",
                    "patientVoice": "就像有块大石头压在胸口一样，闷闷的，压着疼",
                    "importance": "critical",
                    "category": "hpi"
                },
                {
                    "id": "hpi_location",
                    "field": "疼痛部位",
                    "answer": "胸骨后面，偏左",
                    "patientVoice": "这里，中间偏左边一点",
                    "importance": "critical",
                    "category": "hpi"
                },
                {
                    "id": "hpi_radiation",
                    "field": "放射痛",
                    "answer": "左肩膀和左手臂内侧也疼",
                    "patientVoice": "左边肩膀和手臂里面也疼，酸酸的",
                    "importance": "critical",
                    "category": "hpi"
                },
                {
                    "id": "hpi_severity",
                    "field": "疼痛程度",
                    "answer": "7-8分（满分10分）",
                    "patientVoice": "挺疼的，七八分吧，受不了",
                    "importance": "important",
                    "category": "hpi"
                },
                {
                    "id": "hpi_aggravating",
                    "field": "加重因素",
                    "answer": "活动时加重，深呼吸也加重",
                    "patientVoice": "动一动就更疼，深呼吸也疼",
                    "importance": "important",
                    "category": "hpi"
                },
                {
                    "id": "hpi_relieving",
                    "field": "缓解因素",
                    "answer": "休息稍微好一点，但没有完全缓解",
                    "patientVoice": "坐着不动稍微好一点点，但还是疼",
                    "importance": "important",
                    "category": "hpi"
                },
                {
                    "id": "hpi_associated",
                    "field": "伴随症状",
                    "answer": "出汗、恶心、胸闷",
                    "patientVoice": "出了一身冷汗，还有点恶心，喘不上气",
                    "importance": "critical",
                    "category": "hpi"
                },
                {
                    "id": "hpi_previous",
                    "field": "既往发作",
                    "answer": "以前没有过这种情况",
                    "patientVoice": "以前没有过，第一次这样",
                    "importance": "important",
                    "category": "hpi"
                }
            ],
            "pastMedical": [
                {
                    "id": "pmh_hypertension",
                    "field": "高血压",
                    "answer": "有高血压10年，吃氨氯地平",
                    "patientVoice": "有高血压，十几年了，一直在吃药",
                    "importance": "important",
                    "category": "pmh"
                },
                {
                    "id": "pmh_diabetes",
                    "field": "糖尿病",
                    "answer": "有糖尿病5年，吃二甲双胍",
                    "patientVoice": "还有糖尿病，吃二甲双胍",
                    "importance": "important",
                    "category": "pmh"
                },
                {
                    "id": "pmh_hyperlipidemia",
                    "field": "高脂血症",
                    "answer": "有高血脂，吃阿托伐他汀",
                    "patientVoice": "血脂也高，吃降脂药",
                    "importance": "important",
                    "category": "pmh"
                },
                {
                    "id": "pmh_surgery",
                    "field": "手术史",
                    "answer": "无手术史",
                    "patientVoice": "没做过手术",
                    "importance": "optional",
                    "category": "pmh"
                }
            ],
            "medications": [
                {
                    "id": "med_current",
                    "field": "当前用药",
                    "answer": "氨氯地平5mg qd，二甲双胍500mg bid，阿托伐他汀20mg qn",
                    "patientVoice": "氨氯地平、二甲双胍、阿托伐他汀，每天都吃",
                    "importance": "important",
                    "category": "med"
                }
            ],
            "allergies": [
                {
                    "id": "allergy",
                    "field": "过敏史",
                    "answer": "无已知过敏",
                    "patientVoice": "没有过敏的",
                    "importance": "important",
                    "category": "allergy"
                }
            ],
            "social": [
                {
                    "id": "social_smoking",
                    "field": "吸烟史",
                    "answer": "吸烟30年，每天1包，未戒烟",
                    "patientVoice": "抽了三十年了，一天一包",
                    "importance": "important",
                    "category": "social"
                },
                {
                    "id": "social_alcohol",
                    "field": "饮酒史",
                    "answer": "偶尔饮酒",
                    "patientVoice": "偶尔喝点酒",
                    "importance": "optional",
                    "category": "social"
                }
            ],
            "family": [
                {
                    "id": "family_history",
                    "field": "家族史",
                    "answer": "父亲有冠心病，60岁心梗去世",
                    "patientVoice": "我爸有心脏病，六十岁的时候心梗走的",
                    "importance": "important",
                    "category": "family"
                }
            ]
        },
        "physicalExam": {
            "vital_signs": {
                "findings": [
                    {"name": "血压", "value": "150/95 mmHg", "isAbnormal": true, "significance": "偏高"},
                    {"name": "心率", "value": "102次/分", "isAbnormal": true, "significance": "偏快"},
                    {"name": "呼吸", "value": "22次/分", "isAbnormal": true, "significance": "偏快"},
                    {"name": "体温", "value": "36.8°C", "isAbnormal": false},
                    {"name": "血氧", "value": "96%", "isAbnormal": false}
                ]
            },
            "cardiovascular": {
                "findings": [
                    {"name": "心率", "value": "102次/分", "isAbnormal": true, "significance": "窦性心动过速"},
                    {"name": "心律", "value": "齐", "isAbnormal": false},
                    {"name": "心音", "value": "S1、S2正常，可闻及S4奔马律", "isAbnormal": true, "significance": "S4奔马律提示心室顺应性下降"},
                    {"name": "杂音", "value": "未闻及杂音", "isAbnormal": false}
                ]
            },
            "respiratory": {
                "findings": [
                    {"name": "呼吸音", "value": "双肺呼吸音清", "isAbnormal": false},
                    {"name": "啰音", "value": "双肺底可闻及少量湿啰音", "isAbnormal": true, "significance": "可能合并轻度心功能不全"}
                ]
            },
            "abdominal": {
                "findings": [
                    {"name": "腹部", "value": "软，无压痛，无反跳痛", "isAbnormal": false}
                ]
            },
            "extremities": {
                "findings": [
                    {"name": "水肿", "value": "双下肢无水肿", "isAbnormal": false}
                ]
            }
        },
        "investigations": {
            "ecg": {
                "testName": "心电图",
                "result": "窦性心律，心率100bpm。V1-V4导联ST段弓背向上抬高0.2-0.4mV，III导联ST段压低。",
                "interpretation": "前壁急性ST段抬高型心肌梗死",
                "flag": "critical_high"
            },
            "troponin": {
                "testName": "肌钙蛋白I",
                "result": "2.8",
                "unit": "ng/mL",
                "reference": "<0.04",
                "flag": "critical_high"
            },
            "bnp": {
                "testName": "BNP",
                "result": "580",
                "unit": "pg/mL",
                "reference": "<100",
                "flag": "high"
            },
            "cbc": {
                "testName": "血常规",
                "result": "WBC 12.5×10⁹/L↑, Hb 142g/L, PLT 220×10⁹/L",
                "interpretation": "白细胞轻度升高，应激反应",
                "flag": "abnormal"
            },
            "bmp": {
                "testName": "生化",
                "result": "Cr 95μmol/L, K+ 4.2mmol/L, Na+ 140mmol/L, Glu 8.5mmol/L↑",
                "interpretation": "血糖偏高",
                "flag": "abnormal"
            },
            "coagulation": {
                "testName": "凝血功能",
                "result": "PT 12.5s, APTT 32s, INR 1.0",
                "flag": "normal"
            },
            "chest_xray": {
                "testName": "胸片",
                "result": "心影不大，双肺纹理增粗，双肺底可见少许渗出",
                "interpretation": "轻度肺淤血",
                "flag": "abnormal"
            }
        }
    }',

    -- ground_truth (Layer 1)
    '{
        "diagnosis": {
            "primary": "急性前壁ST段抬高型心肌梗死",
            "primaryAliases": ["STEMI", "急性前壁心梗", "ST段抬高型心肌梗死", "急性心肌梗死", "心梗"],
            "icd10": "I21.0"
        },
        "differentials": [
            {
                "diagnosis": "主动脉夹层",
                "aliases": ["夹层", "主动脉夹层动脉瘤"],
                "keyDiscriminator": "疼痛性质为压榨样而非撕裂样，无双上肢血压不对称",
                "mustExclude": true,
                "supportAgainst": "against"
            },
            {
                "diagnosis": "肺栓塞",
                "aliases": ["PE", "肺动脉栓塞"],
                "keyDiscriminator": "无下肢DVT风险因素，无突发呼吸困难",
                "mustExclude": true,
                "supportAgainst": "against"
            },
            {
                "diagnosis": "心包炎",
                "aliases": ["急性心包炎"],
                "keyDiscriminator": "无发热，疼痛性质为压榨样而非锐痛",
                "mustExclude": false,
                "supportAgainst": "against"
            },
            {
                "diagnosis": "胃食管反流",
                "aliases": ["GERD", "反流性食管炎"],
                "keyDiscriminator": "疼痛与进食无关，有放射痛，心电图ST段抬高",
                "mustExclude": false,
                "supportAgainst": "against"
            }
        ],
        "criticalEvidence": {
            "forDiagnosis": {
                "fromHistory": [
                    "胸骨后压榨样胸痛",
                    "放射至左肩左臂",
                    "伴出汗、恶心",
                    "持续不缓解",
                    "高血压、糖尿病、吸烟、冠心病家族史"
                ],
                "fromExam": [
                    "心率快",
                    "S4奔马律",
                    "双肺底湿啰音"
                ],
                "fromTests": [
                    "V1-V4 ST段弓背向上抬高",
                    "肌钙蛋白I显著升高",
                    "BNP升高"
                ]
            }
        },
        "treatment": {
            "immediate": [
                {"action": "阿司匹林 300mg 嚼服", "isCritical": true, "aliases": ["拜阿司匹林", "ASA"]},
                {"action": "P2Y12受体拮抗剂负荷剂量", "isCritical": true, "aliases": ["氯吡格雷", "替格瑞洛", "波立维"]},
                {"action": "普通肝素抗凝", "isCritical": true, "aliases": ["肝素", "抗凝"]},
                {"action": "急诊PCI", "isCritical": true, "aliases": ["介入治疗", "冠脉介入", "支架", "PCI"]},
                {"action": "吗啡止痛", "isCritical": false, "aliases": ["止痛"]},
                {"action": "吸氧", "isCritical": false, "aliases": ["氧气"]}
            ],
            "definitive": [
                {"action": "他汀类药物", "isCritical": true, "aliases": ["阿托伐他汀", "瑞舒伐他汀", "降脂"]},
                {"action": "β受体阻滞剂", "isCritical": true, "aliases": ["美托洛尔", "倍他乐克"]},
                {"action": "ACEI/ARB", "isCritical": true, "aliases": ["依那普利", "缬沙坦"]}
            ],
            "dangerous": [
                {
                    "action": "急性心衰未稳定用β阻滞剂",
                    "penalty": 5,
                    "aliases": []
                },
                {
                    "action": "已做PCI再溶栓",
                    "penalty": 10,
                    "aliases": ["溶栓"]
                },
                {
                    "action": "遗漏急诊PCI",
                    "penalty": 10,
                    "aliases": []
                }
            ]
        }
    }',

    -- scoring_rubric
    '{
        "diagnosis": {
            "weight": 40,
            "exactMatch": 40,
            "partialMatch": 30,
            "categoryMatch": 15,
            "hitDifferential": 8,
            "wrong": 0
        },
        "differential": {
            "weight": 20,
            "threeOrMoreWithReasoning": 20,
            "threeOrMore": 16,
            "two": 12,
            "one": 8,
            "none": 0,
            "missingCritical": -3
        },
        "evidence": {
            "weight": 20,
            "coverageWeight": 0.5,
            "associationWeight": 0.3,
            "interpretationWeight": 0.2
        },
        "treatment": {
            "weight": 20,
            "criticalCoverageWeight": 0.4,
            "safetyWeight": 0.3,
            "reasonablenessWeight": 0.3
        }
    }'
);
