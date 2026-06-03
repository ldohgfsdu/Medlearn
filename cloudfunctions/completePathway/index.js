/**
 * completePathway 云函数
 * 推导链完成记录：保存推导链练习结果
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
  LEARNING_RECORDS: 'learning_records',
  STUDY_ACTIVITIES: 'study_activities'
}

/**
 * 云函数入口
 * @param {Object} event - 云函数事件对象
 * @param {Object} context - 云函数上下文
 */
exports.main = async (event, context) => {
  const { openid, pathwayData } = event

  if (!openid || !pathwayData) {
    return {
      code: -1,
      message: '缺少必要参数',
      data: null
    }
  }

  const { pathwayId, steps, score, duration } = pathwayData

  if (!pathwayId || !steps) {
    return {
      code: -1,
      message: '推导链数据不完整',
      data: null
    }
  }

  try {
    console.log('开始保存推导链完成记录，openid:', openid)

    const timestamp = Date.now()

    // 1. 创建学习记录
    const learningRecord = {
      openid,
      type: 'pathway',
      pathwayId,
      steps,
      score: score || 0,
      duration: duration || 0,
      completedAt: timestamp,
      createdAt: timestamp
    }

    const recordResult = await db.collection(COLLECTIONS.LEARNING_RECORDS).add({
      data: learningRecord
    })

    console.log('学习记录创建成功:', recordResult._id)

    // 2. 创建学习活动记录
    const studyActivity = {
      openid,
      type: 'pathway',
      pathwayId,
      recordId: recordResult._id,
      score: score || 0,
      stepCount: steps.length,
      duration: duration || 0,
      createdAt: timestamp
    }

    await db.collection(COLLECTIONS.STUDY_ACTIVITIES).add({
      data: studyActivity
    })

    console.log('学习活动记录创建成功')

    // 3. 返回保存结果
    return {
      code: 0,
      message: '推导链完成记录保存成功',
      data: {
        recordId: recordResult._id,
        pathwayId,
        score: score || 0,
        stepCount: steps.length
      }
    }

  } catch (err) {
    console.error('completePathway 云函数错误:', err)
    return {
      code: -1,
      message: '推导链完成记录保存失败：' + err.message,
      data: null
    }
  }
}