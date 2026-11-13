# 算法与 Agent 岗面试路线

适用于供给理解与生成、酒旅预测与定价、业务决策 Agent 两类岗位。默认四周，每周六天，每天约两小时。开场先做一轮诊断，再按失分项调整训练。通过标准用于判断是否适合开始约面。

## 两个工具怎么用

- [Notess](https://github.com/Jianglllri/Notess) 用于阅读、闭卷回忆和记录项目复盘。在「工具 ··· → 导入文档」填入 [Practice 面试路线目录](https://github.com/Jianglllri/Practice/tree/main/docs/interview-track)，即可导入路线和复盘模板。
- [Practice 练习室](http://127.0.0.1:8765/) 用于写 Python、运行用例、模拟面试和错题复刷。先按仓库首页启动服务。把错因和需要重练的题记入 Practice，把概念对照、实验取舍和项目故事留在自己的 Notess 笔记里。
- 每天先处理到期题，再做当天训练。建议 25 分钟复刷、40 分钟算法、35 分钟八股、20 分钟项目口述。每周第六天留出 90 分钟模拟与复盘。遇到同一知识点两次答错，从 Notess 补齐定义和反例，再隔天闭卷重答。

## 第一周 · 基础和诊断

- 算法依次练 [两数之和](https://github.com/Jianglllri/Practice/blob/main/docs/leetcode/two_sum.md)、[有效括号](https://github.com/Jianglllri/Practice/blob/main/docs/leetcode/valid_parentheses.md)、[无重复字符的最长子串](https://github.com/Jianglllri/Practice/blob/main/docs/leetcode/longest_substring_without_repeating_characters.md)、[二分查找](https://github.com/Jianglllri/Practice/blob/main/docs/leetcode/binary_search.md)、[反转链表](https://github.com/Jianglllri/Practice/blob/main/docs/leetcode/reverse_linked_list.md)、[岛屿数量](https://github.com/Jianglllri/Practice/blob/main/docs/leetcode/number_of_islands.md)。每题先讲不变量、复杂度和边界，再写代码。
- 用 Notess 的 [LLM 基础](https://github.com/Jianglllri/Notess/tree/main/imports/agent-interview-300/01-LLM基础) 复习 Self-Attention、位置编码、KV Cache、GQA、LoRA。闭卷解释批量推理时 KV Cache 显存和延迟怎么测，以及 LoRA 适合改什么。
- 练习室做 [持续预训练](http://127.0.0.1:8765/?view=industry&id=case:domain-pretraining)、[训练全链路](http://127.0.0.1:8765/?view=industry&id=case:cpt)。能区分 CPT、SFT、DPO、RL，写出混配消融、数据泄漏检查和遗忘回归。准备一份 90 秒自我介绍和两个可公开讲述的项目候选。

## 第二周 · Agent 与 AutoResearch

- 算法练 [合并区间](https://github.com/Jianglllri/Practice/blob/main/docs/leetcode/merge_intervals.md)、[LRU 缓存](https://github.com/Jianglllri/Practice/blob/main/docs/leetcode/lru_cache.md)、[课程表](https://github.com/Jianglllri/Practice/blob/main/docs/leetcode/course_schedule.md)、[数组中的第 K 个最大元素](https://github.com/Jianglllri/Practice/blob/main/docs/leetcode/kth_largest_element_in_an_array.md)、[零钱兑换](https://github.com/Jianglllri/Practice/blob/main/docs/leetcode/coin_change.md)。用环、重复元素、空输入和极值验证。
- 阅读 Notess 的 [Agent 核心概念](https://github.com/Jianglllri/Notess/tree/main/imports/agent-interview-300/02-Agent核心概念)、[单 Agent 架构](https://github.com/Jianglllri/Notess/tree/main/imports/agent-interview-300/04-单Agent架构)、[多 Agent 系统](https://github.com/Jianglllri/Notess/tree/main/imports/agent-interview-300/05-多Agent系统)。重点做工具选择、任务规划、并发、失败恢复和可观测性。
- 做 [MCP 写入幂等](http://127.0.0.1:8765/?view=industry&id=case:mcp-writes)、[检查点与恢复](http://127.0.0.1:8765/?view=industry&id=case:runtime-checkpoint)、[任务 Rubric](http://127.0.0.1:8765/?view=industry&id=case:rubric)、[固定预算实验](http://127.0.0.1:8765/?view=industry&id=case:research-fixed-budget)。用合成任务画出假设、执行、评估、归因的闭环。构造工具超时、Schema 变更和指标作弊三个回归样本，逐个说明验收和回退。

## 第三周 · 业务专项

- 算法练 [滑动窗口最大值](https://github.com/Jianglllri/Practice/blob/main/docs/leetcode/sliding_window_maximum.md)、[二叉树的层序遍历](https://github.com/Jianglllri/Practice/blob/main/docs/leetcode/binary_tree_level_order_traversal.md)、[单词搜索](https://github.com/Jianglllri/Practice/blob/main/docs/leetcode/word_search.md)、[最长递增子序列](https://github.com/Jianglllri/Practice/blob/main/docs/leetcode/longest_increasing_subsequence.md)。补做 [时间点正确的 SQL](http://127.0.0.1:8765/?view=industry&id=case:sql) 和 [分桶预测指标](http://127.0.0.1:8765/?view=industry&id=case:python)。
- 供给岗主练 [实体标准化](http://127.0.0.1:8765/?view=industry&id=case:catalog)、[图文证据冲突](http://127.0.0.1:8765/?view=industry&id=case:attributes)、[过滤式向量召回](http://127.0.0.1:8765/?view=industry&id=case:filtered-knn)、[供给平台时效](http://127.0.0.1:8765/?view=industry&id=case:supply-platform)。从实体粒度和错误代价讲到上线验证。阅读 Notess 的 [RAG 与知识增强](https://github.com/Jianglllri/Notess/tree/main/imports/agent-interview-300/06-RAG与知识增强)，解释召回、重排和证据校验分别解决什么问题。
- 酒旅 Agent 岗主练 [库存截尾](http://127.0.0.1:8765/?view=industry&id=case:censored)、[Chronos-2](http://127.0.0.1:8765/?view=industry&id=case:chronos2)、[预测区间校准](http://127.0.0.1:8765/?view=industry&id=case:adaptive-conformal)、[定价离线评估](http://127.0.0.1:8765/?view=industry&id=case:pricing-ope-overlap)。设计滚动回测、切片指标、线上分流及价格护栏。
- 优惠券分配追问按顺序练 [样本与平衡检查](http://127.0.0.1:8765/?view=industry&id=case:coupon-samples)、[IPW／PSM／PSS 与 DML](http://127.0.0.1:8765/?view=industry&id=case:coupon-debias)、[uplift 阈值分配](http://127.0.0.1:8765/?view=industry&id=case:coupon-assignment)、[非等比随机回放](http://127.0.0.1:8765/?view=industry&id=case:coupon-replay)、[周预算控制](http://127.0.0.1:8765/?view=industry&id=case:coupon-pacing)、[折扣与直减](http://127.0.0.1:8765/?view=industry&id=case:coupon-denomination)、[发券渠道与券包成本](http://127.0.0.1:8765/?view=industry&id=case:coupon-delivery)。用无券、8 折、85 折三臂合成日志，手算一次 IPS，给出阈值、预算护栏与退款后的净成本。连续剂量延伸读 [DRNet](https://ojs.aaai.org/index.php/AAAI/article/view/6014) 和 [VCNet](https://arxiv.org/abs/2103.07861)。
- 选主投方向做一次 25 分钟系统设计，另一方向做一次 10 分钟口述。把两个项目按[复盘模板](复盘模板.md)写成可追问版本。

## 第四周 · 模拟和补缺

- 进行三轮[模拟面试](http://127.0.0.1:8765/?view=mock)。第一轮找共性失分，第二轮用新题检验迁移，第三轮请同伴追问项目取舍和失败案例。每轮后按错误类型安排次日重练。
- 准备两篇论文口述。供给方向用 [DeepSeek-OCR 2](http://127.0.0.1:8765/?view=industry&id=case:deepseek-ocr2) 和 [Qwen3.8](http://127.0.0.1:8765/?view=industry&id=case:qwen38-hybrid)，酒旅 Agent 方向用 [Chronos-2](http://127.0.0.1:8765/?view=industry&id=case:chronos2) 和 [Δτ-Bench](http://127.0.0.1:8765/?view=industry&id=case:delta-tau)。每篇三分钟讲问题、机制、证据、边界和复现实验。
- 建议约面前连续两轮达标。用 60 分钟独立完成两道未做过的中等题，运行代表性用例并说明复杂度。八股至少 5/6 能在两分钟内讲清定义、适用场景和一个失败模式。两个项目都能用五分钟说明个人职责、基线、效果验证和回退，接着回答三轮追问。每个未达标项用同类新题复测。
