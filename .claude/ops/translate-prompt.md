You are translating one Kaggle discussion/writeup document from English into Japanese.

Read: `@@SRC@@`
Write: `@@DEST@@`

Write the translation to that destination path with the Write tool. Do not edit
any other file. Do not run commands. Do not summarize the work back to me — the
file you write is the entire deliverable.

## The one rule that matters

**Translate the whole document. Do not summarize, condense, or skip.**

This exists so a human can read the author's actual argument in Japanese. A
summary defeats the purpose: the detail that turns out to matter is almost never
the one a summarizer keeps. Every section, every sentence, every table row,
every numbered list item in the source appears in the output. If the source is
600 lines, the translation is roughly 600 lines. Translating fewer sections than
the source has is a failed run, not a shorter one.

## Structure — mirror the source exactly

- Keep the heading hierarchy, the ordering, and the horizontal rules as they are.
- Keep every table, with the same rows and columns. Translate the cell text;
  leave numbers alone.
- **Do not translate code.** Code blocks, identifiers, file paths, CLI flags,
  library names, metric names and column names stay verbatim in English. You may
  translate a comment *inside* a code block if it is prose.
- **Copy every image line character-for-character**, including its path
  (`![...](../assets/...)`). Keep it in the same position in the document. The
  paths are rewritten automatically afterwards — if you "fix" them, you break
  them. Never invent an image reference that is not in the source.
- Keep LaTeX/math as-is.
- Preserve emphasis (`**bold**`, `*italic*`) and blockquotes.

## The header block

Reproduce the source's metadata block at the top, in Japanese, immediately after
the `# ` title:

```
> **著者**: <name> ／ **投稿日**: <YYYY-MM-DD> ／ **votes**: <n> ／ **コメント**: <n>
> **原文**: <the Source URL from the header, unchanged>
```

Then `---`, then the translated body. Author names, @handles and team names are
never translated.

## The comment thread at the tail

The source ends with a `## Comments (n)` section: the reply thread, attached to
the body it belongs to. Translate it as `## コメント欄` at the end of your
output, keeping one `###` heading per comment with the author, date and votes
unchanged.

Two allowances, and only these two:

- If a comment is purely congratulatory ("great work!", "congrats!"), you may
  drop it — but then state at the top of `## コメント欄` how many were dropped
  and why, e.g. `技術的な内容を含むコメントはなく、10件はすべて祝辞でした。`
- If the source has no `## Comments` section, omit `## コメント欄` entirely.

Anything with technical content — a correction, a hyperparameter, a follow-up
question the author answered — gets translated in full. Those replies are
frequently where the post's actual errata live.

## Register

Plain 常体 (だ・である), the way a Japanese engineer writes a technical postmortem.
Keep established English terms in English where a Japanese ML engineer would
(GroupKFold, out-of-fold, ensemble, U-Net, pseudo-label, leakage …). Translate
ordinary prose fully — a half-translated sentence is worse than either language
alone. Where the author is hedging or uncertain, keep the hedge; do not upgrade
"we think this helped" into "this helped".

If a passage is genuinely ambiguous, translate your best reading and add a brief
`<!-- 訳注: ... -->` comment rather than silently choosing.
