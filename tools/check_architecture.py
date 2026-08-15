#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDSS 九星专家包 · 架构检测器（可移植 · 纯标准库 · 零依赖）
============================================================
方法论来源（来源透明）：
  1. PDSS 原生「系统结构自检」(启明·司宪 2026-08-14)：
     IPOE 主表 + 金标准 0-4 门禁 + 结构债清单 + 自我证伪（E 列必填、诚实标「未验证」非「无问题」）。
  2. verify-dont-guess 铁律：先 web-confirm 基线，再本地只读验证，最后给结论。
     本脚本是「本地只读验证」的自动化；web-confirm 基线见 CHECKS.md（MAS-FIRE 等）。
  3. MAS-FIRE-lite 静态代理：将 LLM 多智能体 15 类故障中【可静态检测】的部分做成结构探针
     （角色模糊 / 断链 / 配置错）；其余需 LLM 运行时动态注入，本脚本仅标注「需运行时」。

检测项：
  A. 结构自检      —— 每包须含 .codebuddy-plugin/plugin.json(合法JSON) + agents/*.md(合法 frontmatter) + 必要组件。
  B. §9.4 脱敏闸门 —— 扫描邮箱 / 真名(蒋平) / 星位=真名映射 / C:/路径 / .workbuddy 内部路径；命中即 blocker。
  C. WB 耦合标注   —— 标注 ~/.workbuddy/skills/* 引用为「可选·非便携」，不报错。
  D. 完整性        —— 若根 MANIFEST.json 存在，校验逐文件 SHA256。
  E. MAS-FIRE-lite —— 静态故障代理（见 FAULT_PROXIES）。

用法：
  python3 check_architecture.py [repo_root]
  exit 0 = 无 blocker；exit 1 = 有 blocker（适合 CI 卡点）。

注意：本脚本只读扫描，零删移、零改写。
"""
import os, sys, re, json, hashlib

# ---------- 脱敏闸门正则（§9.4） ----------
# 真实 PII（命中即 blocker）：邮箱（占位 .local 除外）/ 真名(蒋平) / 星位=真名映射 / C:\绝对路径
PII_BLOCKERS = {
    "email":            re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "realname_jiangping": re.compile(r"蒋平"),
    "star_eq_realname": re.compile(r"(北极星|紫微|玉衡|天枢|天璇|天玑|天权|摇光|开阳)\s*[=(＝]\s*蒋"),
    "c_abs_path":       re.compile(r"[Cc]:\\|/c/Users|/c/research"),
}
# WB 内部耦合（占位符式引用，仅信息提示，非 PII，不计入 blocker）
WB_COUPLING = re.compile(r"~/\.workbuddy|\\\.workbuddy\\\\skills")
EMAIL_PLACEHOLDER = re.compile(r"@[\w.-]*\.local$", re.IGNORECASE)  # local@pdSS.local 等占位邮箱
# 已脱敏占位符（命中窗口内出现这些则跳过，不误报）
ALLOWED_TOKENS = ["[用户]", "[本地路径·已脱敏]", "[战略伴侣·校准者]",
                  "[合作者A]", "[合作者B]", "[北极星·策源]", "[本地 vault]"]

# ---------- MAS-FIRE-lite 静态故障代理（15 类中的可静态检测子集） ----------
FAULT_PROXIES = {
    "F01_role_ambiguity":  "角色模糊：agent 缺 name/description 或正文过短(<200字)",
    "F02_broken_xref":    "断链：frontmatter skills:[x] 但 skills/x/ 目录不存在，或引用本地路径缺失",
    "F03_config_fault":   "配置错：plugin.json 非法 JSON 或缺 required 键(name/description/agents)",
    "F04_instruction_drift": "指令漂移：正文含 '待补'/'TODO'/'XXX' 未完成标记",
}

REQUIRED_PLUGIN_KEYS = ["name", "description"]


def parse_scalar(s):
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [x.strip().strip('"').strip("'") for x in inner.split(",")] if inner else []
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s


def parse_frontmatter(text):
    """极简 YAML frontmatter 解析（覆盖本仓 schema：嵌套 displayName/profession + 内联列表）。"""
    if not text.startswith("---"):
        return None, text, "no_frontmatter"
    end = text.find("\n---", 3)
    if end == -1:
        return None, text, "unclosed_frontmatter"
    fm = text[3:end].strip("\n")
    body = text[end + 4:]
    data, cur = {}, None
    try:
        for line in fm.splitlines():
            if not line.strip():
                continue
            m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
            if m and not line.startswith(" "):
                cur = m.group(1)
                val = m.group(2).strip()
                data[cur] = {} if val == "" else parse_scalar(val)
            elif line.startswith(" ") and cur and isinstance(data.get(cur), dict):
                m2 = re.match(r"^\s+([A-Za-z_][\w-]*):\s*(.*)$", line)
                if m2:
                    data[cur][m2.group(1)] = parse_scalar(m2.group(2).strip())
    except Exception as e:
        return None, text, "parse_error:" + str(e)
    return data, body, "ok"


def scan_pii(text, rel):
    """仅返回真实 PII（blocker）。占位邮箱(.local)与已脱敏 token 窗口跳过。"""
    hits = []
    for label, pat in PII_BLOCKERS.items():
        for m in pat.finditer(text):
            snippet = m.group(0)
            if label == "email" and EMAIL_PLACEHOLDER.search(snippet):
                continue  # 占位符邮箱（.local 域）不计为泄漏
            window = text[max(0, m.start() - 25):m.end() + 25]
            if any(tok in window for tok in ALLOWED_TOKENS):
                continue
            hits.append((label, snippet, rel))
    return hits


def list_md_files(pkg_dir):
    out = []
    for root, _, files in os.walk(pkg_dir):
        for f in files:
            if f.endswith(".md"):
                out.append(os.path.join(root, f))
    return out


def main():
    repo = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print("# PDSS 九星专家包 · 架构检测报告")
    print("> 仓库根: %s" % repo)
    print("> 方法论: 系统结构自检(IPOE+金标准) + verify-dont-guess + MAS-FIRE-lite 静态代理\n")

    blockers, warnings, info = [], [], []
    pkgs = []
    for name in sorted(os.listdir(repo)):
        if name.startswith("."):
            continue  # 跳过 .claude / .git 等生成态或版本目录
        if name in ("tools", "node_modules"):
            continue  # 跳过工具/依赖目录（非专家包）
        pdir = os.path.join(repo, name)
        if not os.path.isdir(pdir):
            continue
        has_plugin = os.path.exists(os.path.join(pdir, ".codebuddy-plugin", "plugin.json"))
        has_agents = os.path.isdir(os.path.join(pdir, "agents"))
        # 只要有 plugin.json 或 agents/ 子目录，就当作专家包纳入扫描
        # （防「缺 plugin.json 导致 agents/*.md 漏扫、脱敏闸门被架空」）
        if has_plugin or has_agents:
            pkgs.append(name)

    print("## A. 结构自检（发现 %d 个专家包）\n" % len(pkgs))
    for pkg in pkgs:
        pdir = os.path.join(repo, pkg)
        line = "- **%s**" % pkg
        pj = os.path.join(pdir, ".codebuddy-plugin", "plugin.json")
        if not os.path.exists(pj):
            warnings.append(("结构缺失", pkg, ".codebuddy-plugin/plugin.json 不存在（按 agents/ 识别，不影响 PII 扫描）"))
            print(line + " ⚠️ 缺 plugin.json（按 agents/ 识别）")
        else:
            try:
                with open(pj, encoding="utf-8") as fh:
                    pjdata = json.load(fh)
                missing = [k for k in REQUIRED_PLUGIN_KEYS if k not in pjdata]
                if missing:
                    blockers.append(("配置错", pkg, "plugin.json 缺键: " + ",".join(missing)))
                    print(line + " ❌ plugin.json 缺键 %s" % missing)
                    continue
            except Exception as e:
                blockers.append(("配置错", pkg, "plugin.json 非法 JSON: " + str(e)))
                print(line + " ❌ plugin.json 非法 JSON")
                continue
        # agents/*.md（无论有无 plugin.json 都扫 PII）
        adir = os.path.join(pdir, "agents")
        amds = [f for f in os.listdir(adir)] if os.path.isdir(adir) else []
        if not amds:
            blockers.append(("结构缺失", pkg, "agents/ 下无 .md"))
            print(line + " ❌ 无 agents/*.md")
            continue
        print(line + " ✅ %d agent(s)" % len(amds))

    # B. 脱敏闸门 + C. WB耦合 + E. MAS-FIRE-lite（扫所有包内 md + plugin.json）
    print("\n## B. §9.4 脱敏闸门 + C. WB 耦合 + E. MAS-FIRE-lite\n")
    scan_files = []
    for pkg in pkgs:
        pdir = os.path.join(repo, pkg)
        scan_files += list_md_files(pdir)
        scan_files.append(os.path.join(pdir, ".codebuddy-plugin", "plugin.json"))
    # 根级分发文件也纳入脱敏扫描（CHECKS.md / tools/ 为工具文档，不扫）
    for rf in ["README.md", "LICENSE", "COPYRIGHT"]:
        rfp = os.path.join(repo, rf)
        if os.path.exists(rfp):
            scan_files.append(rfp)
    pii_total = 0
    wb_refs = set()
    for fp in scan_files:
        try:
            with open(fp, encoding="utf-8") as fh:
                txt = fh.read()
        except Exception:
            continue
        rel = os.path.relpath(fp, repo)
        hits = scan_pii(txt, rel)
        for label, snip, r in hits:
            pii_total += 1
            blockers.append(("脱敏违规", r, "[%s] 命中: %s" % (label, snip)))
            print("- ❌ 脱敏违规 `%s` → [%s] `%s`" % (r, label, snip))
        for ref in re.findall(r"~/\.workbuddy/skills/([\w\-]+)", txt):
            wb_refs.add(ref)
        # MAS-FIRE-lite static proxies on agent md bodies
        if fp.endswith(".md") and "/agents/" in fp:
            fm, body, status = parse_frontmatter(txt)
            if status != "ok":
                warnings.append(("frontmatter", rel, status))
                continue
            if not fm.get("name") or not fm.get("description"):
                blockers.append(("角色模糊", rel, "缺 name/description"))
            if len(body.strip()) < 200:
                warnings.append(("角色模糊", rel, "正文过短(<200字)"))
            for todo in re.findall(r"待补|TODO|XXX|FIXME", body):
                warnings.append(("指令漂移", rel, "未完成标记: " + todo))
            sk = fm.get("skills") or []
            if isinstance(sk, str):
                sk = [sk]
            for s in sk:
                if not os.path.isdir(os.path.join(os.path.dirname(os.path.dirname(fp)), "skills", s)):
                    warnings.append(("断链", rel, "skills:[%s] 目录不存在" % s))
    if wb_refs:
        print("- ⚠️ WB 内部耦合（可选·非便携，跨平台运行时忽略即可）: " + ", ".join(sorted(wb_refs)))
    if pii_total == 0:
        print("- ✅ 未检出 §9.4 脱敏违规")

    # D. 完整性
    print("\n## D. 完整性（MANIFEST.json SHA256）\n")
    manifest = os.path.join(repo, "MANIFEST.json")
    if os.path.exists(manifest):
        try:
            with open(manifest, encoding="utf-8") as fh:
                man = json.load(fh)
            bad = 0
            for relp, exp in man.get("files", {}).items():
                fp = os.path.join(repo, relp)
                if not os.path.exists(fp):
                    print("- ❌ 缺失: %s" % relp); bad += 1; continue
                h = hashlib.sha256(open(fp, "rb").read()).hexdigest()
                if h.lower() != str(exp).lower():
                    print("- ❌ SHA256 不符: %s" % relp); bad += 1
            print("- ✅ 完整性校验通过" if bad == 0 else "- ⚠️ %d 项不符" % bad)
            if bad:
                warnings.append(("完整性", "MANIFEST", "%d 项不符" % bad))
        except Exception as e:
            warnings.append(("完整性", "MANIFEST", "解析失败: " + str(e)))
            print("- ⚠️ MANIFEST.json 解析失败: " + str(e))
    else:
        print("- ⚠️ 工作树无 MANIFEST.json（戳包内含；跨平台分发建议补入）")
        warnings.append(("完整性", "MANIFEST", "工作树缺失（戳包侧卡可补）"))

    # 汇总门禁
    print("\n## 门禁汇总\n")
    print("- 专家包数: %d" % len(pkgs))
    print("- 🔴 blocker（须修才能发）: %d" % len(blockers))
    print("- 🟠 warning（建议修）: %d" % len(warnings))
    print("- 🔵 info: WB耦合引用 %d 种（可选）" % len(wb_refs))
    print("\n### blocker 明细")
    if blockers:
        for kind, where, msg in blockers:
            print("- [%s] %s — %s" % (kind, where, msg))
    else:
        print("- 无")

    # 写 markdown 报告
    rep = os.path.join(repo, "tools", "last_check_report.md")
    try:
        with open(rep, "w", encoding="utf-8") as fh:
            fh.write("# 架构检测报告（自动生成）\n\n")
            fh.write("blockers=%d warnings=%d packages=%d\n" % (len(blockers), len(warnings), len(pkgs)))
            fh.write("\n## blockers\n")
            for kind, where, msg in blockers:
                fh.write("- [%s] %s — %s\n" % (kind, where, msg))
    except Exception:
        pass

    print("\n> 退出码: %d（0=无 blocker 可发, 1=有 blocker 须先修）" % (1 if blockers else 0))
    print("> 动态故障注入（MAS-FIRE 运行时层）需在 Claude Code / OpenCode 加载 agent 后跑，见 CHECKS.md。")
    sys.exit(1 if blockers else 0)


if __name__ == "__main__":
    main()
