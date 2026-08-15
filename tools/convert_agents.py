#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_agents.py —— 九星专家包 → 跨平台 drop-in 生成器
=========================================================
把每个包的 agents/*.md（WorkBuddy/CodeBuddy 原生格式）转成：
  - .claude/agents/<name>.md      （Claude Code subagent，frontmatter 同构）
  - opencode_agents.json          （OpenCode 自定义 agent 配置片段，粘进 ~/.config/opencode/opencode.json 的 agent【单数】键）
只读 agents/*.md，不改源；生成的 drop-in 仅含已脱敏的 agent 正文。

用法： python3 convert_agents.py [repo_root]
"""
import os, sys, json, re


def parse_scalar(s):
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [x.strip().strip('"').strip("'") for x in inner.split(",")] if inner else []
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.startswith("'")):
        return s[1:-1]
    return s


def parse_frontmatter(text):
    if not text.startswith("---"):
        return None, text, "no_frontmatter"
    end = text.find("\n---", 3)
    if end == -1:
        return None, text, "unclosed_frontmatter"
    fm = text[3:end].strip("\n")
    body = text[end + 4:]
    data, cur = {}, None
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
    return data, body, "ok"


def dump_yaml_min(d):
    return "\n".join("%s: %s" % (k, json.dumps(v, ensure_ascii=False)) for k, v in d.items()) + "\n"


def main():
    repo = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cc_dir = os.path.join(repo, ".claude", "agents")
    os.makedirs(cc_dir, exist_ok=True)
    oc_agents = {}
    count = 0
    for name in sorted(os.listdir(repo)):
        if name.startswith("."):
            continue  # 跳过 .claude 等生成态目录，避免自我覆盖
        adir = os.path.join(repo, name, "agents")
        if not os.path.isdir(adir):
            continue
        for f in sorted(os.listdir(adir)):
            if not f.endswith(".md"):
                continue
            fp = os.path.join(adir, f)
            with open(fp, encoding="utf-8") as fh:
                txt = fh.read()
            fm, body, status = parse_frontmatter(txt)
            if status != "ok":
                print("  skip %s: %s" % (fp, status))
                continue
            aname = fm.get("name", f[:-3])
            cc_fm = {
                "name": aname,
                "description": fm.get("description", ""),
                "tools": "Read, Write, Edit, Bash, Grep, Glob, WebSearch, WebFetch",
                "model": "sonnet",
            }
            cc_text = "---\n" + dump_yaml_min(cc_fm) + "---\n\n" + body
            with open(os.path.join(cc_dir, aname + ".md"), "w", encoding="utf-8") as out:
                out.write(cc_text)
            oc_agents[aname] = {
                "description": fm.get("description", ""),
                "prompt": body,
                # 注意：opencode 的 model 必须是 provider/model 全名（如 deepseek/deepseek-ai/DeepSeek-V4-Flash）。
                # 这里刻意不写 model，让 agent 继承你 opencode.json 里的全局默认模型，drop-in 即开即用；
                # 如需钉死模型，自行在 agent 块加 "model": "provider/model"。
            }
            count += 1
            print("  ✓ %s -> .claude/agents/%s.md" % (f, aname))
    with open(os.path.join(repo, "opencode_agents.json"), "w", encoding="utf-8") as out:
        # opencode 顶层键是单数 agent（非 Claude Code 的 agents 复数）
        json.dump({"agent": oc_agents}, out, ensure_ascii=False, indent=2)
    print("\n生成 %d 个 drop-in → .claude/agents/*.md + opencode_agents.json" % count)
    print("Claude Code: 把 .claude/ 整目录拷到你的项目根即可被 `Task`/subagent 调用。")
    print("OpenCode: 把 opencode_agents.json 的 agent（单数）字段合并进 ~/.config/opencode/opencode.json。")


if __name__ == "__main__":
    main()
