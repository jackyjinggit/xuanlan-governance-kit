# PDSS 玄览治理检测包（公开版 / Public）

> PDSS（协议驱动共生系统）是一套「人-AI 共生体」治理框架。本仓库是其**单点公开包**：
> 只发布一个中性、可独立运行的治理/规划 agent —— **玄览（xuanlan）自主学习型战略规划师**，
> 外加一套**架构合规检测器工具链**。
>
> **为什么只发这一个**：PDSS 内部另有「对抗式战略操盘」「九星议会编排」等节点，
> 属于私有语境下的主观能动性还原手段，对外观感易引发误读，故**不进入公开包**。
> 本包只暴露最中性的「先检索、再规划、来源透明、不自欺」能力。

## 一、仓库结构

| 路径 | 内容 |
|------|------|
| `xuanlan/` | 玄览 agent 源（`agents/xuanlan.md` + 自检 skill `strategist-advisor`） |
| `tools/check_architecture.py` | 架构合规检测器（PII / 脱敏泄露 / 真源指针漂移 闸门） |
| `tools/convert_agents.py` | 跨平台 drop-in 生成器（把 agent 源转成 `.claude/agents/*.md`） |
| `tools/CHECKS.md` | 检测器治理文档与判定规则 |
| `opencode_agents.json` | opencode 兼容 drop-in（顶层 `agent` 字段，单数；`model` 继承全局默认） |
| `.claude/agents/xuanlan.md` | Claude Code 兼容 drop-in |
| `LICENSE` | Apache-2.0（© 2026 PDSS Nine Star） |

## 二、自包含性

- 玄览的 system prompt 与 skill **全部内联**在 agent 源 / drop-in 中，opencode / Claude Code
  无需本仓库外的文件即可加载运行。
- 断网或无本地 vault 时，玄览以「inline 核」**降级运行**（仍能做来源透明的规划与自检）。
- 满血运行需本地 PDSS vault（兵法库、术语表、int 全量等），该 vault **刻意不在本包、不上云**，
  属私有真源；缺失时不影响基本启动，仅降级。
- **不联网自行补充**：prompt 引用的是本地路径而非 URL，缺失组件需本地补齐，无法在线拉取。

## 三、检测器工具链（核心卖点）

`tools/check_architecture.py` 是一个发布前合规闸门：扫描仓库内的真实姓名、邮箱、星位=真名映射、
真源指针漂移等，命中即输出 blocker。**用途**：你自己或社区在扩展本包前，先跑一遍防脱敏回归。

```bash
python3 tools/check_architecture.py
```

## 四、使用

### opencode（OpenAI 兼容 provider，如 SiliconFlow / DeepSeek）
1. 把 `opencode_agents.json` 里的 **`agent`**（单数）字段整体并入你的 `~/.config/opencode/opencode.json` 的 `agent` 键下；
   或直接在该文件里引用本包 provider 与 `xuanlan` agent。
2. **模型**：本 drop-in 不写 `model`，自动继承你 `opencode.json` 里的全局默认模型，drop-in 即开即用。
   如需钉死模型，在 agent 块加 `"model": "provider/model"`（全名，例如 SiliconFlow 的 `deepseek/deepseek-ai/DeepSeek-V4-Flash`）。
3. **调用**（2026-08-15 双线试运行已验证）：
   ```bash
   opencode run --agent xuanlan "只读扫一遍你的仓库导航文件，检三类漂移：死指针/旧路径残留/版本号漂移" --auto
   ```
   - `--agent xuanlan` 选主 agent（本包只发布这一个，加载后显示 `xuanlan (all)`）。
   - `--auto` 放行只读权限（Glob/Read/Grep/Test-Path 等），避免交互卡住。
4. **中文乱码规避**：Windows 终端 opencode 默认 stdout 偶发 GBK/UTF-8 混排乱码（内容无损，但阅读不便）。两种干净解法：
   - 加 `--format json` 走结构化输出；或
   - 重定向到 UTF-8 文件再读：`opencode run --agent xuanlan "..." --auto > runA.txt`（用 Read 工具看，不乱码）。

### Claude Code
复制 `.claude/agents/xuanlan.md` 到你的项目 `.claude/agents/`，用 `Task` 工具或 `/agents` 派活。

### WorkBuddy 专家市场
将 `xuanlan/` 按专家包规范放入市场目录。

## 五、脱敏声明

本公开版**不含**任何可识别个人的信息：真实姓名、邮箱、健康状态、私人关系、本地绝对路径
均已泛化占位（`[用户]` / `[本地路径·已脱敏]` 等）。真源（含私人上下文）不在此仓库，不上云。

## 六、许可证

**Apache License 2.0** —— 自由使用、修改、再分发，但必须保留本脱敏声明与署名（© 2026 PDSS Nine Star）。
完整条款见仓库根目录 `LICENSE` 文件。
