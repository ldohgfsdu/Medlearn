# AGENT.md - MedLearn 移动应用开发规则

**版本**: 2.0  
**创建日期**: 2026-06-03  
**更新日期**: 2026-06-03  
**项目**: MedLearn - AI 驱动的医学思维训练移动应用

---

## 技术栈决策（重要变更）

> **变更说明**: 原计划使用微信小程序 + 云开发，因云开发收费政策调整，改为 APK + Supabase 方案。

### 新技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| **前端框架** | Taro 4 + React 18 | 编译为 H5（网页应用） |
| **打包方式** | Capacitor | 将 H5 打包为 Android APK |
| **后端服务** | Supabase | 免费额度：500MB 数据库、1GB 存储 |
| **数据库** | PostgreSQL (Supabase) | 替代微信云数据库 |
| **认证** | Supabase Auth | 替代微信登录 |
| **存储** | Supabase Storage | 替代微信云存储 |

### 免费额度对比

| 资源 | 微信云开发 | Supabase |
|------|-----------|----------|
| 数据库存储 | 2GB | 500MB |
| 文件存储 | 5GB | 1GB |
| 月活用户 | - | 50,000 |
| 数据库行数 | - | 无限 |
| API 请求 | 按量计费 | 免费 |

---

## 核心开发规则

### 硬性规则

1. **所有代码修改必须围绕移动应用开发逻辑**
   - 使用 Taro 4 + React 18 + TypeScript 技术栈
   - 编译目标为 H5，通过 Capacitor 打包为 APK
   - 后端使用 Supabase 替代微信云开发

2. **技术栈约束**
   - 前端框架：Taro 4.x + React 18.x
   - 语言：TypeScript 5.x（严格模式）
   - 样式：SCSS Modules
   - 构建：Webpack5
   - 后端：Supabase（PostgreSQL + Auth + Storage）
   - 打包：Capacitor (Android)

3. **代码组织规范**
   - 遵循 `src/` 目录结构规范
   - 页面文件放在 `pages/`
   - 通用组件放在 `components/common/`
   - 服务层代码放在 `services/`
   - Supabase 相关代码放在 `lib/supabase/`
   - 类型定义放在 `types/`
   - 常量定义放在 `constants/`

4. **数据交互规范**
   - 所有外部数据访问必须经过服务层（`services/`）
   - 使用 Supabase 客户端库操作数据库
   - 使用 `useSupabaseQuery` Hook 处理数据查询
   - 实现本地缓存策略减少 API 调用

5. **AI 调用规范**
   - V1.0 阶段采用客户端直连方式
   - 所有 AI 调用通过 `services/ai.ts` 封装
   - 支持 Anthropic 和 OpenAI 兼容接口自动检测
   - 实现超时处理：15秒提示、30秒超时

6. **认证规范**
   - 使用 Supabase Auth 实现用户认证
   - 支持邮箱/密码登录和匿名登录
   - 用户数据通过 `user_id` 隔离

7. **医学内容合规**
   - 所有 AI 生成内容必须展示"⚠️ AI 生成内容，不构成医学建议"标识
   - 种子数据必须标注教材来源（sourceReference 字段）
   - VINDICATE 框架定义统一从 `constants/vindicate.ts` 导出

8. **数据安全**
   - 所有数据库查询通过 Row Level Security (RLS) 实现用户数据隔离
   - API Key 加密存储
   - 请求频率限制（每用户每分钟 ≤ 10 次）

---

## Supabase 配置

### 环境变量
```env
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_anon_key
```

### 数据库表结构
- `knowledge_nodes`: 知识点数据
- `exam_questions`: 考试题目
- `causal_chains`: 推导链
- `cases`: 病例
- `user_profiles`: 用户资料
- `feynman_records`: 费曼复述记录
- `dialogue_records`: 对话记录
- `exam_records`: 答题记录
- `exam_sessions`: 考试会话
- `wrong_questions`: 错题
- `spaced_repetition`: 间隔重复计划
- `study_activities`: 学习活动
- `favorites`: 收藏

### Row Level Security (RLS)
所有用户数据表启用 RLS，确保用户只能访问自己的数据。

---

## Capacitor 配置

### 打包 APK 步骤
1. `npm run build:h5` - 编译 H5
2. `npx cap add android` - 添加 Android 平台
3. `npx cap sync` - 同步代码
4. `npx cap open android` - 打开 Android Studio
5. 在 Android Studio 中构建 APK

### 权限配置
- `android.permission.INTERNET`: 网络访问
- `android.permission.RECORD_AUDIO`: 语音输入（P1）

---

## 开发检查清单

### 代码修改前
- [ ] 确认修改符合 Taro 4 + React 18 + TypeScript 技术栈
- [ ] 确认修改兼容 H5 编译目标
- [ ] 确认 Supabase 查询使用 RLS

### 代码修改后
- [ ] 运行 TypeScript 类型检查
- [ ] 运行 ESLint 代码规范检查
- [ ] 验证 H5 编译成功
- [ ] 确保所有 AI 输出区域展示合规标识
- [ ] 确保数据操作经过服务层封装

---

## 参考文档

- [PRD 文档](docs/PRD.md) - 产品需求文档 v2.0
- [技术架构文档](docs/TECHNICAL_ARCHITECTURE.md) - 技术架构文档 v1.0
- [Supabase 文档](https://supabase.com/docs) - Supabase 官方文档
- [Capacitor 文档](https://capacitorjs.com/docs) - Capacitor 官方文档

---

## 更新记录

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2026-06-03 | 2.0 | 技术栈变更：微信小程序 + 云开发 → APK + Supabase |
| 2026-06-03 | 1.0 | 初始版本，建立微信小程序开发规则 |
