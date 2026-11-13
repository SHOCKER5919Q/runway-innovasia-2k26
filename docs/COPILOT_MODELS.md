# AI copilot models

Figures are always calculated first by RUNWAY's deterministic tools; the
model only writes the explanation, and every rupee amount in a reply is
verified against the tool output. A reply with an unverified figure is
discarded and the built-in writer answers instead. **A model can change how
clear an answer is, never the numbers.**

Provider: xkiro (OpenAI-compatible, `https://api.xkiro.com/v1`). Key in
`backend/.env` as `RUNWAY_XKIRO_API_KEY` - gitignored, never committed.
In the app: **AI Copilot → model menu** or the **Choose a model** panel.

## Benchmark (2026-11-13)

18 free models × 10 real questions on the demo ledger (cash, dues, GST,
runway, worst case, risk, two decisions, Hindi, Telugu). Scored on verified
figures, median latency, Flesch reading ease (English; higher = easier) and
correct script for Hindi/Telugu.

| Model | Verified | Median | Reading ease | Use for |
|---|---|---|---|---|
| Mistral Medium 3.5 | 10/10 | 1.7 s | 61 | **Auto default**: today's figures, forecast, risk, Indian languages |
| Mistral Large (2512) | 10/10 | 2.1 s | 65 (easiest) | **Auto for decisions & scenarios** |
| Mistral Small | 9/10 | 1.5 s | 59 | Fastest; once summed two figures itself (caught) |
| Aya Expanse 32B | 9/10 | 6.5 s | 42 | Multilingual specialist, slower |
| Command R7B | 10/10 | 2.8 s | 50 | Backup; Telugu answer not in Telugu script |
| Built-in | always | instant | template | Offline / quota used up |

Not offered: Ministral 3B/8B and Tiny Aya (2–5/10 verified), Command A and
SenseNova (40–120 s), Command A Plus (failed 9 of 10 calls). Paid models are
not used, to avoid charges. Samples per category are 1–3 questions - guidance,
not proof.

## Found and fixed

The verifier rejected **correct** answers: `rstrip(".0")` turned `1230000`
into `123`, and `json.dumps` escaped "₹" so display strings were invisible to
it. It now handles ₹, lakh/crore rounding of a real figure, and still rejects
invented or summed figures (tests in `tests/test_copilot.py`). Pass rates
rose from 6/10 to 10/10 for the Mistral models with no model change.

## Free quota

xkiro's free models share a daily token quota. When it is used up (HTTP 429,
scope "free") RUNWAY stops calling until the reset, shows how long remains,
and answers with the built-in writer. The benchmark used today's quota.
