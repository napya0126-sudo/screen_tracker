# Screen Tracker

Mac mini上での作業内容をバックグラウンドで自動記録し、後からAIエージェントで解析しやすい形式でローカル保存するプロジェクトです。

## 目的

- 作業の実態を時系列で記録する
- 後から振り返りや分析に使えるログを残す
- 保存先はローカルのみとし、外部クラウドは利用しない

## 想定動作環境

- macOS (Mac mini)
- ローカルファイル保存

## 主要機能（要件定義ベース）

- アクティブウィンドウ記録
  - 5〜10秒間隔で最前面アプリ名とウィンドウタイトルを記録
- ブラウザ対応
  - Google Chrome と Dia のウィンドウタイトルを記録
- アイドル判定
  - キーボード・マウス無操作が10分継続で `Idle`
  - 操作再開で `Active` に復帰
- 会議判定（推定）
  - `Zoom` はバックグラウンド起動も検知して `meeting_candidate` を記録
  - 前面が `Zoom` / `Google Meet` の場合は `in_meeting` を記録
  - `Teams` は会議判定の対象外（チャット用途として扱う）

## ログ形式

- 出力: JSON
- 記録項目:
  - タイムスタンプ
  - アプリケーション名
  - ウィンドウタイトル
  - ステータス (`Active` / `Idle`)
  - 会議判定 (`meeting_status`, `meeting_tool`, `meeting_confidence`, `meeting_reasons`)
  - バックグラウンド会議アプリ (`running_meeting_apps`)
  - 集計除外フラグ (`analysis_excluded`: `Python`を除外しやすくするため)

## 開発ロードマップ

### Phase 1: MVP（まず動く版）

- [x] GitHub連携と初期README作成
- [x] 要件定義の整理
- [x] 最小トラッカー実装（Active window + Idle判定 + JSON保存）
- [ ] ローカル動作確認（30分程度）

### Phase 2: 運用しやすくする

- [ ] 起動・停止を簡単にする（スクリプト化）
- [ ] ログローテーション（ファイル分割）対応
- [ ] 設定ファイル化（間隔・Idle閾値・保存先）

### Phase 3: 解析連携

- [ ] 日次サマリ生成（作業アプリ・時間集計）
- [ ] AIエージェントが読みやすい整形データ出力
- [ ] 解析プロンプトひな形作成

## クイックスタート（現在）

1. `python3 src/tracker.py` を実行
2. `logs/activity_log.jsonl` に1行1レコードで追記される
3. 終了は `Ctrl + C`

## 開始・停止を簡単にする方法

- 開始: `bash scripts/start_tracker.sh`
- 停止: `bash scripts/stop_tracker.sh`

補足:

- バックグラウンド実行で記録を継続します。
- プロセスの標準出力は `logs/tracker_stdout.log` に保存されます。
- 実行状態の管理に `logs/tracker.pid` を使います。

## 初回セットアップ時の注意

- macOSの「プライバシーとセキュリティ」で、ターミナル（または実行環境）に
  「アクセシビリティ」権限を付与してください。
- 権限がない場合、アプリ名やウィンドウタイトルが取得できないことがあります。

## 現在の実装範囲

- 最前面アプリ名とウィンドウタイトル取得（macOS）
- 10分無操作で `Idle` 判定（`ioreg` ベース）
- Zoom/Google Meetの会議推定（Teams除外）
- JSON Lines形式（`*.jsonl`）でローカル追記保存
