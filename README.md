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
watchlists/*.csv
↓
scripts/build_report.py
↓
reports/latest.json
↓
index.html + dashboard.js
↓
スマホでダッシュボード確認
```

## Watchlist CSV

`watchlists/jp_candidates.csv` と `watchlists/us_candidates.csv` を編集します。

列は以下です。

```csv
symbol,name,market,theme,note
```

例:

```csv
7011.T,三菱重工業,JP,防衛・重工,大型テーマ継続
MU,Micron Technology,US,HBM・メモリ,AIメモリ主役候補
```

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

手動実行も可能です。

## 今後の拡張

- yfinanceで米国株の日足を取得
- J-Quants APIで日本株の日足を取得
- 50/150/200日線、52週高値安値、出来高平均、ATR、相対強度を自動計算
- VCP/SEPAスコアを実データで算出
- ブレイク後の3日/5日/10日リターンを自動記録

## 注意

このダッシュボードは投資判断の補助用です。売買前に必ず証券会社画面、企業IR、TDnet、EDINETなど一次情報を確認してください。
