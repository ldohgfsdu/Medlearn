# 第二轮代码审查修复 + 最终检查提交

## Context

第二轮手动代码审查发现 6 个真实 bug + 2 个可读性问题。全部修复后进行最终全量检查，确认零问题后提交推送。

## 修复清单

### Bug 修复 (6)

1. **`service.sh:174` — `lock_params` 函数未定义 (CRITICAL)**
   - `service.sh` 第 174 行调用 `lock_params`，但该函数不存在于任何文件中
   - 这是 Shell 回退引擎的核心锁定循环，缺失会导致 Rust 引擎不可用时守护进程静默失败
   - 需在 `memory.sh` 中定义 `lock_params()` 函数

2. **`uninstall.sh:69-72` — ZRAM 恢复顺序错误**
   - `max_comp_streams` 的恢复必须在 `disksize` 设置之前
   - 当前顺序：algorithm → disksize → mkswap/swapon → max_comp_streams (错)
   - 正确顺序：algorithm → max_comp_streams → disksize → mkswap/swapon

3. **`customize.sh:79` — `$escaped_val` 误用于直接文件写入**
   - `$escaped_val` 包含 sed 反斜杠转义，仅应用于 `sed -i` 替换
   - 直接 `echo` 追加到文件时应使用原始 `$val`

4. **`memory.sh` `run_optimization` — 硬编码 `echo "" >> "$LOG"`**
   - 未检查 `$LOG` 是否有效（可能为空或目录不存在）
   - 需加 `[ -w "$LOG" ]` 或等效检查

5. **`post-fs-data.sh:17` — `log.txt.old` 文件名错误**
   - 日志轮转创建的是 `log.txt.1`, `log.txt.2`, `log.txt.3`
   - `rm -f log.txt.old` 永远不会匹配到实际文件
   - 应改为删除 `log.txt.[0-9]*` 或 `log.txt.1 log.txt.2 log.txt.3`

6. **`memory.sh` `config_vm` — `watermark_scale_factor` 重复调用 `get_config_safe`**
   - 同一函数内对 `watermark_scale_factor` 调用了两次 `get_config_safe`
   - 应缓存到局部变量

### 可读性改进 (2)

7. **`common.sh:17` — `|| &&` 链改为 `if` 块**
   - `[ -z "$mt" ] || [ "$mt" = "0" ] && mt=$(ls -l ...)` 虽然逻辑正确但易误读
   - 改为显式 `if` 块

8. **`memory.sh:139` — 同上模式**
   - `[ -z "$sz" ] || [ "$sz" = "0" ] && return 0` 同样改为 `if` 块

## 涉及文件

- `C:\Users\21234\MemoryOpt_Plus\service.sh`
- `C:\Users\21234\MemoryOpt_Plus\memory.sh`
- `C:\Users\21234\MemoryOpt_Plus\uninstall.sh`
- `C:\Users\21234\MemoryOpt_Plus\customize.sh`
- `C:\Users\21234\MemoryOpt_Plus\post-fs-data.sh`
- `C:\Users\21234\MemoryOpt_Plus\common.sh`

## 执行步骤

### 1. 修复 6 个 bug + 2 个可读性改进
### 2. 全量最终检查所有源文件
### 3. 确认零问题后提交并推送
