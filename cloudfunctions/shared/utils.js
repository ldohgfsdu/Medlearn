/**
 * 云函数共享工具模块
 */

const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()
const _ = db.command

/**
 * 集合名称常量
 */
const COLLECTIONS = {
  KNOWLEDGE_NODES: 'knowledge_nodes',
  EXAM_QUESTIONS: 'exam_questions',
  CAUSAL_CHAINS: 'causal_chains',
  CASES: 'cases',
  LEARNING_RECORDS: 'learning_records',
  FEYNMAN_RECORDS: 'feynman_records',
  DIALOGUE_RECORDS: 'dialogue_records',
  CASE_RECORDS: 'case_records',
  EXAM_RECORDS: 'exam_records',
  EXAM_SESSIONS: 'exam_sessions',
  WRONG_QUESTIONS: 'wrong_questions',
  SPACED_REPETITION: 'spaced_repetition',
  STUDY_ACTIVITIES: 'study_activities',
  FAVORITES: 'favorites',
  SETTINGS: 'settings',
  LEARNING_PATHS: 'learning_paths',
  STUDY_PLANS: 'study_plans',
  STUDY_GOALS: 'study_goals'
}

/**
 * 从云函数事件中获取 openid
 * @param {Object} event - 云函数事件对象
 * @returns {string} openid
 */
function getOpenId(event) {
  const openid = event.userInfo && event.userInfo.openId
  if (!openid) {
    throw new Error('无法获取用户身份信息，请重新登录')
  }
  return openid
}

/**
 * 标准化响应格式
 * @param {number} code - 状态码，0 表示成功
 * @param {string} message - 消息
 * @param {*} data - 数据
 * @returns {Object}
 */
function formatResponse(code, message, data = null) {
  const response = { code, message }
  if (data !== null) {
    response.data = data
  }
  return response
}

/**
 * 成功响应
 */
function success(data = null, message = '操作成功') {
  return formatResponse(0, message, data)
}

/**
 * 失败响应
 */
function fail(message = '操作失败', code = -1) {
  return formatResponse(code, message)
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
    } catch (err) {
      console.error(`批次 ${i + 1} 写入失败:`, err)
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

module.exports = {
  cloud,
  db,
  _,
  COLLECTIONS,
  getOpenId,
  success,
  fail,
  formatResponse,
  batchAdd,
  hasData
}