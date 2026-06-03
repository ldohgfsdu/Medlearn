/**
 * submitExam 云函数
 * 考试提交事务：原子写入考试记录
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
  EXAM_SESSIONS: 'exam_sessions',
  EXAM_RECORDS: 'exam_records',
  WRONG_QUESTIONS: 'wrong_questions',
  STUDY_ACTIVITIES: 'study_activities'
}

/**
 * 云函数入口
 * @param {Object} event - 云函数事件对象
 * @param {Object} context - 云函数上下文
 */
exports.main = async (event, context) => {
  const { openid, examData } = event

  if (!openid || !examData) {
    return {
      code: -1,
      message: '缺少必要参数',
      data: null
    }
  }

  const { questionIds, answers, score, weakNodes } = examData

  if (!questionIds || !answers || score === undefined) {
    return {
      code: -1,
      message: '考试数据不完整',
      data: null
    }
  }

  try {
    console.log('开始提交考试记录，openid:', openid)

    const timestamp = Date.now()

    // 1. 创建考试会话记录
    const examSession = {
      openid,
      questionIds,
      score,
      weakNodes: weakNodes || [],
      createdAt: timestamp,
      updatedAt: timestamp
    }

    const sessionResult = await db.collection(COLLECTIONS.EXAM_SESSIONS).add({
      data: examSession
    })

    console.log('考试会话创建成功:', sessionResult._id)

    // 2. 创建每题答题记录
    const examRecords = []
    const wrongQuestions = []

    for (const answer of answers) {
      const record = {
        openid,
        sessionId: sessionResult._id,
        questionId: answer.questionId,
        userAnswer: answer.userAnswer,
        isCorrect: answer.isCorrect,
        createdAt: timestamp
      }

      examRecords.push(record)

      // 如果答错，添加到错题本
      if (!answer.isCorrect) {
        wrongQuestions.push({
          openid,
          questionId: answer.questionId,
          nodeId: answer.nodeId || '',
          sessionId: sessionResult._id,
          retryCorrect: false,
          createdAt: timestamp,
          updatedAt: timestamp
        })
      }
    }

    // 批量写入答题记录
    const recordPromises = examRecords.map(record => {
      return db.collection(COLLECTIONS.EXAM_RECORDS).add({ data: record })
    })

    await Promise.all(recordPromises)
    console.log('答题记录写入成功:', examRecords.length, '条')

    // 3. 批量写入错题记录
    if (wrongQuestions.length > 0) {
      const wrongPromises = wrongQuestions.map(wrong => {
        return db.collection(COLLECTIONS.WRONG_QUESTIONS).add({ data: wrong })
      })

      await Promise.all(wrongPromises)
      console.log('错题记录写入成功:', wrongQuestions.length, '条')
    }

    // 4. 创建学习活动记录
    const studyActivity = {
      openid,
      type: 'exam',
      sessionId: sessionResult._id,
      score,
      questionCount: questionIds.length,
      correctCount: answers.filter(a => a.isCorrect).length,
      wrongCount: wrongQuestions.length,
      duration: examData.duration || 0,
      createdAt: timestamp
    }

    await db.collection(COLLECTIONS.STUDY_ACTIVITIES).add({
      data: studyActivity
    })

    console.log('学习活动记录创建成功')

    // 5. 返回提交结果
    return {
      code: 0,
      message: '考试提交成功',
      data: {
        sessionId: sessionResult._id,
        score,
        totalQuestions: questionIds.length,
        correctCount: answers.filter(a => a.isCorrect).length,
        wrongCount: wrongQuestions.length,
        weakNodes: weakNodes || []
      }
    }

  } catch (err) {
    console.error('submitExam 云函数错误:', err)
    return {
      code: -1,
      message: '考试提交失败：' + err.message,
      data: null
    }
  }
}