# MemoryOpt-Plus 审查报告

## 概要

MemoryOpt Plus 是一个面向 Android 设备的 Magisk 内存优化模块（约 1400 行 shell），通过 ZRAM 管理、VM 参数锁定、LMK 调优、厂商回收禁用等功能提升多任务后台保活能力。

项目整体完成度高，架构清晰，代码风格一致。以下是发现的问题，按严重程度排序。

---

## 严重问题 (P0)

### 1. service.sh 缺少 `_cfg_*` 辅助函数（功能完全失效）

**文件**: `service.sh:120-140`

`reload_config_cache()` 调用了 `_cfg_num`、`_cfg_str`、`_cfg_bool` 三个函数，但这些函数在整个项目中 **从未定义**。`common.sh` 和 `memory.sh` 中都没有这些函数。

这导致守护进程每次重载配置时，所有缓存变量都为空字符串，参数锁定循环完全失效。

**修复建议**: 在 `common.sh` 中添加这三个辅助函数：
```sh
_cfg_num()  { get_config_num "$1" "$2"; }
_cfg_str()  { local v; v=$(get_config "$1"); echo "${v:-$2}"; }
_cfg_bool() { local v; v=$(get_config_safe "$1"); echo "${v:-false}"; }
```

### 2. `swappiness_max()` 中 `eval` 导致全局变量污染

**文件**: `common.sh:157-165`

```sh
eval '
    cur=$(cat /proc/sys/vm/swappiness 2>/dev/null)
    echo 32767 > /proc/sys/vm/swappiness 2>/dev/null
    max=$(cat /proc/sys/vm/swappiness 2>/dev/null)
    [ -n "$cur" ] && printf "%s" "$cur" > /proc/sys/vm/swappiness 2>/dev/null
    echo "${max:-200}"
'
```

`eval` 内部修改了全局 `max` 和 `cur` 变量。虽然在当前调用点问题不大，但这是不安全的模式。**建议**: 改用子 shell `$(...)` 代替 `eval`：
```sh
max=$(cur=$(cat /proc/sys/vm/swappiness 2>/dev/null)
    echo 32767 > /proc/sys/vm/swappiness
    max=$(cat /proc/sys/vm/swappiness)
    [ -n "$cur" ] && printf "%s" "$cur" > /proc/sys/vm/swappiness
    echo "${max:-200}")
```

---

## 重要问题 (P1)

### 3. ZRAM reset 后 disksize=0 检查使用错误单位

**文件**: `memory.sh:80-85`

```sh
_wait_zram_reset() {
    while [ "$waited" -lt 100 ]; do
        local sz; sz=$(cat "$zsys/disksize" 2>/dev/null | tr -cd '0-9')
        if [ -z "$sz" ] || [ "$sz" = "0" ]; then return 0; fi
        usleep 50000 || sleep 1
        waited=$((waited + 1))
    done
```

注释说 "50ms" 但 `usleep 50000` 是 50ms（正确），不过 `sleep 1` 作为回退是 1 秒，与 50ms 差距很大。且循环上限 100 次，最坏情况等待 100 秒。**建议**: 回退用 `sleep 0.1` 更合理。

### 4. `lock_params` 中读取 `enable_mglru` 但未实际写入

**文件**: `memory.sh:238` + `service.sh:141`

`reload_config_cache()` 读取了 `_lock_mglru`，但 `lock_params()` 循环中从未使用该值来写入 `/sys/kernel/mm/lru_gen/enabled`。如果用户在热重载中切换 `enable_mglru`，该变更不会生效。

### 5. `bind_lmkd` 使用 `pgrep` 可能在低版本 Android 上不可用

**文件**: `memory.sh:124`

```sh
for pid in $(pgrep lmkd 2>/dev/null); do
```

Android Shell（toybox）不一定提供 `pgrep`。建议回退到 `ps | grep lmkd | awk '{print $2}'`。

### 6. `stat -c %Y` 不可用时的 mtime 检测回退链过长

**文件**: `common.sh:56-62`

`get_config()` 中 mtime 检测回退了三种方式（`stat -c %Y` → `date -r` → `ls -l | awk`），但三者的输出格式完全不同。`ls -l` 的 `$6$7$8$5` 拼接出的值不能直接与 `stat -c %Y` 的 epoch 比较，可能导致缓存永不失效或频繁失效。**建议**: 统一使用 `date +%s` 作为标准化输出。

### 7. `config_lmk()` 中 resetprop 回退值计算可能溢出

**文件**: `memory.sh:179-181`

```sh
resetprop ro.lmk.low      "$((mem_mb * l * 256 / 100))"
```

当 `mem_mb=12288, l=6` 时，`12288 * 6 * 256 = 18,874,368`，在 shell 整数范围内没问题，但 LMK 框架期望的值单位需要确认是否与 `use_minfree_levels` 格式匹配。

---

## 一般问题 (P2)

### 8. `get_config()` 性能：每次读取都 fork `sed` + `while` 子 shell

**文件**: `common.sh:55-67`

`get_config` 在守护进程的高频循环中被反复调用。当前实现每次调用都会 fork 一个 `sed` 进程和一个 `while` 子 shell。虽然有 mtime 缓存避免重复读取文件，但查找逻辑仍然有开销。**建议**: 用单次 `grep` 替代 `sed | while`：
```sh
echo "$_CFG_CACHE" | grep "^${1}=" | head -n1 | cut -d= -f2-
```

### 9. `pack.sh` 引用了不存在的 `service.sh` 但实际存在——注释中引用的 Rust 引擎残留

**文件**: `swap.ini:2` 注释提到 "Rust 引擎 <100ms / Shell 引擎 ~5s"，但 Rust 引擎已移除。

**文件**: `UPDATE.md` 仍然描述 "双引擎架构：Rust 守护进程 (memoptd) + Shell 零依赖回退"，与实际代码不符。

### 10. `uninstall.sh` 中 `_prop_del` 依赖 `common.sh` 的 `_HAS_RESETPROP`，但卸载时可能已无 Magisk 环境

**文件**: `uninstall.sh:72-80`

卸载脚本会 `source common.sh`，但 Magisk 卸载阶段 `resetprop` 可能不可用。当前代码已做兼容处理（`_prop_del` 回退到 `setprop`），但 `setprop` 删除属性可能不生效。建议增加 `resetprop -d` 的直接调用作为首选。

### 11. `post-fs-data.sh` 中重复定义了 `is_xiaomi()` 和 `is_oppo()`

**文件**: `customize.sh:43-48` 和 `common.sh:79-84` 中有相同定义，`post-fs-data.sh` 通过 source `common.sh` 获取。但 `customize.sh` 中的副本可能造成维护分歧。

### 12. 日志轮转不处理 `.1` 文件已存在的情况

**文件**: `common.sh:122-132`

```sh
rm -f "${_LOG_FILE}.${_LOG_KEEP}" 2>/dev/null
local i=$_LOG_KEEP
while [ "$i" -gt 1 ]; do
    [ -f "${_LOG_FILE}.$((i-1))" ] && mv "${_LOG_FILE}.$((i-1))" "${_LOG_FILE}.${i}" 2>/dev/null
    i=$((i-1))
done
mv "${_LOG_FILE}" "${_LOG_FILE}.1" 2>/dev/null
```

当 `MAX_LOG_SIZE` 较小且写入频率高时，轮转期间的并发写入可能丢失日志行。在 Shell 环境下难以完全避免，但值得知晓。

### 13. `dirty_writeback_centisecs` 默认值不一致

- `swap.ini` 中注释示例为 `500`
- `generate_optimal_config()` 中生成 `100`
- `config_vm()` 中 fallback 为 `100`

README 中未列出此参数。建议统一默认值。

---

## 架构/设计观察

### 14. 缺少卸载恢复脚本的验证

`uninstall.sh` 假设备份文件一定存在且格式正确。如果备份文件损坏（如 `algorithm` 文件为空），恢复操作可能静默失败，导致 ZRAM 处于不一致状态。

**建议**: 在恢复前验证备份文件完整性，失败时打印明确警告。

### 15. 无 systemd/svc 原生的服务管理集成

守护进程通过 Magisk 的 `service.sh` 启动，但没有使用 Android 的 `svc` 机制。这是 Magisk 模块的常见做法，但如果守护进程 crash，不会自动重启。

### 16. `CONFIG` 变量在 `common.sh` 中依赖 `$MODDIR`

`common.sh:3` 中 `[ -n "$_COMMON_SH_LOADED" ] && return 0` 可能导致 `CONFIG` 在某些调用链中未被设置。`memory.sh` 在开头设置了默认值，但 `service.sh` 显式设置了 `CONFIG`。这种分散的配置路径增加了出错风险。

---

## 文档问题

### 17. README 中部分参数未列出

- `dirty_expire_centisecs` 和 `dirty_writeback_centisecs` 有默认值但不在 README 参数表中
- `stat_interval` 被锁定但未在配置文件中说明
- `enable_mglru` 在 README 中列为高级参数，但 `swap.ini` 中实际存在

### 18. UPDATE.md 与代码状态不同步

仍然描述 "双引擎架构" 和 "inotify 配置热重载"，但 inotify 和 Rust 引擎均已移除。

---

## 代码质量正面评价

1. **输入验证全面**: `get_config_safe()` 对所有参数做了类型和范围检查
2. **原子文件写入**: `zram_dev.tmp` → `mv` 模式避免了部分写入
3. **配置缓存高效**: mtime 检测避免了每次循环重新解析文件
4. **日志分级清晰**: quiet/normal/verbose 三级 + logcat 同步
5. **备份-恢复链完整**: 原生 ZRAM 和 VM 参数都有备份，卸载时完整恢复
6. **冲突模块检测**: 安装时自动标记卸载冲突模块，避免功能重叠
7. **权限处理健壮**: `_raw_write` 有完整的 SELinux/permission 回退链

---

## 总结

| 级别 | 数量 | 说明 |
|------|------|------|
| P0 严重 | 2 | `_cfg_*` 缺失导致守护进程失效；`eval` 污染 |
| P1 重要 | 5 | MGLRU 热重载失效、pgrep 兼容性、mtime 比较等 |
| P2 一般 | 6 | 性能、文档不一致、默认值冲突等 |

**最紧急**: 修复 `_cfg_num`/`_cfg_str`/`_cfg_bool` 函数缺失问题，这会导致所有通过 Magisk Manager 启动的守护进程参数锁定完全无效。
