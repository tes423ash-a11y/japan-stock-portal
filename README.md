# Full-Market VCP/SEPA Daily Dashboard

スマホで見るための投資ダッシュボードです。

目的は、手入力の銘柄管理ポータルではなく、毎日生成されるスクリーニング結果を読みやすく確認することです。

## 画面の構成

- 司令室: 今日の候補数、Aランク数、見る順番
- 実行候補: VCP・ブレイク・押し目候補をスコア順に表示
- セクターRS: 日米を分け、公式業種内の相対力を確認
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

`universes/jp_liquid.csv` と `universes/us_liquid.csv` を読み、20日平均売買代金を計算して、**日本株と米国株を別々に上位N件** 残します。

JP/USを合算しません。

```text
screening_top_n: 100
```

なら、意味は以下です。

```text
日本株 売買代金トップ100
米国株 売買代金トップ100
合計 最大200銘柄
```

おすすめはこれです。

```text
screening_mode: top_turnover
screening_top_n: 100
screening_max_symbols: 300
screening_usdjpy: 150
```

`screening_top_n` と `screening_max_symbols` は、どちらも **各市場ごと** の数です。

### all_universe

通常運用です。東証の内国普通株と、米国主要市場の流動性基準を通過した普通株をまとめて一次走査します。その後、同一市場内RSとSEPA/VCPスコアで日米それぞれ上位500銘柄、合計1000銘柄だけを画面へ公開します。

つまり「1000銘柄しか見ない」のではなく、全母集団を走査してから上位1000銘柄へ絞る構成です。画面の軽さを保ったまま、母集団からの取りこぼしを減らします。

## CSV形式

最小形式は以下です。公式母集団ファイルでは `sector` と `industry` も使用します。

```csv
symbol,name,market,theme,note
```

日本株は `7011.T` のように `.T` を付けます。

例:

```csv
7011.T,三菱重工業,JP,防衛・重工,大型テーマ継続
MU,Micron Technology,US,HBM・メモリ,AIメモリ主役候補
```

## データソース

- 日本株の会社名・業種: JPX「東証上場銘柄一覧」
- 日本株の母集団: JPX「東証上場銘柄一覧」のプライム・スタンダード・グロース内国株式
- 米国株の母集団: Nasdaq Stock Screenerの主要市場銘柄から、普通株・最低流動性条件を通過したもの
- 日米の公式大型株メタデータ補完: TOPIX構成銘柄・S&P 500構成銘柄
- 日米の価格・出来高: yfinanceによる日足一括取得

全市場走査では日米を同じ取得方式にそろえるため、J-Quants認証情報は現在使用しません。J-Quants用Secretsの追加は不要です。
画面の「採点可能率」は、価格通信が返っただけでなく、テクニカル指標を構築できた銘柄だけを数えます。

## 共通スクリーニングデータ

毎回の全市場走査結果は、ほかの投資画面から再利用できる共通データとして分離して出力します。

- `reports/shared/manifest.json`: 基準日、走査数、利用先ファイル
- `reports/shared/jp-base.json`: 日本株の全走査済み基本指標
- `reports/shared/us-base.json`: 米国株の全走査済み基本指標
- `reports/shared/technical-top.json`: モバイル画面向け軽量上位候補

価格履歴の取得と移動平均・RS・出来高・ATR等の基本計算はここで一度だけ実行し、各サイトは目的別の最終判定だけを行います。別々のサイトが同じ価格データを何度も取得しないため、更新時刻のずれと取得制限を抑えられます。

## レポート生成

ローカルまたはGitHub Actionsで実行します。

```bash
pip install -r requirements.txt
python scripts/update_sp500_universe.py
python scripts/update_topix500_universe.py
python scripts/validate_universes.py
python scripts/build_report.py
python scripts/enrich_external_signals.py
python scripts/enrich_sector_strength.py
python scripts/update_tracking.py
```

生成されるファイル:

- `reports/latest.json`
- `reports/latest.md`
- `reports/shared/*.json`

価格取得元が一時的にレート制限されている間に、既存の終値データへ新しい採点・会社名・業種ロジックだけを安全に適用する場合は、生成日時を更新せずに次を実行します。

```bash
python scripts/rescore_existing_report.py
```

## GitHub Actions

`.github/workflows/daily-screener-report.yml` で、日本株終値反映用の平日18:00 JSTと、米国株終値反映用の火〜土曜7:30 JSTに実行します。

手動実行では以下を指定できます。

- `screening_mode`: `watchlists` / `top_turnover_today` / `top_turnover` / `all_universe`
- `screening_top_n`: 各市場ごとに公開する件数。標準500。
- `screening_max_symbols_jp`: 日本株で取得する最大銘柄数。標準5000。
- `screening_max_symbols_us`: 米国株で取得する最大銘柄数。標準8000。
- `screening_usdjpy`: 日本株の売買代金をUSD換算するための仮レート。

## 現在のスコアリング

- 20日、50日、150日、200日移動平均
- 直近高値・安値
- 出来高20日/50日平均
- 20日平均売買代金
- 20日平均売買代金USD換算
- ATR風ボラティリティ
- 20日/60日/120日/252日リターンの市場内パーセンタイルRS
- 60日・30日・15日の値幅収縮、10日タイトネス、出来高枯れ
- 深さ40%超のベースをVCP実行候補から除外
- setupType分類: vcp_ready / breakout_ready / pullback_ready / trend_watch / early_stage / extended / avoid
- rank分類: S（90点以上）/ A（80点以上）/ B（70点以上）/ C（60点以上）/ D
- componentScores: trend 25 / RS 20 / VCP 25 / volume 10 / risk 10 / liquidity 10

テーマ一致は表示だけに使い、テクニカル点へ加算しません。

## テスト

```bash
python -m unittest discover -s tests -p "test_*.py"
node --test tests/dashboard-utils.test.mjs
```

## 注意

このダッシュボードはテクニカル一次選別用です。決算・EPS・売上成長率・次回決算日・ニュース材料は採点していません。売買前に必ず証券会社画面、企業IR、TDnet、EDINETなど一次情報を確認してください。
