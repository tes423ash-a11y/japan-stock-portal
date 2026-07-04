# VCP/SEPA Daily Dashboard

スマホで見るための投資ダッシュボードです。

目的は、手入力の銘柄管理ポータルではなく、毎日生成されるスクリーニング結果を読みやすく確認することです。

## 画面の構成

- 司令室: 今日の候補数、Aランク数、見る順番
- A級候補ランキング: VCP/SEPA候補をスコア順に表示
- テーマ別資金流入: 強いテーマとリーダー銘柄を確認
- 売買計画: ピボット、損切り、利確、RRを一覧表示
- ブレイク後検証: 検出後の最大上昇、最大下落、成功/失敗を記録
- 今日の判断メモ: スマホ内にメモ保存

## データの流れ

```text
watchlists/*.csv または universes/*.csv
↓
scripts/build_report.py
↓
reports/latest.json
↓
index.html + dashboard.js
↓
スマホでダッシュボード確認
```

## Screening Mode

GitHub Actionsの手動実行時に、以下のモードを選べます。

### watchlists

`watchlists/jp_candidates.csv` と `watchlists/us_candidates.csv` だけをスコアリングします。

### top_turnover

`universes/jp_liquid.csv` と `universes/us_liquid.csv` を読み、20日平均売買代金を計算して上位N件を残します。

おすすめはこれです。

```text
screening_mode: top_turnover
screening_top_n: 50
screening_max_symbols: 100
```

### all_universe

`universes/*.csv` の銘柄を順番に処理します。全銘柄リストを入れれば全銘柄に近い運用もできますが、yfinanceを数千銘柄に投げると遅く不安定になるため、GitHub Actionsではまず100〜300銘柄程度から始めます。

## CSV形式

`watchlists/` も `universes/` も列は同じです。

```csv
symbol,name,market,theme,note
```

日本株は `7011.T` のように `.T` を付けます。

例:

```csv
7011.T,三菱重工業,JP,防衛・重工,大型テーマ継続
MU,Micron Technology,US,HBM・メモリ,AIメモリ主役候補
```

## J-Quants API設定

日本株はJ-Quants APIを使って日足データを取得できます。ただし契約期間外の場合は自動でyfinanceにfallbackします。

GitHub Actionsで使う場合は、Repository Secretsに以下を設定します。

```text
JQUANTS_API_KEY
```

既に `JQUANTS_REFRESH_TOKEN` にAPI Keyを入れている場合も、互換のため読み込みます。

## レポート生成

ローカルまたはGitHub Actionsで実行します。

```bash
pip install -r requirements.txt
python scripts/build_report.py
```

生成されるファイル:

- `reports/latest.json`
- `reports/latest.md`

## GitHub Actions

`.github/workflows/daily-screener-report.yml` で、平日18:00 JST相当に日次実行します。

手動実行では以下を指定できます。

- `screening_mode`: `watchlists` / `top_turnover` / `all_universe`
- `screening_top_n`: 出力に残す件数
- `screening_max_symbols`: 取得対象にする最大銘柄数

## 現在のスコアリング

- 20日、50日、150日、200日移動平均
- 直近高値・安値
- 出来高20日/50日平均
- 20日平均売買代金
- ATR風ボラティリティ
- 20日/60日リターン
- setupType分類: breakout / pullback / theme_leader / high_volatility / trend_watch / avoid
- componentScores: trend / momentum / volume / risk / theme / setup / liquidity

## 注意

このダッシュボードは投資判断の補助用です。売買前に必ず証券会社画面、企業IR、TDnet、EDINETなど一次情報を確認してください。
