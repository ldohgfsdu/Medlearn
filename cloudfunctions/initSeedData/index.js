/**
 * initSeedData 云函数
 * 首次登录时初始化种子数据到云数据库
 */

const cloud = require('wx-server-sdk')
const fs = require('fs')
const path = require('path')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

/**
 * 集合名称常量
 */
const COLLECTIONS = {
  KNOWLEDGE_NODES: 'knowledge_nodes',
  EXAM_QUESTIONS: 'exam_questions',
  CAUSAL_CHAINS: 'causal_chains',
  CASES: 'cases'
}

/**
 * 批量写入数据（每批最多 20 条，云数据库限制）
 * @param {string} collectionName - 集合名称
 * @param {Array} dataList - 数据列表
 * @returns {Object} 写入结果
 */
async function batchAdd(collectionName, dataList) {
  const batchSize = 20
  const totalBatches = Math.ceil(dataList.length / batchSize)
  let successCount = 0
  let failCount = 0

  for (let i = 0; i < totalBatches; i++) {
    const batch = dataList.slice(i * batchSize, (i + 1) * batchSize)
    try {
      // 使用 Promise.all 并行写入当前批次
      const tasks = batch.map(item => {
        return db.collection(collectionName).add({ data: item })
      })
      await Promise.all(tasks)
      successCount += batch.length
      console.log(`批次 ${i + 1}/${totalBatches} 写入成功: ${batch.length} 条`)
    } catch (err) {
      console.error(`批次 ${i + 1}/${totalBatches} 写入失败:`, err)
      failCount += batch.length
    }
  }

  return {
    total: dataList.length,
    success: successCount,
    fail: failCount,
    batches: totalBatches
  }
}

/**
 * 检查集合是否已有数据
 * @param {string} collectionName - 集合名称
 * @param {Object} conditions - 查询条件
 * @returns {boolean}
 */
async function hasData(collectionName, conditions = {}) {
  try {
    const countResult = await db.collection(collectionName)
      .where(conditions)
      .count()
    return countResult.total > 0
  } catch (err) {
    console.error(`检查集合 ${collectionName} 数据失败:`, err)
    return false
  }
}

/**
 * 读取种子数据文件
 * @param {string} filename - 文件名
 * @returns {Array} 数据数组
 */
function readSeedDataFile(filename) {
  try {
    const filePath = path.join(__dirname, 'data', filename)
    const data = fs.readFileSync(filePath, 'utf-8')
    return JSON.parse(data)
  } catch (err) {
    console.error(`读取文件 ${filename} 失败:`, err)
    return []
  }
}

/**
 * 云函数入口
 * @param {Object} event - 云函数事件对象
 * @param {Object} context - 云函数上下文
 */
exports.main = async (event, context) => {
  const { openid } = event

  if (!openid) {
    return {
      code: -1,
      message: '缺少 openid 参数',
      data: null
    }
  }

  try {
    console.log('开始初始化种子数据，openid:', openid)

    // 1. 检查是否已有数据
    const hasKnowledgeNodes = await hasData(COLLECTIONS.KNOWLEDGE_NODES)
    if (hasKnowledgeNodes) {
      console.log('知识节点数据已存在，跳过初始化')
      return {
        code: 0,
        message: '种子数据已存在，无需初始化',
        data: {
          alreadyExists: true
        }
      }
    }

    // 2. 读取并初始化知识节点数据
    console.log('开始初始化知识节点数据...')
    const manifest = readSeedDataFile('manifest.json')
    if (!manifest || !manifest.chunks) {
      throw new Error('无法读取种子数据清单文件')
    }

    let totalNodes = 0
    let successNodes = 0
    let failNodes = 0

    // 逐个读取并写入数据块
    for (let i = 0; i < manifest.chunks.length; i++) {
      const chunkFile = manifest.chunks[i]
      console.log(`处理数据块 ${i + 1}/${manifest.chunks.length}: ${chunkFile}`)

      const nodes = readSeedDataFile(chunkFile)
      if (nodes.length === 0) {
        console.warn(`数据块 ${chunkFile} 为空，跳过`)
        continue
      }

      // 添加时间戳
      const timestamp = Date.now()
      const nodesWithTimestamp = nodes.map(node => ({
        ...node,
        createdAt: timestamp,
        updatedAt: timestamp,
        generatedAt: timestamp
      }))

      // 批量写入
      const result = await batchAdd(COLLECTIONS.KNOWLEDGE_NODES, nodesWithTimestamp)
      totalNodes += result.total
      successNodes += result.success
      failNodes += result.fail

      console.log(`数据块 ${chunkFile} 写入完成: 成功 ${result.success}, 失败 ${result.fail}`)
    }

    // 3. 初始化考试题目数据（占位符）
    console.log('开始初始化考试题目数据...')
    const examQuestions = [
      {
        id: 'exam-001',
        type: 'single',
        question: '急性上呼吸道感染最常见的病原体是？',
        options: ['病毒', '细菌', '支原体', '衣原体'],
        answer: 0,
        explanation: '急性上感约70%～80%由病毒引起，最常见的是鼻病毒。',
        relatedNodes: ['textbook-呼吸系统疾病-急性上呼吸道感染和急性气管支气管炎-急性上呼吸道感染'],
        difficulty: 1,
        source: 'seed',
        createdAt: Date.now(),
        updatedAt: Date.now()
      }
    ]

    const examResult = await batchAdd(COLLECTIONS.EXAM_QUESTIONS, examQuestions)
    console.log('考试题目初始化完成:', examResult)

    // 4. 初始化推导链数据（占位符）
    console.log('开始初始化推导链数据...')
    const causalChains = [
      {
        id: 'chain-001',
        title: '上呼吸道感染诊断推理链',
        steps: [
          {
            step: 1,
            description: '患者主诉鼻塞、流涕、咽痛',
            options: ['普通感冒', '过敏性鼻炎', '流行性感冒', '急性咽炎'],
            correct: 0,
            feedback: '普通感冒起病急，主要表现为鼻部症状。'
          },
          {
            step: 2,
            description: '查体：鼻腔黏膜充血、水肿，咽部轻度充血',
            options: ['继续观察', '血常规检查', '胸部X线', '病原学检查'],
            correct: 1,
            feedback: '血常规可帮助判断病毒或细菌感染。'
          }
        ],
        relatedNodes: ['textbook-呼吸系统疾病-急性上呼吸道感染和急性气管支气管炎-急性上呼吸道感染'],
        difficulty: 2,
        source: 'seed',
        createdAt: Date.now(),
        updatedAt: Date.now()
      }
    ]

    const chainResult = await batchAdd(COLLECTIONS.CAUSAL_CHAINS, causalChains)
    console.log('推导链初始化完成:', chainResult)

    // 5. 初始化病例数据（占位符）
    console.log('开始初始化病例数据...')
    const cases = [
      {
        id: 'case-001',
        title: '急性上呼吸道感染病例',
        chiefComplaint: '鼻塞、流涕、咽痛3天',
        stages: [
          {
            stage: 1,
            name: '主诉分析',
            content: '患者，男，25岁，3天前开始出现鼻塞、流清水样鼻涕，伴有咽痛、轻微咳嗽。'
          },
          {
            stage: 2,
            name: '现病史采集',
            content: '患者3天前淋雨后出现症状，无发热，无头痛，无肌肉酸痛。'
          }
        ],
        difficulty: 1,
        source: 'seed',
        createdAt: Date.now(),
        updatedAt: Date.now()
      }
    ]

    const caseResult = await batchAdd(COLLECTIONS.CASES, cases)
    console.log('病例初始化完成:', caseResult)

    // 6. 返回初始化结果
    const result = {
      code: 0,
      message: '种子数据初始化成功',
      data: {
        alreadyExists: false,
        knowledge_nodes: {
          total: totalNodes,
          success: successNodes,
          fail: failNodes
        },
        exam_questions: examResult,
        causal_chains: chainResult,
        cases: caseResult
      }
    }

    console.log('种子数据初始化完成:', result)
    return result

  } catch (err) {
    console.error('initSeedData 云函数错误:', err)
    return {
      code: -1,
      message: '种子数据初始化失败：' + err.message,
      data: null
    }
  }
}