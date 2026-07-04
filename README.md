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

日本株は `7011.T` のように `.T` を付けます。J-Quants APIへ渡すときは、スクリプト内で `7011` に変換します。

例:

```csv
7011.T,三菱重工業,JP,防衛・重工,大型テーマ継続
MU,Micron Technology,US,HBM・メモリ,AIメモリ主役候補
```

## J-Quants API設定

日本株はJ-Quants APIを使って日足データを取得できます。

GitHub Actionsで使う場合は、Repository Secretsに以下のどちらかを設定します。

### 方法A: メールアドレスとパスワード

- `JQUANTS_EMAIL`
- `JQUANTS_PASSWORD`

### 方法B: リフレッシュトークン

- `JQUANTS_REFRESH_TOKEN`

どちらも未設定の場合、スクリプトはJ-Quants取得をスキップし、CSVベースのMVPスコアでレポートを作ります。

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

注意: 新規Workflowファイルは、PRをマージして `main` に入ってからActions画面で手動実行できるようになります。PR確認中はSecrets設定とコードレビューまで行い、マージ後に `Actions > Daily Screener Report > Run workflow` を実行してください。

## 現在のスコアリング

J-Quants認証情報がある場合、日本株について以下を計算します。

- 50日、150日、200日移動平均
- 52週高値・安値
- 出来高20日/50日平均
- ATR風ボラティリティ
- 20日/60日リターン
- 簡易SEPA/VCPスコア
- ATRベースの初期損切り候補

米国株はまだ外部データ取得なしです。次の拡張でyfinanceまたは別APIを追加します。

## 今後の拡張

- 米国株の日足取得
- ブレイク後の3日/5日/10日リターンを自動記録
- テーマ強度を出来高・騰落率ベースで集計
- 決算日・TDnet・EDINETリンクの自動補完

## 注意

このダッシュボードは投資判断の補助用です。売買前に必ず証券会社画面、企業IR、TDnet、EDINETなど一次情報を確認してください。
