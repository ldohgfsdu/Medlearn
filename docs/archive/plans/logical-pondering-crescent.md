# MemoryOpt Plus — Rust 守护进程 + WebUI 升级方案

## Context

当前模块完全用 shell 实现，`service.sh` 通过 `while+sleep` 轮询锁定 VM 参数，每次迭代都有 fork/exec 开销。需要升级为 native 守护进程以降低资源占用、提升响应速度，并增加 WebUI 方便手机端管理。

## 目标

1. Rust 编写守护进程 `memoryoptd`，替代 `service.sh` + `memory.sh` + `common.sh`（大部分）
2. 内置 HTTP 服务器 + WebUI，手机浏览器管理
3. 配置格式从 INI 升级为 JSON（swap.ini → swap.json）
4. GitHub Actions 自动交叉编译 arm64-v8a / armeabi-v7a / x86_64
5. 保留 shell 脚本作为安装/卸载入口，`service.sh` 退化为薄薄一层 exec 调用

## 架构

```
MemoryOpt-Plus/
├── daemon/                          # Rust 项目
│   ├── Cargo.toml
│   ├── Cargo.lock
│   ├── build.sh                     # 本地构建脚本
│   └── src/
│       ├── main.rs                  # CLI 入口、参数解析
│       ├── config.rs                # JSON 配置结构体、验证、默认值
│       ├── daemon.rs                # 主循环：mtime 检测 + 定时锁定
│       ├── zram.rs                  # ZRAM 初始化/重配/算法选择
│       ├── vm.rs                    # VM 参数写入与锁定
│       ├── lmk.rs                   # LMK minfree 计算与写入
│       ├── vendor.rs                # 厂商回收禁用
│       ├── httpd.rs                 # HTTP 服务 + 内嵌 WebUI
│       └── logger.rs                # 双目标日志（文件 + logcat）
├── bin/                             # 预编译二进制（由 CI 产出）
│   ├── arm64-v8a/memoryoptd
│   ├── armeabi-v7a/memoryoptd
│   └── x86_64/memoryoptd
├── custom/                          # 用户可替换的 WebUI 文件
│   └── index.html                   # 可选：用户自定义 UI
├── service.sh                       # 薄 wrapper：exec memoryoptd
├── customize.sh                     # 安装：检测架构 → 复制二进制 → 生成 swap.json
├── post-fs-data.sh                  # 保留（系统属性注入，一次性）
├── uninstall.sh                     # 保留（清理恢复，一次性）
├── module.prop                      # 更新版本号
├── update.json                      # 更新
├── swap.json                        # 默认 JSON 配置模板
├── META-INF/...                     # 不变
├── README.md                        # 更新
├── changelog.md                     # 更新
├── .gitignore                       # 更新
├── .gitattributes                   # 保留
└── .github/workflows/build.yml      # CI 自动构建
```

## JSON 配置格式

```json
{
  "zram": {
    "algorithm": "zstd",
    "size_factor": 2.0,
    "max_streams": "auto",
    "priority": 100
  },
  "vm": {
    "swappiness": 130,
    "dirty_background_ratio": 2,
    "dirty_ratio": 5,
    "vfs_cache_pressure": 125,
    "dirty_expire_centisecs": 1000,
    "dirty_writeback_centisecs": 100,
    "page_cluster": "auto",
    "compaction_proactiveness": 20,
    "overcommit_memory": 1,
    "extra_free_kbytes": "auto",
    "watermark_scale_factor": 100
  },
  "lmk": {
    "low_percent": 6,
    "medium_percent": 4,
    "critical_percent": 2
  },
  "general": {
    "enabled": true,
    "early_start": false,
    "disable_vendor_reclaim": false,
    "bind_lmkd": false,
    "bind_lmkd_mask": "0x0f",
    "watch_interval": 5
  },
  "logging": {
    "level": "normal",
    "log_to_logcat": false
  }
}
```

## 关键依赖（Cargo.toml）

- `serde` + `serde_json` — JSON 序列化/反序列化
- `tiny_http` — 内嵌 HTTP 服务器（最小的可用 crate）
- 标准库足以处理：文件读写、`/proc/sys/vm/*`、`/sys/block/zram*`、mtime 检测

不引入 `tokio` 等异步框架——单线程事件循环足够，减小二进制体积。

## 守护进程主循环设计

```
初始化阶段:
  1. 解析 CLI（--config / --daemon / --version）
  2. 读取 swap.json
  3. 初始化日志系统
  4. 初始化 ZRAM 设备
  5. 应用所有 VM/LMK/vendor 参数
  6. 启动 HTTP 线程（端口 8025）
  7. 记录 PID 文件

主循环（每 watch_interval 秒一轮）:
  1. 检查 disable 文件是否存在 → 存在则跳过优化，sleep 继续
  2. stat swap.json 的 mtime → 变了则重载配置、重配 ZRAM
  3. 重新锁定 VM 参数（防系统回改）
  4. 每 N 轮写一次心跳日志
  5. 自适应间隔：根据屏幕状态（dumpsys power）加倍
```

## HTTP API + WebUI

### 端点
- `GET /` — 内嵌 WebUI HTML 页面
- `GET /api/status` — 实时状态 JSON：内存、Swap、ZRAM、VM 各项当前值
- `GET /api/config` — 当前配置 JSON
- `POST /api/config` — 更新配置（写 swap.json，自动触发重载）
- `GET /api/logs` — 最近 N 行日志

### WebUI
单文件 HTML，内嵌到 Rust 二进制（`include_str!`）。功能：
- 内存/交换实时仪表盘
- ZRAM 信息（算法、大小、压缩率）
- 配置表单（分 ZRAM / VM / LMK 三区）
- 开关按钮（启用/禁用模块）
- 深色主题、响应式（手机友好）

## 兼容性处理

- 安装时同时支持 INI（旧版）和 JSON（新版），旧配置自动迁移到 JSON
- `customize.sh` 检测 `/data/adb/modules/MemoryOpt/swap.ini` → 若存在则调用 `memoryoptd --migrate` 转换
- WebUI 文件支持自定义：优先使用 `/data/adb/modules/MemoryOpt/custom/index.html`，否则用内置

## 修改的文件

| 文件 | 动作 | 说明 |
|------|------|------|
| `daemon/**` | 新建 | Rust 守护进程源码 |
| `.github/workflows/build.yml` | 新建 | CI 交叉编译 arm64/armv7/x86_64 |
| `service.sh` | 重写 | 退化为 arch 检测 + exec memoryoptd |
| `customize.sh` | 修改 | 检测 arch、复制二进制、生成 swap.json、迁移旧 INI |
| `module.prop` | 修改 | 升级版本号 |
| `swap.json` | 新建 | 默认配置模板 |
| `common.sh` | 保留 | post-fs-data 和 uninstall 仍引用 |
| `memory.sh` | 可删除 | 被 memoryoptd 替代（或保留作 fallback） |
| `README.md` | 修改 | 更新文档 |
| `changelog.md` | 修改 | 新版本记录 |
| `.gitignore` | 修改 | 添加 target/、bin/ 等 |

## 构建流程

1. 本地开发：`cd daemon && cargo build --release`
2. CI 自动构建（GitHub Actions，每次打 tag 触发）
3. 产出 3 个架构的二进制，自动附加到 Release

## 验证方式

1. `cd daemon && cargo build` — Rust 编译通过
2. CI 成功产出 3 个架构的二进制
3. 模块 zip 包含 `bin/arm64-v8a/memoryoptd` 等文件
4. 模块安装后在手机上 `ps | grep memoryoptd` 看到守护进程
5. 浏览器访问 `http://localhost:8025` 看到 WebUI
6. 修改 `swap.json` 后守护进程自动重载（日志可见）
