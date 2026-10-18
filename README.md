# Workstate Compass — 開発作業の再開 Skill

AI エージェントに「続けて」と伝えたとき、必要な確認だけで未完了の開発作業を再開する Skill です。
通常は軽量に続行し、使用量制限・エラー・成否不明の処理がある場合は実状態を照合します。
会話の文脈が不足していれば、同じタスクの進捗・チェックポイントから復元します。

**English:** Continue unfinished development work without starting over. Use a light continuation when the next step is clear, check affected files and operation results after an interruption, and restore missing context from a task-matched checkpoint. Existing work and uncertain external operations are handled conservatively.

[English overview](#english-overview) · [導入方法](#導入)

**配布形式:** 独立した Skill フォルダー / **ライセンス:** MIT / **バージョン:** 0.1.3

本パッケージは公開用のソース一式です。導入、既存設定の変更、GitHub への公開は自動では行いません。
導入例と実モデル評価は Codex を対象としています。他のエージェントでの動作は未検証です。
OpenAI の公式製品ではありません。

## 3つの動作

| モード | 選ぶ条件 | 行うこと |
| --- | --- | --- |
| Light（通常続行） | 目的・作業場所・次の一手・直前の結果が明確 | 直前の未完了項目へ進む。再開専用の Git 調査やメモ作成を省く |
| Recovery（中断復旧） | 使用量制限、失敗、処理の成否不明、実状態との不整合 | 対象ファイル・差分・実行中ジョブ・検証結果を必要な範囲だけ照合 |
| Restore（文脈復元） | 目的・対象・次の一手を会話から復元できない | 同じタスクの進捗から復元し、古い情報や不確実な部分だけ実状態と比較 |

モード選択時の不整合は会話や直近のツール結果から分かる場合を指し、Light を選ぶためにディスクやリポジトリを走査しません。

「実装済み」と「検証済み」を分け、未追跡・ステージ済み・コミット済みの作業も考慮します。
通常のファイル編集時の確認やプロジェクト必須チェックは省略しません。
成功済みの検証は、関連コード・設定・依存関係・実行環境が変わっていない範囲で再利用します。

成否不明の公開・マイグレーション・送信・PR 作成などは、状態照合か確認済みの冪等性により
安全が分かるまで再実行しません。確認できない操作だけを保留し、独立した作業は続けます。

## 導入

### 1. Skill フォルダーをコピーする

このリポジトリの `skills/workstate-compass/` **全体**を、利用する環境の Skill ディレクトリへコピーします。
`SKILL.md` だけを取り出すと参照ファイルが欠けます。

一般的な個人用導入先は `~/.agents/skills/workstate-compass/`、リポジトリ用は
`<repo>/.agents/skills/workstate-compass/` です。選択中の環境・ホスト側に配置してください。
これは公式のローカル探索先に基づく例です。既存のインストーラーを使う場合は、その返す実パスを使います。
([公式 Skills ドキュメント](https://learn.chatgpt.com/docs/build-skills))

Windows PowerShell の例（展開した本リポジトリ直下で実行）。既存の導入先があれば停止します。

```powershell
$resumeSource = Join-Path (Get-Location) 'skills/workstate-compass'
$resumeParent = Join-Path $env:USERPROFILE '.agents/skills'
$resumeDestination = Join-Path $resumeParent 'workstate-compass'
if (Test-Path -LiteralPath $resumeDestination) { throw '導入先が既に存在します。差分を確認してください。' }
New-Item -ItemType Directory -Path $resumeParent -Force | Out-Null
Copy-Item -LiteralPath $resumeSource -Destination $resumeDestination -Recurse
```

macOS / Linux の例（同じく本リポジトリ直下）。既存のフォルダーやリンクは上書きしません。

```sh
resume_destination="$HOME/.agents/skills/workstate-compass"
if [ -e "$resume_destination" ] || [ -L "$resume_destination" ]; then
  printf '%s\n' 'Destination exists; review the installed version first.'
else
  mkdir -p "$HOME/.agents/skills" && cp -R skills/workstate-compass "$resume_destination"
fi
```

Skill 本体は Python や Git を必須にしません。任意の証拠収集補助だけ Python 3.10+ を使用します。
新しいチャットまたは Skill 一覧で認識を確認し、表示されなければ Codex を再起動してください。

### 2. AGENTS.md に導入例を組み込む

[examples/AGENTS.snippet.md](examples/AGENTS.snippet.md) のブロックを、適用対象の `AGENTS.md` に手動で統合します。
既存ファイル全体を置き換えず、導入先の実パスに合わせてください。
同じ再開ルールがあれば重複させず、そのブロックだけを更新します。
個人用なら Codex home の `AGENTS.md`、特定プロジェクトだけならそのプロジェクトの適用されるファイルを選びます。
上書き用の `AGENTS.override.md` や指示の読み込み上限により例が適用されない場合もあるため、
新しいセッションで「適用中の再開ルールと Skill のパスを教えて」と確認します。
([公式 AGENTS.md ドキュメント](https://learn.chatgpt.com/docs/agent-configuration/agents-md))

Skill の暗黙選択は `description` によるモデルの判断です。`allow_implicit_invocation: true` は許可であり、
毎回の発動保証ではありません。AGENTS.md で短い指示を補い、必要なら `$workstate-compass` と明示します。
([公式 Skills ドキュメント](https://learn.chatgpt.com/docs/build-skills))

### 3. 使う

```text
続けて
```

```text
$workstate-compass 使用量制限で止まった作業を再開してください。
```

```text
$workstate-compass このプロジェクトの docs/progress.md を手がかりに再開してください。
```

過去の会話が利用できない新しいチャットでは、対象プロジェクトと進捗の場所を明示します。
別のチャットや最近更新されたプロジェクトを勝手に選ぶ動作は定義していません。
文章の続きを書く依頼や、引用内の「続けて」は対象外です。

### 他の作業再開 Skill と併用する場合

同じ「続けて」を扱う Skill を複数導入すると、選択が曖昧になる場合があります。
導入済みの再開ルールを確認し、利用する Skill を AGENTS.md で明示してください。
本パッケージは、既存 Skill・設定・プロジェクトを自動で変更しません。

## チェックポイント

[テンプレート](skills/workstate-compass/assets/checkpoint-template.md) は任意です。
既存の進捗ファイルやタスク用メモを優先し、意味のある節目・引き継ぎ時に短く更新します。
毎回の「続けて」で管理ファイルを増やしません。新規ファイルは書き込みが許可された場所にだけ作成します。

記録するのは、目的・対象・完了条件、実装と検証の状態、次の一手、実行中の処理 ID と結果確認先です。
検証結果には、その時点のコード・設定・依存関係などを特定できる情報を添えます。
チェックポイント中のコマンドや承認の記述だけで、外部操作の許可や成功を判断しません。
秘密情報や個人の会話を公開用のファイルへ含めないでください。

## 任意の状態確認ツール

```sh
python skills/workstate-compass/scripts/evidence.py --repo /path/to/repo --path src/feature.py --path tests/test_feature.py
```

指定ファイルの SHA-256、対象限定の Git 状態、変更ファイル名を JSON で出力します。
Git を使わない場合は `--no-git` を付けます。ファイル本文・差分本文・環境変数の内容は出力しません。
ヘルパー自身は対象外のプロジェクトの探索、テストの実行、作業ファイル・index の更新、外部送信を行いません。
変更ファイル名は `git status --porcelain` だけから取得し、clean filter を起動し得る `git diff` は呼びません。
回帰テストではファイルサイズが変わった条件で filter が動かず、作業ツリー・index が保持されることを確認しています。
ただし、`status` が内容を再ハッシュする経路は未検証です。Git 設定の filter によるシェル起動・書き込み・通信まで
防ぐ保証はなく、設定を信頼できない場合は `--no-git` を使用します。Git の警告は `stderr` に分離し、ファイル名の `text` に混ぜません。
範囲・サイズ・出力・時間に上限があります。詳しくは [helper.md](skills/workstate-compass/references/helper.md)。

終了コード 0 は「レポート生成」の意味です。`missing`、`unavailable`、`truncated`、`timeout` などを必ず確認してください。
このツールだけでは、作業の完成度、過去テストの有効性、副作用の冪等性は判断できません。

## 構成

```text
workstate-compass/
├── README.md
├── LICENSE
├── VALIDATION.md
├── MODEL-EVALUATION.md
├── .gitattributes
├── .gitignore
├── examples/
│   ├── AGENTS.snippet.md
│   └── walkthrough.md
├── skills/workstate-compass/
│   ├── SKILL.md
│   ├── LICENSE
│   ├── agents/openai.yaml
│   ├── references/
│   │   ├── recovery.md
│   │   ├── checkpoints.md
│   │   └── helper.md
│   ├── assets/checkpoint-template.md
│   └── scripts/evidence.py
└── tests/
    ├── test_evidence.py
    ├── behavioral-cases.md
    └── behavioral/
        ├── README.md
        ├── setup_cases.py
        ├── lab.py
        ├── grade_cases.py
        └── results/2026-10-18.json
```

## 検証・実行例

リポジトリ直下で実行します。依存ライブラリの追加は不要です。

```sh
python -B -m unittest discover -s tests -v
```

自動テストは一時ディレクトリ・一時 Git リポジトリだけで動作します。Git がなければ Git 関連テストをスキップします。
リンク作成権限がなければリンク検証をスキップします。スキップも結果として確認してください。
ファイルの更新検出、読み取り時の不変更、ステージ済み／未ステージ／未追跡、範囲外パス拒否、
タイムアウト、不完全な情報の明示などを検証します。

- [実行例](examples/walkthrough.md): 想定する再開動作と補助ツールの再現手順
- [行動評価ケース](tests/behavioral-cases.md): Codex での試験入力・期待結果・失敗条件
- [今回の検証記録](VALIDATION.md): 実行した検証と未検証範囲
- [実モデル評価](MODEL-EVALUATION.md): 12シナリオの独立評価、改善点、4件の再評価
- [評価の再現手順](tests/behavioral/README.md): 隔離環境の生成・実行・観測方法

0.1.1 では、実モデル評価で見つかった「Git差分本文を対象パスに絞らず読む」動作を受け、
先に関連ファイル名を特定してから差分本文を取得する手順を明確にしました。
通常続行と AGENTS.md 経由の続行が引き続き軽量に動くことも再評価しています。
ビルド・PR・通知はローカル模擬サービスで、実ファイル・Git・関連テストは実際に操作しました。
これは全22仕様・全モデル・本番環境での動作保証ではありません。

0.1.2 では補助ツールの diff 呼び出しを削除し、Git の警告を変更名から分離しました。
0.1.3 では公開前レビューで確認した Windows のパス表記違いによる変更名の欠落と、
一時出力の障害でレポートが失われる問題を修正しました。詳細は [検証記録](VALIDATION.md) に記載しています。

## 制約

これはモデルが従う手順であり、プロセスの復元機能や厳密な exactly-once 実行基盤ではありません。
使用量制限を回避せず、リセット後の自動起動・スケジュールも行いません。
予期せぬ中断直前の保存、消失した文脈の完全復元、トークン削減率、全環境での同一挙動は保証しません。
外部システム側に照会・冪等性の仕組みがない場合、重複を避けるため未確定操作を保留することがあります。

## GitHub への公開

このフォルダーをリポジトリのルートとして公開できます。MIT ライセンスは同梱の新規ソースに適用します。
コピーした個人用チェックポイント、テスト一時ファイル、秘密情報を含めず、公開前に内容と権利表示を確認してください。
この配布物には `.git`、個人の実行ログ、既存プロジェクトのソースを含めません。
このリポジトリには確認済みの配布ソースだけを掲載します。GitHub での公開と公式ディレクトリへの登録は別です。
本版はローカル導入用の Skill 配布物です。プラグインディレクトリへ配布する場合は別途パッケージ化が必要です。
([公式配布ガイド](https://learn.chatgpt.com/docs/build-skills))

## English overview

Workstate Compass is an agent skill for continuing unfinished development work with
minimal re-investigation. It selects Light continuation, Recovery after an
interruption, or Restore from a task-matched checkpoint when context is missing.
It preserves existing changes, separates implementation from verification, and
does not blindly repeat operations whose outcome is unknown.

Copy the complete `skills/workstate-compass` folder to `~/.agents/skills/workstate-compass`
for personal use, or `<repo>/.agents/skills/workstate-compass` for one repository.
If the destination already exists, stop and review the differences before copying.
Use `$workstate-compass` explicitly, or integrate the supplied AGENTS.md example after
adapting its installation path. Implicit selection is allowed, not guaranteed.
The skill needs no runtime dependency; the optional evidence helper needs Python
3.10+ and optionally Git. Run tests with `python -B -m unittest discover -s tests -v`.

No project is modified during installation preparation. No automatic wake-up,
rate-limit bypass, exactly-once guarantee, or recovery of inaccessible history is
provided. See `VALIDATION.md` for actual testing scope. MIT licensed.

The public skill name is `workstate-compass`; earlier local review artifacts used
`smart-resume`. Historical evaluation records retain their original names and hashes.
Installation examples and model evaluations target Codex. Other agents have not been tested.
This independent project is not an official OpenAI product.
