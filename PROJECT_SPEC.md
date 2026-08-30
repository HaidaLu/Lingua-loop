# 语言学习自动化平台 — 项目规格文档

> 本文档面向 Claude Code，用于启动开发。所有架构决策已在需求讨论阶段确定，无需重新征询用户意见，除非文档中明确标注为"待定"。

---

## 1. 项目概述

一个个人使用的语言学习网站/App，服务于两门语言的不同学习阶段：

- **英语**：已在工作/生活中使用，需求集中在"高效查词 → 卡片沉淀 → 真实语境例句 → 口语产出练习"
- **德语**：A2 阶段，依托 DW *Nicos Weg* 课程，需求集中在"课程配套的听写/跟读/纠错 → 卡片沉淀"，并需要处理德语特有的阴阳性/格变化信息

两条语言线共用同一套底层基础设施（查词卡片生成、复习引擎、例句查询、对话练习），只在卡片 schema 和素材来源上有差异。

**核心产品目标**：一个用户可以随时随地（不限于同一台电脑/局域网）访问的单一网页/App，替代目前分散在 Anki + YouGlish 网站 + 手动整理之间的碎片工作流。

---

## 2. 已确定的关键架构决策

这些决策已经过权衡讨论，请直接按此执行，不要重新引入 Anki 桌面版依赖：

| 决策点 | 选择 | 原因 |
|---|---|---|
| 复习/记忆曲线引擎 | **自建 FSRS**，不使用 Anki + AnkiConnect | AnkiConnect 是本地 HTTP API，依赖 Anki 桌面版常开且与客户端同机/同局域网，不满足"随时随地用手机访问"的目标 |
| FSRS 实现方式 | 使用开源库 `ts-fsrs`（Node/TS）或 `fsrs`（Python），不自己推导算法 | 算法已开源验证，重复造轮子无意义 |
| 卡片生成方式 | 单次 LLM 调用，输出结构化 JSON，**不是 Agent** | 查词生成卡片是无状态的一次性任务，不涉及多步决策 |
| YouGlish 集成方式 | 使用 YouGlish 官方 **JS Widget API**（`widget.js`），不是静态 iframe | Widget API 内置完整播放器控制（含"下一个例句"切换），体验接近原网站；静态 iframe 做不到这点 |
| 对话练习架构 | LLM + 工具调用（轻量 agentic），文字 MVP 先行，语音是二期 | 需要根据"最近学的词"动态调整对话内容，属于需要工具调用的场景，但不需要复杂的自主 agent 架构 |
| Nicos Weg 自动化 | 多步骤 Agent（听写生成 → diff 比对 → 错词提取 → 卡片回流） | 官网无法自动抓取（反爬/版权），素材需手动粘贴；但后续处理是真正的多步依赖决策链，值得用 agent 编排 |
| 技术栈 | Next.js（前后端一体）+ SQLite（起步）→ 可迁移 Postgres/Supabase | 单人开发、个人使用场景，避免过度工程化；SQLite 起步足够，未来要跨设备实时同步再迁移 |
| 部署 | VPS 或 Vercel（前端）+ Supabase（数据），确保移动网络下可直接访问 | 满足"随时随地用"的核心目标 |

---

## 3. Agent vs 普通调用 —— 判断依据（供后续新功能参考）

新增功能时，按此表判断是否需要 agent 编排，避免过度设计：

- **不需要 Agent**（单次结构化 LLM 调用或纯 API 集成）：查词生成卡片、YouGlish 例句展示、AnkiConnect 类的纯数据推送
- **需要轻量 Agent**（LLM + 少量工具调用，无复杂分支决策）：对话练习（工具：拉取最近生词、标记已产出词汇）
- **需要多步 Agent**（结果依赖上一步、有分支决策）：Nicos Weg 工作流（生成听写 → 比对 → 决定哪些词进卡片 → 更新进度）

---

## 4. 数据模型

```sql
-- 单词/词条本体
CREATE TABLE words (
  id INTEGER PRIMARY KEY,
  word TEXT NOT NULL,
  language TEXT NOT NULL CHECK (language IN ('en', 'de')),
  pos TEXT,                    -- 词性
  definitions TEXT,            -- JSON array
  examples TEXT,               -- JSON array
  collocations TEXT,           -- JSON array，常见搭配
  -- 德语专属字段
  gender TEXT,                 -- 'der' | 'die' | 'das'，仅 language='de' 时使用
  plural_form TEXT,
  case_notes TEXT,             -- 格变化提示
  mnemonic TEXT,                -- 记忆锚点，LLM 生成
  source TEXT,                  -- 'manual' | 'llm_lookup' | 'nicos_weg_dictation'
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- FSRS 复习状态（每个词一条）
CREATE TABLE fsrs_cards (
  id INTEGER PRIMARY KEY,
  word_id INTEGER REFERENCES words(id),
  state TEXT,                   -- 'new' | 'learning' | 'review' | 'relearning'
  stability REAL,
  difficulty REAL,
  due_date DATETIME,
  reps INTEGER DEFAULT 0,
  lapses INTEGER DEFAULT 0,
  last_review DATETIME
);

-- 每次复习记录
CREATE TABLE review_logs (
  id INTEGER PRIMARY KEY,
  card_id INTEGER REFERENCES fsrs_cards(id),
  rating INTEGER,               -- 1=again 2=hard 3=good 4=easy
  reviewed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 对话练习记录
CREATE TABLE conversations (
  id INTEGER PRIMARY KEY,
  language TEXT,
  transcript TEXT,              -- JSON，完整对话记录
  words_targeted TEXT,          -- JSON array，本次对话设定要练习的词
  words_produced TEXT,          -- JSON array，实际用出来的词
  session_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Nicos Weg 课程进度（德语专属）
CREATE TABLE nicos_weg_progress (
  id INTEGER PRIMARY KEY,
  lesson_id TEXT,
  original_text TEXT,           -- 手动粘贴的官方课文
  dictation_input TEXT,         -- 用户听写结果
  diff_result TEXT,             -- JSON，比对出的错误点
  shadow_reading_audio_path TEXT,
  shadow_reading_feedback TEXT,
  completed_at DATETIME
);
```

---

## 5. 核心功能规格

### 5.1 查词与卡片生成（英语 + 德语通用接口，参数区分语言）

**接口**：`POST /api/generate-card`

**输入**：`{ "word": "string", "language": "en" | "de", "context": "string (可选，用户提供的原句上下文)" }`

**LLM 调用要求**：使用结构化输出（JSON mode / function calling schema），system prompt 需强制以下字段：

```json
{
  "word": "string",
  "pos": "string",
  "definitions": ["string"],
  "examples": ["string"],
  "collocations": ["string"],
  "gender": "der|die|das|null",
  "plural_form": "string|null",
  "case_notes": "string|null",
  "mnemonic": "string"
}
```

德语请求时 `gender` 字段必填，不允许返回 null（除非该词本身无固定冠词，如动词/形容词，此时应返回 `null` 并在 `pos` 中说明）。

生成后自动调用 FSRS 初始化逻辑，写入 `words` + `fsrs_cards` 表（state='new'）。

### 5.2 FSRS 复习引擎

- 使用 `ts-fsrs` 库，不自行实现算法
- 接口：`GET /api/review/due`（今日待复习列表）、`POST /api/review/submit`（提交打分，触发 FSRS 状态更新 + 写 `review_logs`）
- **历史数据迁移**：如用户提供已有 Anki `.apkg` 导出文件，需实现一次性迁移脚本，读取 SQLite（`.apkg` 本质是 SQLite），转换为本系统 schema，并用 FSRS 的历史复习记录反推初始 state（避免用户进度归零）

### 5.3 YouGlish 集成

- 使用官方 `https://youglish.com/public/emb/widget.js`，实现 `onYouglishAPIReady` 回调创建 widget 实例
- 卡片详情页/复习背面嵌入该 widget，传入当前单词 + 语言（`english` / `german`）
- **不要用静态 iframe 方案**，widget API 原生支持切换下一条例句
- 注意页面需保留 "Powered by YouGlish.com" 标识（官方要求）；纯个人使用不涉及商用许可问题，但如果未来考虑分享给他人使用需留意官方的商用/App 内嵌许可条款

### 5.4 对话练习模块

**Phase 1（文字 MVP）**：
- 接口：`POST /api/conversation/message`
- System prompt 注入：调用 `get_recent_words(language, limit)` 获取最近学习的生词表，引导对话自然带入这些词
- 工具调用：`mark_word_used(word_id)` — 检测到用户在对话中正确使用某生词时调用，触发生成一张"产出型"复习卡片（可选：标记原卡片为已产出，提升其 FSRS 难度评级）
- 德语场景建议：system prompt 中允许适度中德混杂，避免 A2 水平对话受挫

**Phase 2（语音，后续迭代）**：
- 评估使用支持流式语音的实时 API，或退化为 STT → LLM → TTS 三段式管线
- 暂不在当前开发阶段实现，仅预留接口设计空间

### 5.5 Nicos Weg 工作流（德语专属，Agent 编排）

**输入**：用户手动粘贴课文原文 + 上传/粘贴自己的听写结果

**处理链**（多步骤，适合用带工具调用的 LLM 编排）：
1. `diff_dictation(original, user_input)` — 逐句比对，标出用户听写错误/遗漏的词
2. 对每个错误词调用 5.1 的卡片生成逻辑，自动写入 `words` + `fsrs_cards`
3. （可选）跟读音频比对：接入 Whisper 转写用户跟读录音，与原文做粗粒度文本相似度对比，给出反馈（不追求音素级精度）
4. 写入 `nicos_weg_progress` 记录本次学习结果

**明确不做**：不自动爬取 DW 官网课文/音频，涉及反爬和版权风险，素材获取始终是用户手动操作。

---

## 6. 开发阶段路线图

请按此顺序实现，每个阶段应产出可运行、可验证的版本，不要跳阶段并行开发：

- **Phase 1** — 查词 → LLM 卡片生成 → 写入自建 FSRS 数据库（无 UI 或极简 UI，先验证 schema 和 LLM 输出质量）
- **Phase 2** — 复习界面：今日待复习列表 + 打分交互，接入 FSRS 更新逻辑
- **Phase 3** — YouGlish widget 嵌入卡片详情/复习页
- **Phase 4** — 对话练习模块（文字 MVP，含 `get_recent_words` / `mark_word_used` 工具调用）
- **Phase 5** — Nicos Weg 工作流（听写 diff + 错词回流 + 进度记录）

Anki 历史数据迁移脚本可在 Phase 1 完成后、Phase 2 之前插入执行（一次性任务，不阻塞主线开发）。

---

## 7. 待定事项（需要与用户确认，不要擅自决定）

- 对话练习语音功能（Phase 2）具体使用哪个实时语音 API，尚未选型
- Nicos Weg 跟读发音评分的具体实现方式和精度要求，尚未最终确定
- 是否需要多设备账号系统（当前假设单用户，暂不设计多用户认证）
- 部署环境（VPS 型号 / Vercel+Supabase 具体方案）尚未选定，Phase 1-2 阶段可先用本地 SQLite 开发
