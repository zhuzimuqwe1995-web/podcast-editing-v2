# Podcast Editing Skill V2.0

一套面向中文长播客的免费 Codex Skill，只处理**完整音频、SRT 字幕和文字配置**。

它协助完成音频校对、原时间码粗剪、主片叙事诊断、人工剪辑决策记忆、爆点与切片策划、B-roll/大字/音效文字提示，以及最终交付语境审核。

> 本 Skill 不接收、不读取、不分析任何视频文件，也不替代剪辑师在 DaVinci 中的最终试听与落刀。

## 核心能力

- 音频与 SRT 双重校验，只有整期覆盖率达到 100% 才标记完成。
- 保留原话、原时间码、限定语、归因和不确定性。
- 生成完整校对版、建议粗剪版、删除对照表和来源映射。
- 诊断开场、章节推进、重复、转场、高潮和收束。
- 记录人工接受、拒绝和调整过的剪辑决定，不覆盖历史。
- 单期决定默认项目隔离；节目级规则必须由用户明确提升。
- 仅从实际保留 SRT 中策划爆点、切片和预告。
- B-roll、大字和音效只作为基于字幕语境的文字建议。
- 支持 V1 项目非破坏导入、发布隐私扫描和版本追溯。

## 安装

下载本仓库，将整个目录放入 Codex Skills 目录，保持目录名为 `podcast-editing-v2`。然后在 Codex 中使用：

```text
Use $podcast-editing-v2 to process a podcast episode from its full audio and original SRT.
```

## 快速开始

初始化新项目：

```bash
python3 scripts/podcast_project.py init episode-project \
  --title "节目标题" \
  --audio full-episode.wav \
  --srt original.srt
```

检查原始 SRT：

```bash
python3 scripts/srt_tool.py inspect original.srt
```

计算音频—字幕核验覆盖率：

```bash
python3 scripts/podcast_project.py coverage episode-project \
  --evidence 01_evidence/audio-text-check.csv \
  --duration-ms 3600000
```

导入旧版项目：

```bash
python3 scripts/podcast_project.py import-v1 old-v1-project new-v2-project
```

## 工作流程

1. 输入完整音频和原始 SRT。
2. 全集音频—字幕证据核验与完整校对。
3. 主片叙事诊断和建议粗剪。
4. 人工在 DaVinci 试听并返回实际保留 SRT。
5. 记录剪辑决定，策划爆点、切片和预告。
6. 输出 B-roll、大字与音效文字提示。
7. 审核字幕、映射、上下文和文字建议。

详细阶段门禁见 [`references/workflow.md`](references/workflow.md)。

## 项目结构

- `SKILL.md`：Skill 入口和阶段路由。
- `references/`：证据、叙事、决策、切片、审核和迁移规则。
- `scripts/`：项目、SRT 和发布校验工具。
- `templates/`：各阶段结构化模板。
- `tests/`：自动回归测试。
- `demo/synthetic-episode/`：不含真实用户素材的合成演示。

## 验证状态

- 16 项自动测试通过。
- Skill 结构校验通过。
- 合成音频与 SRT 端到端流程通过。
- 发布扫描会阻止视频、私有绝对路径和非演示音频进入发布包。

运行测试：

```bash
python3 -m unittest discover -s tests -v
```

## 隐私与边界

- 不要把真实用户音频、字幕或项目历史提交到公共仓库。
- “爆点”是可解释的编辑判断，不是传播效果保证。
- 建议粗剪不等于实际剪辑结果。
- 无法映射回源时间码时，流程会停止下游切片分配。

## License

MIT License。欢迎免费使用、修改和分享；请保留版权与许可声明。

---

## English summary

Podcast Editing V2 is a free Codex Skill for traceable Chinese long-form podcast workflows using audio and SRT inputs only. It supports audio-verified transcript correction, source-timecode rough cuts, narrative diagnosis, human decision memory, retained-program highlight planning, text-only post-production cues, and context review. Video input and video review are intentionally out of scope.
