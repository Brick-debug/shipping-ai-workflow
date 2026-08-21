# Shipping Brain

Shipping Brain is a tool I built from scratch to turn broker emails into usable
shipping-market data.

[Live Demo](https://brick-debug.github.io/shipping-ai-workflow/) ·
[Bilingual interface](https://brick-debug.github.io/shipping-ai-workflow/)

## Why I built it

Broker emails arrive in large volumes, but the useful information inside them —
open vessels, cargo orders, ports, Laycan and market updates — is rarely written
in a consistent format.

I wanted to see whether AI could turn that stream of unstructured emails into a
market view that was easier to search, check and use.

## How it works

```text
Broker mailbox
      ↓
Email fetcher (IMAP + UID deduplication)
      ↓
Classifier Agent
TONNAGE / CARGO / MARKET / FIXTURE / OTHER
      ↓
Ship / Cargo / Market extraction
      ↓
Field cleaning, date and region normalization, duplicate merging
      ↓
Excel master tables + Streamlit dashboard
```

The pipeline runs automatically. My manual work happens after extraction: I
check samples against the original email, record incorrect or failed cases, and
use that error set to improve prompts and rules.

## What I built

- An email fetcher that decodes messages and avoids processing the same UID twice
- A classifier that routes each email by commercial type
- Ship extraction for vessel name, DWT, build year, open position, dates, gear
  and restrictions
- Cargo extraction for commodity, quantity, load/discharge ports, Laycan, terms
  and special requirements
- Market and fixture processing with the original source retained for checking
- Date, vessel-class and region normalization
- Duplicate merging and Excel master-table export
- A Streamlit dashboard for browsing, filtering and matching ship/cargo data
- A failed-email workbook used as an error set for later iterations

## Internal pilot

I shared the tool with around 5–10 colleagues, who used the early version in
their work.

The pilot also exposed the main gap: email was only one part of the real
information flow. Important updates often arrived through WeChat or direct
conversation, so the dashboard could fall out of sync with the latest business
context. The interface also did not fully match everyone's existing habits.

That changed how I thought about the product. Improving extraction was useful,
but the bigger challenge was capturing off-system information without forcing
the team to change how they already worked.

## Demo and code

- `docs/index.html` — bilingual browser demo, no server required
- `demo_app.py` — synthetic Streamlit dashboard
- `main.py` — email-processing pipeline and error-case capture
- `core/email_fetcher.py` — mailbox connection and message decoding
- `core/classifier.py` — email classification
- `core/extractor.py` — ship and cargo extraction
- `core/exporter.py` — cleaning, merging and Excel export

The public demo uses synthetic records. It does not contain real emails,
customers, vessels, rates or company data.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run demo_app.py
```

<details>
<summary>中文说明</summary>

Shipping Brain 是我独立从 0 到 1 开发的航运邮件智能处理工具。

程序通过邮箱接口自动抓取经纪邮件，利用 UID 避免重复处理；Classifier Agent 先判断邮件属于船盘、货盘、市场、成交还是其他类型，再由 Ship、Cargo、Market 处理分支提取结构化信息。数据经过清洗、日期和区域标准化、重复记录合并后，写入 Excel 主表并展示在 Streamlit 看板中。

我的人工工作不是复制邮件，而是对照原邮件抽检 AI 输出，把错误和失败案例存进错题集，再根据高频问题调整 Prompt 和规则。

早期版本推广给了约 5–10 位同事使用。实际使用中最大的缺口是信息同步：不少更新发生在微信或人与人沟通中，没有进入邮箱，因此看板可能落后于真实业务状态；界面也没有完全适配所有人的原有习惯。这个项目让我意识到，AI 提取只是第一步，更难的是把工具嵌进真实的信息流。

公开版本全部使用合成数据，不包含真实邮件、客户、船舶、运价或公司数据。

</details>
