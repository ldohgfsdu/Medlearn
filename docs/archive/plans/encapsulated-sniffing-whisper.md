# 修复黑屏问题

## Context

用户刷入重构后的 MemoryOpt Plus 后出现黑屏。经深度分析，发现重构引入了多个关键 bug，结合默认参数偏激进，在部分设备上会引发系统级内存停摆/黑屏。

## 黑屏根因分析（按概率排序）

### BUG 1 [致命] `flock` 不存在导致守护进程静默退出
- **文件**: `service.sh:21-25`
- **问题**: `flock` 不是 Toybox 标准组件，很多 Android 设备没有。`flock -n 9` 失败（exit 1），`!` 取反后条件为 true，脚本直接 `exit 0`
- **后果**: 守护进程首次启动就退出，VM 参数永不锁定，系统参数处于失控状态
- **修复**: 用 PID 文件锁作为回退，先检测 `flock` 是否可用

### BUG 2 [致命] `get_config()` IFS 污染风险
- **文件**: `common.sh:50-56`
- **问题**: `IFS='|'` 修改全局 IFS，若被信号中断则无法恢复
- **修复**: 在子 shell 中执行查找，或用 POSIX 安全的替代方案

### BUG 3 [致命] `get_config()` 值含 `|` 时截断
- **文件**: `common.sh:44-45`
- **问题**: 值中若包含 `|` 字符，`cut -d'|'` 会错误分割
- **修复**: 使用换行符作分隔符

### BUG 4 [严重] `post-fs-data.sh` 重入保护失效
- **文件**: `post-fs-data.sh:7`
- **问题**: `[ -n "_POST_FS_DATA_DONE" ]` 检查的是字面字符串（永远非空），不是变量
- **修复**: 加 `$`

### BUG 5 [严重] `swappiness_max()` 写 32767 后恢复失败风险
- **文件**: `memory.sh:269-271`
- **问题**: 探针写入 32767，若恢复失败 swappiness 永久为 32767 → swap 风暴 → 黑屏
- **修复**: 用子 shell 隔离探针，或用 `trap` 确保恢复

### BUG 6 [中等] `_stop_pid` 在无 usleep 设备上每次等 1 秒 × 10 次 = 10 秒
- **文件**: `common.sh:179`
- **修复**: 用 `sleep 0.3` 兼容写法（Android toybox sleep 支持小数）

### BUG 7 [中等] `config_lmk` 返回值不检查
- **文件**: `memory.sh:335`
- **问题**: `if set_value ... quiet; then return 0; fi` — 当 minfree 写入成功但后续验证失败时，跳过了 resetprop 回退
- **修复**: 这个在上轮已修复，当前代码看起来 OK，跳过

## 修改计划

### 1. `service.sh` — flock 兼容 + PID 锁回退
- 先 `command -v flock` 检测
- 有 flock → 用 flock；无 flock → 用 PID 文件 + kill 旧进程
- `exec` → `& wait` 恢复为 `exec`（避免 trap 作用域问题）

### 2. `common.sh` — get_config 完全重写
- 用换行分隔替代 `|` 分隔
- IFS 操作在子 shell 中完成
- 增加注释中 `#` 的正确处理

### 3. `post-fs-data.sh` — 修复重入保护
- `[ -n "_POST_FS_DATA_DONE" ]` → `[ -n "$_POST_FS_DATA_DONE" ]`

### 4. `memory.sh` — swappiness_max 安全化
- 用子 shell 探针，确保写入 32767 和恢复在同一个上下文
- 或者在写入 32767 前先设置 trap 确保恢复

### 5. `common.sh` — _stop_pid 兼容性
- `sleep 1` → `sleep 0.3`（Android toybox 支持）

### 6. `swap.ini` — 默认参数保守化
- `dirty_writeback_centisecs`: 100 → 500（减少 I/O 风暴）
- `dirty_background_ratio`: 2 → 5（减少频繁写回）
- `dirty_ratio`: 5 → 10（给前台更多空间）
- `watermark_scale_factor`: 100 → 50（减少激进回收）
- `swappiness`: 130 → 100（更安全的默认值）
- MGLRU: 添加 `enable_mglru=true` 配置项，默认 true 但允许禁用

## 涉及文件

1. `service.sh` — flock 兼容 + PID 回退
2. `common.sh` — get_config 重写 + _stop_pid 兼容
3. `post-fs-data.sh` — 修复变量引用
4. `memory.sh` — swappiness_max 子 shell 隔离
5. `swap.ini` — 默认参数保守化
6. `memoptd/src/main.rs` — MGLRU 可配置化

## 验证

1. `bash -n` 检查所有 .sh 语法
2. 在设备上检查 `/sdcard/Android/data/com.android.shell/log.txt` 日志输出
3. 重点检查日志中 swappiness 值、lock_params 是否正常启动
