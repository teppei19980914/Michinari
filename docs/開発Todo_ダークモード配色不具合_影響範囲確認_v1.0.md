# 開発TODO：ダークモード配色不具合（文字の背景色同化）の影響範囲確認

作成日: 2026-10-25
対象: 2026-10-24のセッションで報告された「目標相談チャット（S09）のAI回答がダークモードで背景と同化して読みにくい」不具合について、同根バグの他箇所への残存有無を`frontend/src`全体でフルスキャンし、影響範囲を確定したもの。
前提: 0〜3章は影響範囲確認時点（コード変更なし）の記録。ユーザー承認を受け、4章の残TODO2件は2026-10-25に対応済み（詳細は4章・5章）。

---

## 0. スキャン範囲・方法

- 対象: `frontend/src`配下の全ソース（`.tsx`/`.ts`、テストファイルは除外）。
- 手法:
  1. 元不具合の原因特定（`MarkdownText.tsx`の`prose`クラス定義を確認、`dark:prose-invert`が無いことを確認）。
  2. `prose`クラスの使用箇所を`Grep`で全量確認（横展開先の特定）。
  3. 同じ不具合クラス（セマンティックカラートークンを使わず、Tailwindの生パレット色を直書きしている箇所）を`Grep`で網羅的に抽出し、1件ずつ「背景色は理論に追従するが文字色（またはその逆）が固定されたままで、ダークモードで同化・不自然になるか」を確認。
  4. `index.css`のダークモード設計（`[data-theme='dark']`属性＋セマンティックトークン、`@custom-variant dark`）を踏まえ、各箇所が「自己完結した固定チップ（背景色・文字色が同じ基準でペア指定されており理論に関係なく成立する）」か「理論追従する周囲とペアが崩れている箇所」かを判定。

---

## 1. 元不具合（事実確認・未修正）

### 1.1 根本原因

[frontend/src/components/MarkdownText.tsx:15](../frontend/src/components/MarkdownText.tsx#L15)

```tsx
<div className={`prose prose-sm prose-gray max-w-none ${className}`}>
```

AI回答等のMarkdown本文を`@tailwindcss/typography`の`prose`（`prose-gray`固定）で描画している。このプラグインは`<p>`・`<li>`等の子要素に**ライトモード専用の固定色**（本文=gray-700相当、見出し=gray-900相当）を直接`color`指定するため、呼び出し側が渡す`text-text-primary`等のセマンティックカラー（ダークモードで`#f9fafb`に切り替わるトークン）が子要素側で上書きされる。背景（`--surface`）はダークモードで`#111827`に切り替わる一方、文字色だけがライト用の暗いグレー固定のままになるため、暗い背景に暗い文字が乗り同化する。

ダークモード自体は`[data-theme='dark']`属性＋`@custom-variant dark`（[frontend/src/index.css:7](../frontend/src/index.css#L7)）で正しく切替済みで、`ThemeProvider.tsx`が`<html data-theme="dark">`を設定していることも確認済み。問題は`MarkdownText.tsx`が`prose`にダークモード対応の指定（`dark:prose-invert`）を一切持たない点のみ。

### 1.2 影響箇所（`prose`の使用は`MarkdownText.tsx`の1箇所のみ、呼び出し元は5画面）

`Grep "prose" frontend/src`で全量確認。`prose`クラスの定義点は`MarkdownText.tsx`の1箇所のみのため、修正もそこに閉じる（横展開漏れの心配はない）。呼び出し元（＝実際にダークモードで読みにくくなる画面）は以下5件。

| 呼び出し元 | 画面 | 渡しているclassName |
| --- | --- | --- |
| [features/goalConsultation/GoalConsultationAnswer.tsx:43](../frontend/src/features/goalConsultation/GoalConsultationAnswer.tsx#L43) | 目標詳細「目標相談」タブ（S09、今回報告された画面） | `text-sm text-text-primary` |
| [features/helpAssistant/HelpAssistantAnswer.tsx:50](../frontend/src/features/helpAssistant/HelpAssistantAnswer.tsx#L50) | ヘルプAIアシスタント回答 | `text-sm text-text-primary` |
| [features/dashboard/WeeklyDigestSection.tsx:36](../frontend/src/features/dashboard/WeeklyDigestSection.tsx#L36) | ダッシュボード「先週のまとめ」AI要約 | `mt-1 text-text-primary` |
| [pages/RecapThemeDetailPage.tsx:95](../frontend/src/pages/RecapThemeDetailPage.tsx#L95) | 振り返りテーマ詳細本文 | `text-text-primary` |
| [features/export/RetrospectiveSection.tsx:61](../frontend/src/features/export/RetrospectiveSection.tsx#L61) | ナレッジエクスポート「総括レポート」 | `text-text-secondary` |

いずれも同一の原因・同一の修正点（`MarkdownText.tsx`側で`dark:prose-invert`を追加）で解消できる見込み（本プロジェクトは`@custom-variant dark`を`[data-theme='dark']`に紐づけ済みのため、`dark:`バリアントは`prose-invert`にもそのまま適用できる）。現時点でこの5画面は**未修正**。

---

## 2. 横展開チェックで新たに見つかった不具合（1件）

### 2.1 `TodayQuotaSection.tsx`のdivider（独立した別件、優先度は低）

[frontend/src/features/dashboard/TodayQuotaSection.tsx:39](../frontend/src/features/dashboard/TodayQuotaSection.tsx#L39)

```tsx
<ul className="divide-y divide-gray-100">
```

本日のノルマ一覧（ダッシュボード）の項目間区切り線が、セマンティックトークン（`border`/`border-strong`）を使わずTailwindの生パレット`gray-100`（ライト専用の極薄グレー）を直書きしている。`divide-`ユーティリティの使用は`Grep`で確認した限り**この1箇所のみ**（横展開先なし）。文字の視認性には影響しないが、ダークモードの暗い背景（`#111827`）に対して区切り線だけが理論を無視した明るい色で浮いて見える、設計トークンから外れた孤立した逸脱。元不具合（文字色のプロパティ上書き）とは発生箇所もパターンも別だが、「セマンティックトークンではなくTailwindの生パレット色を直書きしてダークモード対応から漏れる」という**同じ不具合クラス**に属するため、今回のスキャンで合わせて計上する。

---

## 3. 横展開チェックで確認し、対象外と判定したもの（誤検知の除外）

`Grep`で「Tailwindの生パレット色（`text-gray-700`等）の直書き」「`bg-white`/`text-black`等の無彩色直書き」「インラインの16進色」を網羅的に抽出し、1件ずつ「背景色と文字色がペアで固定されており理論に関係なく成立する自己完結パターンか」を確認した。以下はいずれも**対象外**（修正不要）と判定。

| ファイル | 内容 | 対象外と判定した理由 |
| --- | --- | --- |
| [features/goal/goalCategoryBadge.ts](../frontend/src/features/goal/goalCategoryBadge.ts) | 目標種別バッジ（`bg-blue-100 text-blue-800`等） | 背景色・文字色とも固定でペア指定されており、ページの理論に関係なく自己完結して成立する。`index.css:33-34`のコメント通り、意味を持つ固定色として意図的に理論から独立させている設計 |
| [features/bookshelf/bookStatusVariant.ts](../frontend/src/features/bookshelf/bookStatusVariant.ts) | 本棚バッジ・背表紙の配色 | `BOOK_STATUS_BADGE_CLASS`はバッジと同じ自己完結パターン。`BOOK_SPINE_ACCENT_CLASS`（`text-white`）は`SPINE_HUE_CLASSES`（`bg-amber-700`等、700〜800番台の濃色のみ）とセットで使われる前提で、白文字との組はいずれの理論でも成立する |
| [features/bookshelf/BookShelfSection.tsx](../frontend/src/features/bookshelf/BookShelfSection.tsx) | 木目調の棚板グラデーション | 既に`dark:from-amber-950/70`等、ダークモード用の指定がコード中に明示的に存在する（コメントでも「ダークモードでは濃い木目に切り替える」と設計意図を明記済み）。対応済み |
| [components/Toast.tsx](../frontend/src/components/Toast.tsx) | トースト通知の背景色（`bg-overlay-strong`/`bg-red-600`） | infoは理論に追従させない固定チップとして意図的に設計（コード内コメントで明記）。errorの`bg-red-600`+`text-white`は自己完結ペアで、どちらの理論でも視認性が保たれる |
| [features/analytics/GanttTab.tsx](../frontend/src/features/analytics/GanttTab.tsx) | ガントチャートの「本日」マーカー線（`bg-red-500`） | 文字ではなく装飾的な縦線で、`bg-surface-muted`のトラック上に乗るだけのため、どちらの理論でも視認性に問題なし |
| [components/Button.tsx](../frontend/src/components/Button.tsx) / [components/Modal.tsx](../frontend/src/components/Modal.tsx) / [components/LoadingOverlay.tsx](../frontend/src/components/LoadingOverlay.tsx) / [components/Tooltip.tsx](../frontend/src/components/Tooltip.tsx) / [features/record/ChatPanel.tsx](../frontend/src/features/record/ChatPanel.tsx) / [features/analytics/QualityTrendTab.tsx](../frontend/src/features/analytics/QualityTrendTab.tsx) / [features/bookshelf/BookSpineCard.tsx](../frontend/src/features/bookshelf/BookSpineCard.tsx) | ボタン・モーダル背景幕・ローディング幕・ツールチップ等の`bg-accent text-white`／`bg-black/40`／`bg-overlay-strong text-white`等 | いずれも背景色・文字色が同じ基準でペア指定された自己完結パターン（アクセント色や理論非追従の固定オーバーレイ色＋白文字）で、周囲の理論追従色とペアが崩れている箇所ではない |
| [features/analytics/chartColors.ts](../frontend/src/features/analytics/chartColors.ts) | グラフの罫線・軸線色（インライン16進色） | `isDarkTheme()`で`document.documentElement.dataset.theme`を見て明暗の値を自前で切り替える設計が既に実装済み（SVG属性としてCSS変数を安定解決できないReChartsの制約への対応とコードコメントに明記）。系列色（`CYCLE_SERIES_COLORS`）はCVD安全性検証済みパレットのため理論非依存が意図的 |

**結論**: 「セマンティックトークンを使わず理論追従しない固定色を直書きしたことで、周囲とのペアが崩れ視認性が落ちる」という不具合パターンは、1章の`MarkdownText.tsx`（5画面に影響）と2章の`TodayQuotaSection.tsx`（1箇所）の2件のみ。それ以外に同クラスの不具合は残存しない。横展開漏れなし。

---

## 4. 残TODO（2026-10-25 対応済み）

- [x] `MarkdownText.tsx`（[frontend/src/components/MarkdownText.tsx:15](../frontend/src/components/MarkdownText.tsx#L15)）のclassNameに`dark:prose-invert`を追加し、ダークモードでAI回答等のMarkdown本文が背景と同化しないようにした。呼び出し元（影響5画面、1.2参照）は変更せず、共通部品側の修正のみで解消（ビルド後のCSSで`.dark\:prose-invert:where([data-theme=dark],...)`が`--tw-prose-body`等をinvert値へ切り替えることを`npm run build`の出力CSSで実機確認済み）。回帰防止として`MarkdownText.test.tsx`を新規作成し、`dark:prose-invert`クラスの存在と、呼び出し元から渡した`className`が維持されることを固定した（従来この部品に専用テストが無かったため、クラス変更時の検知手段を併せて用意した）。
- [x] `TodayQuotaSection.tsx`（[frontend/src/features/dashboard/TodayQuotaSection.tsx:39](../frontend/src/features/dashboard/TodayQuotaSection.tsx#L39)）の`divide-gray-100`をセマンティックトークン`divide-border`へ置き換えた（他の一覧・罫線が揃って使っている`border-border`と同じトークン、3章参照）。`TodayQuotaSection.test.tsx`に、区切り線が`divide-border`を使い`divide-gray-100`を含まないことを固定するテストを追加した。
- [x] 上記2件の修正後、フロントエンド全体のlint（`npm run lint`）・型検査（`npx tsc --noEmit`）・テスト（`npm run test`、カバレッジ付き）を実行し、デグレが無いことを確認した（結果は5章）。

### 再発防止についての所感（参考、対応要否は要判断）

今回の2件はいずれも「背景はセマンティックトークンで理論追従するが、文字色・罫線色だけがTailwindの生パレット色で固定されたまま」という共通パターンで発生していた。`CODING_RULES.md`の`style-reviewer`/`label-checker`はハードコード文言・命名規約が対象で、この種の配色トークン逸脱は現状レビュー対象外。再発防止として、PRレビュー観点（または`style-reviewer`の対象拡大）に「新規追加されたTailwindクラスに`-gray-`/`-white`/`-black`等の生パレット色が含まれていないか」を加えることが考えられるが、要否はユーザー判断に委ねる。

---

## 5. 対応結果（2026-10-25）

### 5.1 変更内容
- [frontend/src/components/MarkdownText.tsx](../frontend/src/components/MarkdownText.tsx): `prose prose-sm prose-gray max-w-none` → `prose prose-sm prose-gray max-w-none dark:prose-invert`。あわせて、なぜ`dark:prose-invert`が要るかをコード内コメントに追記（CODING_RULES.mdのコメント方針「WHYが非自明な箇所のみ」に従う）。
- [frontend/src/features/dashboard/TodayQuotaSection.tsx](../frontend/src/features/dashboard/TodayQuotaSection.tsx): `divide-y divide-gray-100` → `divide-y divide-border`。
- [frontend/src/components/MarkdownText.test.tsx](../frontend/src/components/MarkdownText.test.tsx): 新規作成（本文描画・`dark:prose-invert`付与・呼び出し元classNameの合成を固定）。
- [frontend/src/features/dashboard/TodayQuotaSection.test.tsx](../frontend/src/features/dashboard/TodayQuotaSection.test.tsx): 区切り線のクラスを固定するテストを1件追加。

呼び出し元5画面（1.2参照）・`goalCategoryBadge.ts`等3章で対象外と判定した箇所には変更を加えていない（横展開範囲の通りで過不足なし）。

### 5.2 検証結果
- `npm run build`: 成功。出力CSS（`dist/assets/index-*.css`）に`.dark\:prose-invert:where([data-theme=dark],[data-theme=dark] *){--tw-prose-body:var(--tw-prose-invert-body);...}`および`.divide-border>:not(:last-child)){border-color:var(--border)}`が生成されていることを`grep`で実機確認（`--border`は`index.css`でダークモード時`#374151`に切り替わるトークン）。
- `npm run test`（カバレッジ付き、フロントエンド全体）: **158 test files / 1363 tests 全通過**。カバレッジ**Statements/Branches/Functions/Lines いずれも100%**を維持。
- `npm run lint`（oxlint）: 警告0件。
- `npx tsc --noEmit`: エラー0件。
- バックエンドは対象外（フロントエンドのみの変更のため無変更、`pytest`/`ruff`の再実行は不要と判断）。

### 5.3 デグレ判定
上記の結果から、今回の2件の修正によるデグレは検出されなかった。
