# MedLearn 全面优化计划

## Context

MedLearn 是一个医学学习 Electron 桌面应用。经过全面代码审查发现了 30+ 个问题，涵盖安全漏洞、逻辑 Bug、性能瓶颈、架构缺陷和数据质量问题。本次计划按优先级分批修复所有发现的问题。

---

## Phase 1: 关键 Bug 修复（影响功能正确性）

### 1.1 Dashboard `buildLearnedSet` 逻辑反转
- **文件**: `src/pages/Dashboard.tsx:32-42`
- **问题**: `learningRecords` 的 `mistakes`（错误节点）被加入"已学集合"，与 `feynmanRecords` 的正确逻辑相反
- **修复**: 将 filter 改为只取 `r.performance` 中成功的节点，或者直接移除这段逻辑（因为 mistakes 不应该算已学）

### 1.2 DB 升级清除数据 → 改为迁移
- **文件**: `src/db/db.ts:76-79, 92-95`
- **问题**: v5 和 v7 的 upgrade 使用 `.clear()` 清除用户数据
- **修复**: 移除 `.clear()` 调用，保留数据；如果确实需要 reseed，提供手动 reseed 按钮而非自动清除

### 1.3 `useEffect` 依赖导致无限重取
- **文件**: `src/pages/Dashboard.tsx:171-175`
- **问题**: `useLiveQuery` 每次返回新数组引用触发 `useEffect` 重复执行
- **修复**: 将 analytics 数据获取改用 `useLiveQuery` 直接返回或使用 `useMemo`；移除 `feynmanRecords` 等作为 useEffect 依赖

### 1.4 FeynmanDetail cleanup 每帧执行
- **文件**: `src/pages/feynman/FeynmanDetail.tsx:63-65`
- **问题**: `evalHook` 对象每渲染都是新引用，cleanup 在每次渲染执行
- **修复**: 使用 `useRef` 存储 evalHook.reset 引用，或使用空依赖数组配合 ref

### 1.5 `useLearningDialogue` 的 node 非空断言
- **文件**: `src/pages/feynman/FeynmanDetail.tsx:57`, `src/pages/case/CaseDetail.tsx:76`
- **问题**: 在 `node!` / `virtualNode!` 可能为 null 时调用 hook
- **修复**: 将 hook 调用移到条件渲染之后，或用 guard 保护

---

## Phase 2: 安全修复

### 2.1 API Key 安全存储
- **文件**: `src/services/ai.ts`, `electron/preload.js`, `electron/main.js`
- **问题**: API Key 明文存于 localStorage/IndexedDB
- **修复**:
  - `electron/preload.js`: 通过 `contextBridge` 暴露 `electronAPI.encryptData()` / `electronAPI.decryptData()`
  - `electron/main.js`: 使用 `safeStorage` 加密/解密，通过 IPC 通信
  - `src/services/ai.ts`: 在 Electron 环境使用 `window.electronAPI` 加密存储，浏览器环境回退到 localStorage（加警告）
  - **注意**: Dev 模式（浏览器）仍使用 localStorage，但在 UI 加提示

### 2.2 CSP 支持自定义 Base URL
- **文件**: `index.html:7`
- **问题**: `connect-src` 硬编码只允许两个域名
- **修复**: 
  - 移除 `connect-src` 限制或添加 `*`（权衡：允许用户使用任何 API 端点）
  - 同时在 Electron 主进程添加 `webRequest` 过滤器作为额外安全层

### 2.3 Electron 安全增强
- **文件**: `electron/main.js`
- **问题**: 缺少请求过滤和权限管理
- **修复**:
  - 添加 `ses.defaultSession.webRequest` 拦截器记录/限制请求
  - 添加 `permissionRequestHandler` 拒绝不必要的权限
  - 添加 `will-navigate` / `will-redirect` 事件处理防止导航劫持

### 2.4 移除 Vite 默认第三方代理
- **文件**: `vite.config.ts:16-22`
- **问题**: 默认代理到 `api.meai.cloud`
- **修复**: 移除 proxy 配置或改为注释掉的示例；在设置页提示用户配置自己的 API 端点

---

## Phase 3: 性能优化

### 3.1 种子数据懒加载
- **文件**: `src/db/seed.ts`, `src/db/seedKnowledge.ts`, `src/db/extractedKnowledge.ts`
- **问题**: 836KB 种子数据打包进主 bundle
- **修复**: 
  - 将 `extractedKnowledge` 改为 JSON 文件放在 `public/` 目录
  - 在 `initSeedData()` 中改为 `fetch()` 加载 JSON
  - 种子数据的导入改为动态 `import()` 带 loading 状态

### 3.2 FeynmanRecall 分组性能优化
- **文件**: `src/pages/FeynmanRecall.tsx`
- **问题**: `groupedData` 的 `useMemo` 内有多层嵌套循环
- **修复**: 
  - 将过滤逻辑前置（先 filter 再 group）
  - 使用 `Map<string, Map>` 两级索引替代多次 `filter()` 遍历
  - 对小数据集保持当前逻辑，门槛 > 500 条才启用优化路径

### 3.3 知识树添加简单虚拟化
- **文件**: `src/pages/FeynmanRecall.tsx`, `src/components/knowledge/SystemContextPanel.tsx`
- **问题**: 展开所有章节后 DOM 节点过多
- **修复**: 默认折叠非当前章节，限制同时展开数 ≤ 3 个章节；对大列表使用 CSS `content-visibility: auto`

---

## Phase 4: 架构改进

### 4.1 TypeScript 路径别名
- **文件**: `tsconfig.app.json`, `vite.config.ts`
- **修复**:
  - tsconfig: 添加 `"paths": { "@/*": ["./src/*"] }`, `"baseUrl": "."`
  - vite.config: 添加 `resolve.alias` 映射
  - 更新所有源文件的导入路径（自动化批量替换）

### 4.2 移除调试代码
- **文件**: `src/db/seed.ts:26-28`
- **修复**: 删除 `window.__forceReseed` 暴露，或改为仅 dev 模式可用

### 4.3 清理硬编码路径
- **文件**: `fix-seed.js`, `启动MedLearn.bat`, `创建桌面快捷方式.ps1`
- **修复**: 全部改为相对路径

### 4.4 修复 ESM/CJS 不一致
- **文件**: `electron/main.js`, `electron/preload.js`
- **修复**: 将 electron JS 文件改为 `.cjs` 扩展名，或在 `package.json` 中移除顶层 `"type": "module"`（因为 `vite.config.ts` 和源文件都由 Vite 打包，不受影响）

### 4.5 tsconfig 检查 electron 文件
- **文件**: `tsconfig.node.json`
- **修复**: include 添加 `"electron/**/*"`，允许 JS 文件检查

### 4.6 添加 icon
- **文件**: `public/icon.ico`, `electron/icon.ico`
- **修复**: 生成一个简单的 SVG favicon 作为占位 icon；更新 electron-builder 引用

### 4.7 移除未使用的 DEFAULT_MODELS 常量
- **文件**: `src/services/ai.ts:13-17`
- **修复**: 删除未使用的导出

---

## Phase 5: 代码质量

### 5.1 统一错误处理
- 将 `.catch(() => {})` 空捕获改为至少 `console.warn`
- 所有 DB 操作统一通过 Toast 或静默日志

### 5.2 Toast nextId 模块级变量
- **文件**: `src/components/common/Toast.tsx:26`
- **修复**: 改为 `useRef(0)` 避免 HMR 时 ID 重复

### 5.3 Database 版本注释
- **文件**: `src/db/db.ts`
- **修复**: 添加注释说明跳过的版本号和原因

### 5.4 种子数据 Date.now() 规范化
- **文件**: 所有 seed 文件
- **修复**: 添加注释说明这些 timestamp 在首次导入时固定

---

## Phase 6: 数据质量

### 6.1 清理提取数据中的重复项
- **文件**: `src/db/extractedKnowledge.ts`
- **修复**: 用脚本去重（基于 title + chapter 相同的合并），修正危重症医学概要/烟草病学概要的异常重复

### 6.2 统一教材目录
- **文件**: `src/constants/subjects.ts`, `src/constants/internalMedicineCatalog.ts`
- **修复**: 将 `internalMedicineStructure` 废弃，统一使用 `internalMedicineCatalog` 作为唯一目录源

---

## 验证步骤

1. `npm run typecheck` — 确保 TypeScript 无错误
2. `npm run build` — 确保构建成功，检查 bundle 大小是否减小
3. `npm run electron:preview` — 确保 Electron 打包运行正常
4. 手动测试：
   - Dashboard 学习统计是否正确（已学 vs 薄弱环节）
   - API Key 保存后重启是否仍在
   - CSP 不阻止自定义 API 端点
   - 知识点分组浏览性能（加载 483+ 节点）

---

## 修改文件清单

| 优先级 | 文件 | 改动类型 |
|--------|------|----------|
| P0 | `src/pages/Dashboard.tsx` | Bug 修复 + 性能 |
| P0 | `src/db/db.ts` | DB 升级逻辑修复 |
| P0 | `src/pages/feynman/FeynmanDetail.tsx` | Bug 修复 |
| P0 | `src/pages/case/CaseDetail.tsx` | Bug 修复 |
| P0 | `src/hooks/useLearningDialogue.ts` | 防御性修复 |
| P1 | `electron/main.js` | 安全增强 + IPC |
| P1 | `electron/preload.js` | 安全 API 桥接 |
| P1 | `src/services/ai.ts` | 加密存储 + 清理 |
| P1 | `index.html` | CSP 修复 |
| P1 | `vite.config.ts` | 移除默认代理 + 别名 |
| P2 | `src/db/seed.ts` | 懒加载 + 移除调试代码 |
| P2 | `src/db/extractedKnowledge.ts` | 数据去重 |
| P2 | `tsconfig.app.json` | 路径别名 |
| P2 | `tsconfig.node.json` | 扩展检查范围 |
| P2 | `package.json` | 修复 ESM 声明 |
| P3 | `fix-seed.js` | 相对路径 |
| P3 | `启动MedLearn.bat` | 相对路径 |
| P3 | `创建桌面快捷方式.ps1` | 相对路径 |
| P3 | `src/components/common/Toast.tsx` | nextId 改为 useRef |
| P3 | `src/constants/subjects.ts` | 废弃标记 |
| P3 | `src/constants/internalMedicineCatalog.ts` | 补充缺失章节 |
| P3 | `src/components/knowledge/SystemContextPanel.tsx` | 性能 + 目录统一 |
| P3 | `src/pages/FeynmanRecall.tsx` | 性能优化 |
