/**
 * initUser 云函数
 * 微信登录：通过 code 换取 openid
 */

const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

/**
 * 云函数入口
 * @param {Object} event - 云函数事件对象
 * @param {Object} context - 云函数上下文
 */
exports.main = async (event, context) => {
  const { code } = event

  try {
    // 1. 通过 code 换取 openid 和 session_key
    const loginResult = await cloud.openapi.auth.code2session({
      appid: event.userInfo && event.userInfo.appId || '',
      code: code,
      grant_type: 'authorization_code'
    })

    if (loginResult.errcode && loginResult.errcode !== 0) {
      console.error('登录失败:', loginResult)
      return {
        code: -1,
        message: '登录失败：' + (loginResult.errmsg || '未知错误'),
        data: null
      }
    }

    const { openid, session_key } = loginResult

    // 2. 检查用户是否已存在
    const userQuery = await db.collection('settings')
      .where({ openid })
      .get()

    let isNewUser = false
    let userData = null

    if (userQuery.data.length === 0) {
      // 3. 新用户：创建用户记录
      isNewUser = true
      const newUser = {
        openid,
        createdAt: db.serverDate(),
        updatedAt: db.serverDate(),
        preferences: {},
        aiConfig: {}
      }

      const addResult = await db.collection('settings').add({
        data: newUser
      })

      userData = {
        _id: addResult._id,
        ...newUser
      }

      console.log('新用户创建成功:', openid)
    } else {
      // 4. 老用户：更新最后登录时间
      userData = userQuery.data[0]
      await db.collection('settings')
        .doc(userData._id)
        .update({
          data: {
            updatedAt: db.serverDate()
          }
        })

      console.log('老用户登录:', openid)
    }

    // 5. 返回登录结果
    return {
      code: 0,
      message: isNewUser ? '注册成功' : '登录成功',
      data: {
        openid,
        isNewUser,
        userId: userData._id
      }
    }

  } catch (err) {
    console.error('initUser 云函数错误:', err)
    return {
      code: -1,
      message: '登录失败：' + err.message,
      data: null
    }
  }
}