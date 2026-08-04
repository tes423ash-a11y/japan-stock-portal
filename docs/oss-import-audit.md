# OSS Import Audit — 2026-08-05

## Adopted

### TradingView Lightweight Charts 5.2.0

- Purpose: render the validation lab's cumulative-R chart.
- License: Apache-2.0.
- Dependency surface: one bundled dependency (`fancy-canvas` 2.1.0) in the standalone build.
- Network behavior: no `fetch`, XHR, WebSocket, cookie, storage, dynamic-code, child-process or token pattern was found in the distributed production bundle.
- Supply-chain control: the npm tarball version and integrity were checked, the production file is vendored locally, and CI verifies its SHA-256.
- Runtime communication: none added. The chart reads only the local validation JSON.

## Reviewed but not imported

| Repository | Decision | Reason |
|---|---|---|
| `polakowo/vectorbt` | Defer | Excellent research model, but Numba/Rust/Plotly add unnecessary weight to the existing daily pipeline. The transparent simulator in this repository covers the immediate validation need. |
| `microsoft/qlib` | Defer | Useful after a point-in-time feature/label dataset exists. Adding ML before historical-universe and fundamentals coverage would mainly increase overfitting risk. |
| `OpenBB-finance/OpenBB` | Defer | Strong data integration platform, but its provider and dependency surface is much larger than this static GitHub Pages deployment needs. |
| `J-Quants/jquants-api-client-python` | Connection-ready only | Official Apache-2.0 client and preferable for Japanese data reliability, but it requires a paid API plan/key. No secret or paid dependency is added until credentials are configured. |
| `ZhuLinsen/daily_stock_analysis` | Do not copy wholesale | MIT, but it connects to many quote, search, LLM and notification providers and has a very large dependency/secret surface. Individual ideas may be reimplemented after separate review. |
| `YoungCan-Wang/WyckoffTradingAgent` | Do not import | AGPL-3.0 and a broad network/database/LLM dependency surface are incompatible with a small permissive static-site enhancement. |

## Validation boundaries

- Signals execute at the next available session open, never the detection close.
- Fees and slippage are charged on entry and exit.
- If both target and stop are touched in one daily candle, the stop wins.
- Detected records remain in the prospective ledger even after a symbol leaves the current universe.
- Historical survivorship bias is explicitly reported as unresolved unless `data/historical_universe.csv` is supplied.
