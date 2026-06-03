/**
 * saveGeneratedContent 云函数
 * AI生成内容保存：保存AI生成的病例和推导链
 */

const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

/**
 * 集合名称常量
 */
const COLLECTIONS = {
  CASES: 'cases',
  CAUSAL_CHAINS: 'causal_chains',
  STUDY_ACTIVITIES: 'study_activities'
}

/**
 * 保存AI生成的病例
 * @param {Object} event - 云函数事件对象
 * @returns {Object} 保存结果
 */
async function saveGeneratedCase(event) {
  const { openid, caseData } = event

  if (!caseData) {
    throw new Error('缺少病例数据')
  }

  const {
    title,
    chiefComplaint,
    stages,
    difficulty,
    relatedNodes
  } = caseData

  if (!title || !chiefComplaint || !stages) {
    throw new Error('病例数据不完整')
  }

  const timestamp = Date.now()

  // 创建病例记录
  const caseRecord = {
    title,
    chiefComplaint,
    stages,
    difficulty: difficulty || 1,
    relatedNodes: relatedNodes || [],
    source: 'ai-generated',
    creatorOpenid: openid,
    createdAt: timestamp,
    updatedAt: timestamp
  }

  const result = await db.collection(COLLECTIONS.CASES).add({
    data: caseRecord
  })

  console.log('AI生成病例保存成功:', result._id)

  // 创建学习活动记录
  await db.collection(COLLECTIONS.STUDY_ACTIVITIES).add({
    data: {
      openid,
      type: 'case_generate',
      caseId: result._id,
      createdAt: timestamp
    }
  })

  return {
    caseId: result._id,
    title,
    source: 'ai-generated'
  }
}

/**
 * 保存AI生成的推导链
 * @param {Object} event - 云函数事件对象
 * @returns {Object} 保存结果
 */
async function saveGeneratedPathway(event) {
  const { openid, pathwayData } = event

  if (!pathwayData) {
    throw new Error('缺少推导链数据')
  }

  const {
    title,
    steps,
    relatedNodes,
    difficulty
  } = pathwayData

  if (!title || !steps) {
    throw new Error('推导链数据不完整')
  }

  const timestamp = Date.now()

  // 创建推导链记录
  const pathwayRecord = {
    title,
    steps,
    relatedNodes: relatedNodes || [],
    difficulty: difficulty || 1,
    source: 'ai-generated',
    creatorOpenid: openid,
    createdAt: timestamp,
    updatedAt: timestamp
  }

  const result = await db.collection(COLLECTIONS.CAUSAL_CHAINS).add({
    data: pathwayRecord
  })

  console.log('AI生成推导链保存成功:', result._id)

  // 创建学习活动记录
  await db.collection(COLLECTIONS.STUDY_ACTIVITIES).add({
    data: {
      openid,
      type: 'pathway_generate',
      pathwayId: result._id,
      createdAt: timestamp
    }
  })

  return {
    pathwayId: result._id,
    title,
    source: 'ai-generated'
  }
}

/**
 * 云函数入口
 * @param {Object} event - 云函数事件对象
 * @param {Object} context - 云函数上下文
 */
exports.main = async (event, context) => {
  const { openid, contentType } = event

  if (!openid || !contentType) {
    return {
      code: -1,
      message: '缺少必要参数',
      data: null
    }
  }

  try {
    console.log('开始保存AI生成内容，openid:', openid, '类型:', contentType)

    let result = null

    // 根据内容类型调用不同的保存函数
    switch (contentType) {
      case 'case':
        result = await saveGeneratedCase(event)
        break

      case 'pathway':
        result = await saveGeneratedPathway(event)
        break

      default:
        throw new Error(`不支持的内容类型: ${contentType}`)
    }

    // 返回保存结果
    return {
      code: 0,
      message: 'AI生成内容保存成功',
      data: {
        contentType,
        ...result
      }
    }

  } catch (err) {
    console.error('saveGeneratedContent 云函数错误:', err)
    return {
      code: -1,
      message: 'AI生成内容保存失败：' + err.message,
      data: null
    }
  }
}