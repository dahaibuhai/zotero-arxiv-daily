# AI 配置提示词：为任意研究方向生成每日文献推送

这份提示词用于把你的研究简介转换成 GitHub Actions 的检索配置。它只生成公开的 **Variables**，不需要、也绝不能提供 Zotero Key、邮箱授权码、LLM API Key 或任何其他 Secret。

## 使用方式

1. 先 fork 本仓库，并按[多源文献推送操作手册](多源文献推送操作手册.md)设置 Zotero 与邮箱 Secrets。
2. 复制下方完整提示词到你常用的 AI 对话中。
3. 将方括号中的内容替换为自己的信息；不确定的项可以写“请你根据研究方向建议”。
4. 让 AI 输出 Variables 表后，逐项粘贴到 **Settings → Secrets and variables → Actions → Variables**。
5. 运行 **Test workflow**，根据邮件前几篇论文再请 AI 做一次小幅调参。

## 可复制提示词

```text
我正在配置 GitHub 仓库 zotero-arxiv-daily 的每日文献推送。请只为我生成 GitHub Actions 的公开 Variables，不要索取、猜测、输出或保存任何 Secret（包括 Zotero Key、邮箱密码和 API Key）。

我的研究资料：
- 研究方向（一句话）：[例如：高温环境下钼靶磁控溅射的原子尺度机制]
- 核心科学问题：[问题 1；问题 2]
- 主要材料、对象或体系：[材料/样品/疾病/数据集/理论对象]
- 主要方法、模型或实验技术：[方法 1；方法 2]
- 重要同义词、缩写和英文术语：[术语列表]
- 明确不想收到的相邻主题：[主题列表；没有则写“无”]
- 希望邮件语言：[Chinese 或 English]
- arXiv 是否覆盖本方向：[是 / 否 / 不确定，请判断]
- 希望每天最多推荐几篇：[建议 5–15]

请按以下规则工作：
1. 先判断这个方向是否有合适的 arXiv 分类。若有，给出 1–3 个分类缩写，并用 `+` 连接；若没有合适分类，设置 `ENABLE_ARXIV` 为 `false`，并令 `ARXIV_QUERY` 为空。不要为了填满配置而给出无关分类。
2. 生成 5–20 条 `KEYWORDS_BOOST`。每行格式必须是 `英文短语:权重`，权重为 1–6；优先保留具体的研究对象、方法和核心问题，避免只有“simulation”“experiment”等泛词。
3. 将 `KEYWORD_FILTER_MODE` 设为 `boost`，`KEYWORDS_REQUIRE` 默认留空。只有当某个术语对研究范围绝对必要时，才建议 hard 筛选。
4. `KEYWORDS_EXCLUDE` 只列明确无关的主题，每行一条；不要堆积大量排除词。
5. 生成 3–8 条英文 `SEMANTIC_SCHOLAR_QUERIES`，每行一条。每条应包含核心主题和必要限定词，兼顾召回率与精确性；不要重复同义词堆砌。
6. 第一次配置使用 `SEMANTIC_SCHOLAR_DAYS=7`、`SEMANTIC_SCHOLAR_MAX_RESULTS_PER_QUERY=5`、`KEYWORD_BOOST_WEIGHT=1.5`、`SEND_EMPTY=false`。除非我另有要求，不要启用 Crossref。
7. 不要修改 Python、YAML workflow 或 Secrets；本仓库的研究方向配置必须只通过 GitHub Variables 完成。

请按下面的顺序输出：
A. 研究范围判断：说明 arXiv 是否适合本方向，以及最可能的噪声来源。
B. 可直接粘贴的 Variables 表：必须包含下列每一项，保留多行值的换行。
   ENABLE_ARXIV
   ARXIV_QUERY
   KEYWORD_FILTER_MODE
   KEYWORDS_BOOST
   KEYWORDS_REQUIRE
   KEYWORDS_EXCLUDE
   KEYWORD_BOOST_WEIGHT
   ENABLE_SEMANTIC_SCHOLAR
   SEMANTIC_SCHOLAR_QUERIES
   SEMANTIC_SCHOLAR_DAYS
   SEMANTIC_SCHOLAR_MAX_RESULTS_PER_QUERY
   MAX_PAPER_NUM
   SEND_EMPTY
   LANGUAGE
C. 运行 Test workflow 后，我应检查的 3 个现象。
D. 只给出一次“首轮配置”；不要在没有测试结果时提供多个互相冲突的方案。
```

## 安全边界

- AI 只需要研究主题和公开术语；绝不粘贴 Secrets 页面中的任何值或截图。
- `SEMANTIC_SCHOLAR_API_KEY` 也是可选 Secret。首次可使用匿名访问；遇到限流后再考虑申请自己的 key。
- `USE_LLM_API`、`OPENAI_API_KEY`、`OPENAI_API_BASE` 和 `MODEL_NAME` 与检索配置无关。默认不设置，系统会使用本地模型生成 TLDR。
- AI 的结果是首轮检索假设，不是领域结论。首次邮件应重点查看前 3–5 篇论文，再按实际噪声微调查询词或排除词。
