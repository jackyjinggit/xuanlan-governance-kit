# CHECKS.md — 九星专家包架构检测方法论与跨平台运行

> 目的：让 GitHub 社区 **clone 下来就能验证**这套九星专家包「结构自洽、已脱敏、可跨运行时跑」。
> 本文件固化「检查一个架构」的方法论（来源透明），并给出在 Claude Code / OpenCode 上真跑的路径。

---

## 一、方法论（三源合一）

### 1. PDSS 原生「系统结构自检」（启明·司宪 2026-08-14）
套 `audit-quantification` 的 **IPOE 主表 + 金标准 0-4 门禁 + 结构债清单 + 自我证伪**。
铁律：只读诊断、零删移；结论必须含 **E(Effect/Outcome) 列**；诚实标「未验证」而非「无问题」，防 IPO 式系统性高估。

### 2. verify-dont-guess（基线先确认）
任何「检查/异常判定」先 **web-confirm 通用现象基线**，再做本地只读验证，最后给结论。禁止凭记忆直接扫本地、禁止猜测。
→ 本仓的「web-confirm 基线」即下方外部方法论（MAS-FIRE 等），本地验证即 `tools/check_architecture.py`。

### 3. 外部权威：MAS-FIRE（2026, 中山大学，arXiv 2602.19843）
面向 LLM 多智能体系统的**故障注入 + 可靠性评估**系统性框架：
- 15 类故障分类（智能体内认知错误 + 智能体间协调失败）；
- 三种非侵入注入机制：提示改写 / 响应重写 / 消息路由操纵；
- 双层评估：系统级鲁棒性分数 + 过程级有效性（发生率/局部成功率/成功率）；
- 关键结论：**架构拓扑比模型更重要**；迭代闭环比线性流程多扛 40% 故障；**配置/指令类故障（角色模糊、盲目信任）最致命**，部分线性架构鲁棒性降至 0%。
- 开源：https://github.com/wxhhxn/MASFIRE
- 本仓 `check_architecture.py` 的 `MAS-FIRE-lite` 仅做**可静态检测**的代理（角色模糊/断链/配置错/指令漂移），动态故障注入需在 LLM 运行时做（见第三节）。

---

## 二、静态检测（任意平台，零依赖）

```bash
cd pdss-nine-star-experts-public
python3 tools/check_architecture.py          # 默认扫本仓
# 或指定路径：
python3 tools/check_architecture.py /path/to/repo
```

**检测项**
| 项 | 内容 | 命中后果 |
|----|------|----------|
| A 结构自检 | 每包须有 `.codebuddy-plugin/plugin.json`(合法JSON) + `agents/*.md`(合法frontmatter) | blocker |
| B §9.4 脱敏闸门 | 邮箱 / 真名(蒋平) / 星位=真名映射 / `C:\`路径 / `.workbuddy`内部路径 | blocker |
| C WB 耦合标注 | `~/.workbuddy/skills/*` 引用 → 标「可选·非便携」 | 仅信息 |
| D 完整性 | 根 `MANIFEST.json` 逐文件 SHA256 校验 | warning（缺则提示补） |
| E MAS-FIRE-lite | 角色模糊 / 断链 / 配置错 / 指令漂移 静态代理 | blocker/warning |

**退出码**：`0`=无 blocker（可发）；`1`=有 blocker（须先修）。
报告同时写入 `tools/last_check_report.md`。CI 可直接拿退出码卡点。

---

## 三、动态检测（在 agent 平台真跑，验证「harness 无关」）

静态检测只能证明「包体自洽」。要证明专家**真能脱离 WorkBuddy 工作**，须把 `agents/*.md` 喂进别的运行时做一轮故障注入。

### 平台选择（2026 横向对比结论）
| 平台 | 适配度 | 理由 |
|------|--------|------|
| **Claude Code** | ★ 主选 | subagent 格式 `.claude/agents/*.md` 与九星 `agents/*.md` **frontmatter 同构**（name/description），能真当 subagent 跑 |
| **OpenCode** | ★ 通用备份 | MIT 开源、BYOK、无厂商锁定、可本地模型，最贴「社区拿到就用」 |
| Aider / Cursor | 辅助 | git-native / IDE，适合静态验证回路；subagent 非一等公民 |

### 步骤（以 Claude Code 为例）
```bash
# 1. 生成 drop-in（同构映射，不改源）
python3 tools/convert_agents.py
#   → 产出 .claude/agents/<name>.md（每个九星专家一个 subagent）
#   → 产出 opencode_agents.json（OpenCode 配置片段）

# 2. 在你的项目根（已含 .claude/agents/）启动 Claude Code
claude
# 3. 派活给某专家 subagent，例如：
#    > 用 Task 工具调 xuanlan：评估「把九星包做成跨运行时通用」的风险
# 4. （进阶）按 MAS-FIRE 做故障注入：
#    - 角色模糊：临时删掉某 agent 的 description，看是否行为漂移
#    - 指令漂移：在 prompt 里塞矛盾指令，看是否盲目信任
#    - 断链：移除 skills/ 子目录，看是否报错自愈
```

### OpenCode 步骤
把 `opencode_agents.json` 的 **`agent`**（单数）字段合并进 `~/.config/opencode/opencode.json` 的 `agent` 键下。
- **模型**：drop-in 不写 `model`，继承全局默认模型；要钉死就加 `"model":"provider/model"`（全名，如 `deepseek/deepseek-ai/DeepSeek-V4-Flash`）。
- **实测调用**（2026-08-15 双线试运行验证可用）：
  ```bash
  opencode run --agent xuanlan "只读扫一遍你的仓库导航文件，检三类漂移：死指针/旧路径残留/版本号漂移" --auto
  ```
  `--auto` 放行只读权限避免交互卡住；中文乱码用 `--format json` 或 `> runA.txt` 重定向规避（Windows 终端 GBK/UTF-8 混排）。
BYOK 可接任意模型（含本地模型），零厂商锁定。

---

## 四、发布前硬性门禁（§9.4）

静态检测 + 动态 smoke test 全过，**且脱敏闸门零命中**，才算「GitHub 社区拿到就能用」。
当前已知 blocker（截至 2026-08-15，待蒋平裁决修复）：
1. `yan/.codebuddy-plugin/plugin.json` → 真实个人邮箱泄漏；
2. `luchen/README.md` → 真名↔星位映射（`玉衡＝蒋平` 等 2 处）；
3. 顶层 `README.md` → `© 2026 蒋平`（署名权，是否保留由作者裁）。

> 发布权归作者（玉衡·蒋平）；本仓 AI 不代 push，仅备好仓 + 出命令。
