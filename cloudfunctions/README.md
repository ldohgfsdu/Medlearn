# MedLearn 微信小程序云函数

本目录包含 MedLearn 微信小程序的所有云函数。

## 云函数列表

### 1. initUser
**功能**: 微信登录云函数，通过 code 换取 openid

**调用方式**:
```javascript
const result = await wx.cloud.callFunction({
  name: 'initUser',
  data: {
    code: loginCode // 从 wx.login() 获取
  }
})
```

**返回数据**:
```javascript
{
  code: 0,
  message: '登录成功',
  data: {
    openid: 'user_openid',
    isNewUser: false,
    userId: 'user_id'
  }
}
```

### 2. initSeedData
**功能**: 种子数据初始化云函数，首次登录时写入种子数据

**调用方式**:
```javascript
const result = await wx.cloud.callFunction({
  name: 'initSeedData',
  data: {
    openid: userOpenid
  }
})
```

**返回数据**:
```javascript
{
  code: 0,
  message: '种子数据初始化成功',
  data: {
    alreadyExists: false,
    knowledge_nodes: { total: 384, success: 384, fail: 0 },
    exam_questions: { total: 1, success: 1, fail: 0 },
    causal_chains: { total: 1, success: 1, fail: 0 },
    cases: { total: 1, success: 1, fail: 0 }
  }
}
```

### 3. submitExam
**功能**: 考试提交事务云函数，原子写入考试记录

**调用方式**:
```javascript
const result = await wx.cloud.callFunction({
  name: 'submitExam',
  data: {
    openid: userOpenid,
    examData: {
      questionIds: ['q1', 'q2', 'q3'],
      answers: [
        { questionId: 'q1', userAnswer: 0, isCorrect: true },
        { questionId: 'q2', userAnswer: 1, isCorrect: false }
      ],
      score: 70,
      weakNodes: ['node1'],
      duration: 300 // 秒
    }
  }
})
```

**返回数据**:
```javascript
{
  code: 0,
  message: '考试提交成功',
  data: {
    sessionId: 'session_id',
    score: 70,
    totalQuestions: 3,
    correctCount: 1,
    wrongCount: 1,
    weakNodes: ['node1']
  }
}
```

### 4. analytics
**功能**: 数据分析云函数，计算学习统计和薄弱知识点

**调用方式**:
```javascript
const result = await wx.cloud.callFunction({
  name: 'analytics',
  data: {
    openid: userOpenid
  }
})
```

**返回数据**:
```javascript
{
  code: 0,
  message: '统计计算成功',
  data: {
    masteryDistribution: { excellent: 10, good: 20, fair: 15, poor: 5, veryPoor: 2 },
    weakPoints: [...],
    activityTimeline: [...],
    streakDays: 7,
    weeklyFeynmanCount: 15,
    todayReviewCount: 5,
    totalFeynmanCount: 100,
    totalWrongCount: 20,
    totalActivityCount: 150
  }
}
```

### 5. completePathway
**功能**: 推导链完成记录云函数

**调用方式**:
```javascript
const result = await wx.cloud.callFunction({
  name: 'completePathway',
  data: {
    openid: userOpenid,
    pathwayData: {
      pathwayId: 'pathway_id',
      steps: [
        { step: 1, userAnswer: 0, isCorrect: true },
        { step: 2, userAnswer: 1, isCorrect: true }
      ],
      score: 100,
      duration: 120 // 秒
    }
  }
})
```

**返回数据**:
```javascript
{
  code: 0,
  message: '推导链完成记录保存成功',
  data: {
    recordId: 'record_id',
    pathwayId: 'pathway_id',
    score: 100,
    stepCount: 2
  }
}
```

### 6. saveGeneratedContent
**功能**: AI生成内容保存云函数

**调用方式**:
```javascript
// 保存AI生成的病例
const result = await wx.cloud.callFunction({
  name: 'saveGeneratedContent',
  data: {
    openid: userOpenid,
    contentType: 'case',
    caseData: {
      title: '病例标题',
      chiefComplaint: '主诉内容',
      stages: [...],
      difficulty: 1,
      relatedNodes: ['node1', 'node2']
    }
  }
})

// 保存AI生成的推导链
const result = await wx.cloud.callFunction({
  name: 'saveGeneratedContent',
  data: {
    openid: userOpenid,
    contentType: 'pathway',
    pathwayData: {
      title: '推导链标题',
      steps: [...],
      relatedNodes: ['node1', 'node2'],
      difficulty: 1
    }
  }
})
```

## 部署步骤

### 1. 安装依赖
在每个云函数目录下执行：
```bash
npm install
```

### 2. 部署云函数
在微信开发者工具中：
1. 右键点击云函数目录
2. 选择"上传并部署：云端安装依赖"

### 3. 配置数据库安全规则
参考 `database-security-rules.json` 文件，在云开发控制台配置数据库安全规则。

### 4. 初始化种子数据
首次部署后，需要调用 `initSeedData` 云函数初始化种子数据。

## 数据库集合

### 静态数据集合（种子数据）
- `knowledge_nodes`: 知识点数据（384条）
- `exam_questions`: 考试题目数据（1条）
- `causal_chains`: 推导链数据（1条）
- `cases`: 病例数据（1条）

### 动态数据集合（用户产生）
- `learning_records`: 学习记录
- `feynman_records`: 费曼复述记录
- `dialogue_records`: 对话记录
- `case_records`: 病例练习记录
- `exam_records`: 答题记录
- `exam_sessions`: 考试会话
- `wrong_questions`: 错题
- `spaced_repetition`: 间隔重复计划
- `study_activities`: 学习活动
- `favorites`: 收藏
- `settings`: 用户设置
- `learning_paths`: 学习路径
- `study_plans`: 学习计划
- `study_goals`: 学习目标

## 注意事项

1. 所有云函数都需要 `openid` 参数用于用户身份验证
2. 静态数据集合只允许云函数写入，客户端只读
3. 动态数据集合只允许数据创建者（openid匹配）读写
4. 种子数据初始化只需执行一次，重复调用会跳过
5. 考试提交使用事务保证数据一致性