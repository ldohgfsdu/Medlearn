# Dyoo AI 视频总结功能 — 实现计划

## Context

Dyoo v1.1.7 是一个 LSP (Xposed) 模块，作用于抖音 (`com.ss.android.ugc.aweme`)，用 Kotlin + DexKit + Jetpack Compose 编写，代码经 R8 混淆。当前无源码，需从反编译入手重建项目并添加 AI 视频总结功能。

用户选择：**Claude API** 作为 AI 服务，内容获取方式为 **优先抓字幕 → 回退音频提取**。

---

## 实现路线

### 阶段一：反编译与项目重建

1. **安装 jadx**（需 Java 17+），对 APK 进行反编译：
   ```
   jadx -d dyoo_src Dyoo_1.1.7.apk
   ```
2. **清理混淆**：根据 `o.dyoo.*` 命名空间（未混淆）还原模块骨架结构：
   - `o.dyoo.app.Init` — 入口
   - `o.dyoo.app.activity.MainActivity` — 模块设置页
   - `o.dyoo.app.plugin.PluginInstrumentation` — Activity 拦截
   - `o.dyoo.app.ui.viewmodel.ConfigViewModel` — 配置管理
   - `o.dyoo.config.DyooConfig` — 配置数据类（含 Filter / Player / Download 内部类）
3. **反编译 DexKit 查询语句**：识别现有 hook 模式（`findMethod` / `findClass` 调用），理解如何定位抖音内部类
4. **搭建 Android 项目**：以反编译代码为参考，重建 Gradle 项目，保持原有功能结构

### 阶段二：添加字幕/文案抓取

5. **通过 DexKit 搜索抖音字幕相关类**，目标：
   - `SubtitleTextView` / `getSubtitle` / `setSubtitle` — 字幕 View
   - 抖音视频详情 API 响应中的 `subtitle` 字段（视频描述/文案）
   - 自动字幕组件（ASR 生成的字幕）
6. **Hook 方案**：
   - **方案 A（文案）**：Hook `Aweme` 模型的 `getDesc()` / `getTitle()` 获取视频文案描述
   - **方案 B（字幕）**：Hook 字幕 View 的文本变化，或 Hook 抖音字幕 API 响应
   - **方案 C（AI 字幕）**：Hook `DetailActivity` 中的字幕数据，提取 ASR 文本
7. **将提取的文本缓存**，关联当前视频 ID（`awemeId`）

### 阶段三：音频提取回退

8. **当字幕/文案不足时回退**：
   - 从抖音视频 URL（通过 Hook `VideoUrlModel` 获取）下载音频流
   - 使用内置的轻量 ASR 引擎或调用 Claude API 的文件上传能力
   - 备选：将音频文件通过 WebDAV/HTTP 发送到自建服务端做 Whisper 转写
9. **音频处理**：用 MediaExtractor + MediaCodec 提取音频轨，裁剪到合理长度

### 阶段四：Claude API 集成

10. **新增配置项** `DyooConfig$AiSummary`：
    ```kotlin
    data class AiSummary(
        val apiKey: String = "",
        val apiHost: String = "https://api.anthropic.com",
        val model: String = "claude-sonnet-4-6-20250514",
        val maxTokens: Int = 1024,
        val language: String = "zh-CN",  // 总结语言
        val enabled: Boolean = false
    )
    ```
11. **API 调用模块**（基于现有 OkHttp3）：
    - POST `{apiHost}/v1/messages`
    - 使用 `prompt caching`：system prompt 缓存为长期记忆
    - System prompt 设计：视频内容总结专家，输出结构化摘要
    - 请求体：
      ```json
      {
        "model": "claude-sonnet-4-6-20250514",
        "max_tokens": 1024,
        "system": [{"type":"text","text":"你是视频内容总结专家...","cache_control":{"type":"ephemeral"}}],
        "messages": [{"role":"user","content":"请总结以下视频内容：\n\n{提取的文本}"}]
      }
      ```
12. **流式响应处理**：SSE 解析，实时更新 UI

### 阶段五：UI 集成

13. **视频详情页添加总结按钮**：
    - 在抖音 `DetailActivity` 或视频右侧面板中注入 Compose/View 按钮
    - 通过 DexKit 找到合适的父容器，注入自定义 View
14. **总结结果展示**：
    - 底部弹出面板（BottomSheet）显示 AI 总结
    - 支持复制、展开/收起
    - 加载状态动画
15. **模块设置页新增 AI 配置**：
    - 在 `MainPage` 中新增「AI 总结」设置区块
    - API Key 输入（密码输入框，密文显示）
    - API Host 自定义（兼容代理/中转）
    - 模型选择下拉
    - 总结语言选择

### 阶段六：构建与测试

16. **编译签名**：用 LSP Manager 安装到设备
17. **测试验证**：
    - 不同类型视频（有字幕/无字幕/直播回放）
    - API Key 为空时的错误处理
    - 网络异常处理
    - 总结结果质量验证

---

## 关键技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| AI 服务 | Claude API (claude-sonnet-4-6-20250514) | 用户选择，性价比好 |
| 内容获取优先级 | 字幕/文案 → 音频 ASR | 轻量优先，兼容性好 |
| HTTP 客户端 | 复用 OkHttp3 | 项目已依赖 |
| UI 框架 | View 注入 + Compose 弹窗 | 与原模块风格一致 |
| 配置存储 | 扩展 dyoo_config.json | 与原模块一致 |
| Prompt Caching | 使用 ephemeral cache | 重复调用相同 system prompt 时节省 token |

---

## 前置条件

- **Java 17+**（jadx 反编译 + Gradle 构建）
- **Android SDK**（API 34+）
- **LSPosed / KernelSU** 测试环境
- **Claude API Key**（用户自行提供）

---

## 验证方式

1. jadx 反编译后检查 `o.dyoo.*` 包结构完整
2. Gradle 构建通过，生成签名 APK
3. 安装到 LSPosed 后模块激活
4. 打开抖音视频 → 出现「AI 总结」按钮 → 点击后获取总结
5. 在模块设置页可配置 API Key / Host / 模型
