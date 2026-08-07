# 長時間ジョブの回し方

コンペでは「1 時間以上かかるローカルジョブ」が普通に出てくる。
素直に走らせると**セッションの都合で殺される**ので、切り離して走らせる。

## バックグラウンドタスクはターン終了後に kill されうる

エージェントのバックグラウンド実行はセッションのターン境界で終了させられる
ことがある。学習を 3 時間回したつもりが 5 分で消えている、という失われ方をする。

**対策: プロセスをセッションから切り離す。**

```bash
nohup uv run python scripts/train.py --fold 0 > logs/train_f0.log 2>&1 &
disown
echo $!   # PID を控える
```

`nohup` で SIGHUP を無視させ、`disown` でジョブテーブルから外す。
これでセッションが終わってもプロセスは生き残る。

## 監視は wakeup で行い、ポーリングで待たない

`sleep` で待つのは時間の無駄で、しかも待っている間セッションは何もできない。
**ScheduleWakeup（または同等の再開機構）で、実際の所要時間に見合った間隔で
起こしてもらう。**

- 8 分の CI なら 1 回 ~480 秒で見に行く。60 秒ポーリング 8 回ではない
- 何を待っているか分からないなら 20〜30 分間隔
- 進捗確認は軽く: `tail -5 logs/train_f0.log` と `ps -p <PID>` で足りる

```bash
# 生存確認と進捗
ps -p "$PID" >/dev/null && echo "running" || echo "finished/dead"
tail -5 logs/train_f0.log
```

## 完了を「静かな失敗」と区別する

プロセスが消えたことと、正常終了したことは違う。ログの末尾だけを見て
「終わった」と判断しない。**終了コードか、成果物の存在で判定する。**

```bash
nohup bash -c 'uv run python scripts/train.py; echo "EXIT=$?" >> logs/train_f0.log' \
  > /dev/null 2>&1 &
disown
```

こうしておけば `grep EXIT= logs/train_f0.log` で確実に判定できる。

## 定期実行はセッションに持たせない

「毎日これを走らせる」はセッション内のスケジューラで組まないこと。

- セッション限定のスケジュールは**失効する**（7 日程度）
- **複数セッションで重複する** — 2 つのセッションがそれぞれ実行し、
  それぞれ commit して push する

macOS なら launchd（LaunchAgent）に持たせる。1 マシン 1 つなので構造的に
重複せず、セッションの生死と無関係に動き、`launchctl list` で確認できる。
実装済みのハーネスが `.claude/ops/` にある — [README](../../ops/README.md) を参照。

## 無人ジョブに判断を入れない

定期ジョブがやるのは**取得・記録・差分を見えるようにすること**まで。
「この結果は何を意味するか」の判断は、人が見ている対話セッションに残す。

無人でエージェントを走らせる必要がある場合は権限を絞る:

```bash
claude -p "$(cat prompt.md)" \
  --permission-mode acceptEdits \
  --allowedTools Read Grep Glob WebSearch Edit Write \
  --disallowedTools Bash Task \
  --max-turns 45
```

Bash と Task を落とすと、学習実行・提出・サブエージェント起動ができなくなる。
git 操作は呼び出し元の wrapper でやる — そちらの方が監査しやすい。

## 関連

- [kaggle-gpu-kernels.md](kaggle-gpu-kernels.md) — Kaggle 側の実行時間上限とクォータ
- [../../ops/README.md](../../ops/README.md) — 定期実行ハーネスの実装
