/**
 * analytics 云函数
 * 数据分析：计算学习统计和薄弱知识点
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
  FEYNMAN_RECORDS: 'feynman_records',
  EXAM_RECORDS: 'exam_records',
  WRONG_QUESTIONS: 'wrong_questions',
  STUDY_ACTIVITIES: 'study_activities',
  SPACED_REPETITION: 'spaced_repetition',
  KNOWLEDGE_NODES: 'knowledge_nodes'
}

/**
 * 计算掌握度分布
 * @param {Array} feynmanRecords - 费曼复述记录
 * @returns {Object} 掌握度分布
 */
function calculateMasteryDistribution(feynmanRecords) {
  const distribution = {
    excellent: 0,  // 90-100
    good: 0,       // 70-89
    fair: 0,       // 50-69
    poor: 0,       // 30-49
    veryPoor: 0    // 0-29
  }

  const nodeScores = {}

  // 按知识点聚合分数
  for (const record of feynmanRecords) {
    const { nodeId, aiScore } = record
    if (!nodeId || !aiScore) continue

    const avgScore = (
      (aiScore.accuracy || 0) +
      (aiScore.completeness || 0) +
      (aiScore.clarity || 0) +
      (aiScore.depth || 0)
    ) / 4

    if (!nodeScores[nodeId] || record.createdAt > nodeScores[nodeId].createdAt) {
      nodeScores[nodeId] = { score: avgScore, createdAt: record.createdAt }
    }
  }

  // 统计分布
  for (const nodeId of Object.keys(nodeScores)) {
    const score = nodeScores[nodeId].score
    if (score >= 90) distribution.excellent++
    else if (score >= 70) distribution.good++
    else if (score >= 50) distribution.fair++
    else if (score >= 30) distribution.poor++
    else distribution.veryPoor++
  }

  return distribution
}

/**
 * 计算薄弱知识点
 * @param {Array} feynmanRecords - 费曼复述记录
 * @param {Array} wrongQuestions - 错题记录
 * @returns {Array} 薄弱知识点列表
 */
function calculateWeakPoints(feynmanRecords, wrongQuestions) {
  const nodeScores = {}

  // 从费曼复述记录计算平均分
  for (const record of feynmanRecords) {
    const { nodeId, aiScore } = record
    if (!nodeId || !aiScore) continue

    const avgScore = (
      (aiScore.accuracy || 0) +
      (aiScore.completeness || 0) +
      (aiScore.clarity || 0) +
      (aiScore.depth || 0)
    ) / 4

    if (!nodeScores[nodeId]) {
      nodeScores[nodeId] = {
        feynmanScores: [],
        wrongCount: 0,
        totalAttempts: 0
      }
    }

    nodeScores[nodeId].feynmanScores.push(avgScore)
    nodeScores[nodeId].totalAttempts++
  }

  // 从错题记录计算错误次数
  for (const wrong of wrongQuestions) {
    const { nodeId } = wrong
    if (!nodeId) continue

    if (!nodeScores[nodeId]) {
      nodeScores[nodeId] = {
        feynmanScores: [],
        wrongCount: 0,
        totalAttempts: 0
      }
    }

    nodeScores[nodeId].wrongCount++
    nodeScores[nodeId].totalAttempts++
  }

  // 计算薄弱知识点（平均分 < 60 或错误率 > 30%）
  const weakPoints = []

  for (const [nodeId, data] of Object.entries(nodeScores)) {
    const avgFeynmanScore = data.feynmanScores.length > 0
      ? data.feynmanScores.reduce((a, b) => a + b, 0) / data.feynmanScores.length
      : 0

    const errorRate = data.totalAttempts > 0
      ? data.wrongCount / data.totalAttempts
      : 0

    if (avgFeynmanScore < 60 || errorRate > 0.3) {
      weakPoints.push({
        nodeId,
        avgFeynmanScore: Math.round(avgFeynmanScore),
        wrongCount: data.wrongCount,
        totalAttempts: data.totalAttempts,
        errorRate: Math.round(errorRate * 100)
      })
    }
  }

  // 按薄弱程度排序
  weakPoints.sort((a, b) => {
    const scoreA = a.avgFeynmanScore * (1 - a.errorRate)
    const scoreB = b.avgFeynmanScore * (1 - b.errorRate)
    return scoreA - scoreB
  })

  return weakPoints.slice(0, 20) // 返回前20个最薄弱的知识点
}

/**
 * 计算学习活动时间线
 * @param {Array} activities - 学习活动记录
 * @returns {Array} 最近7天的学习活动
 */
function calculateActivityTimeline(activities) {
  const now = new Date()
  const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)

  // 过滤最近7天的活动
  const recentActivities = activities.filter(activity => {
    return activity.createdAt >= sevenDaysAgo.getTime()
  })

  // 按日期分组
  const timeline = {}
  for (let i = 0; i < 7; i++) {
    const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000)
    const dateStr = date.toISOString().split('T')[0]
    timeline[dateStr] = {
      date: dateStr,
      count: 0,
      duration: 0,
      types: {}
    }
  }

  // 统计每天的学习活动
  for (const activity of recentActivities) {
    const date = new Date(activity.createdAt)
    const dateStr = date.toISOString().split('T')[0]

    if (timeline[dateStr]) {
      timeline[dateStr].count++
      timeline[dateStr].duration += activity.duration || 0

      const type = activity.type || 'unknown'
      timeline[dateStr].types[type] = (timeline[dateStr].types[type] || 0) + 1
    }
  }

  // 转换为数组并按日期排序
  return Object.values(timeline).sort((a, b) => a.date.localeCompare(b.date))
}

/**
 * 计算连续学习天数
 * @param {Array} activities - 学习活动记录
 * @returns {number} 连续学习天数
 */
function calculateStreakDays(activities) {
  if (activities.length === 0) return 0

  // 获取所有学习日期（去重）
  const studyDates = new Set()
  for (const activity of activities) {
    const date = new Date(activity.createdAt)
    const dateStr = date.toISOString().split('T')[0]
    studyDates.add(dateStr)
  }

  // 从今天开始往前计算连续天数
  const now = new Date()
  let streak = 0

  for (let i = 0; i < 365; i++) {
    const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000)
    const dateStr = date.toISOString().split('T')[0]

    if (studyDates.has(dateStr)) {
      streak++
    } else {
      // 如果今天还没有学习记录，不算中断
      if (i === 0) continue
      break
    }
  }

  return streak
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
    console.log('开始计算学习统计，openid:', openid)

    // 1. 获取费曼复述记录
    const feynmanResult = await db.collection(COLLECTIONS.FEYNMAN_RECORDS)
      .where({ openid })
      .orderBy('createdAt', 'desc')
      .limit(1000)
      .get()

    const feynmanRecords = feynmanResult.data
    console.log('费曼复述记录数:', feynmanRecords.length)

    // 2. 获取错题记录
    const wrongResult = await db.collection(COLLECTIONS.WRONG_QUESTIONS)
      .where({ openid })
      .get()

    const wrongQuestions = wrongResult.data
    console.log('错题记录数:', wrongQuestions.length)

    // 3. 获取学习活动记录
    const activityResult = await db.collection(COLLECTIONS.STUDY_ACTIVITIES)
      .where({ openid })
      .orderBy('createdAt', 'desc')
      .limit(1000)
      .get()

    const activities = activityResult.data
    console.log('学习活动记录数:', activities.length)

    // 4. 计算掌握度分布
    const masteryDistribution = calculateMasteryDistribution(feynmanRecords)
    console.log('掌握度分布:', masteryDistribution)

    // 5. 计算薄弱知识点
    const weakPoints = calculateWeakPoints(feynmanRecords, wrongQuestions)
    console.log('薄弱知识点数:', weakPoints.length)

    // 6. 计算学习活动时间线
    const activityTimeline = calculateActivityTimeline(activities)
    console.log('学习活动时间线:', activityTimeline.length, '天')

    // 7. 计算连续学习天数
    const streakDays = calculateStreakDays(activities)
    console.log('连续学习天数:', streakDays)

    // 8. 计算本周费曼复述完成数
    const now = new Date()
    const weekStart = new Date(now.getTime() - now.getDay() * 24 * 60 * 60 * 1000)
    weekStart.setHours(0, 0, 0, 0)

    const weeklyFeynmanCount = feynmanRecords.filter(record => {
      return record.createdAt >= weekStart.getTime()
    }).length

    console.log('本周费曼复述完成数:', weeklyFeynmanCount)

    // 9. 计算今日待复习知识点数
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const todayEnd = new Date(today.getTime() + 24 * 60 * 60 * 1000)

    const spacedRepetitionResult = await db.collection(COLLECTIONS.SPACED_REPETITION)
      .where({
        openid,
        nextReview: _.lte(todayEnd.getTime())
      })
      .count()

    const todayReviewCount = spacedRepetitionResult.total
    console.log('今日待复习知识点数:', todayReviewCount)

    // 10. 返回统计结果
    return {
      code: 0,
      message: '统计计算成功',
      data: {
        masteryDistribution,
        weakPoints,
        activityTimeline,
        streakDays,
        weeklyFeynmanCount,
        todayReviewCount,
        totalFeynmanCount: feynmanRecords.length,
        totalWrongCount: wrongQuestions.length,
        totalActivityCount: activities.length
      }
    }

  } catch (err) {
    console.error('analytics 云函数错误:', err)
    return {
      code: -1,
      message: '统计计算失败：' + err.message,
      data: null
    }
  }
}