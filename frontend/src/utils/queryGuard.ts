/**
 * 複数の取得（useQuery）を使う画面が「読み込み中か」「失敗したか」を判定するための共通部品。
 *
 * 従来は画面ごとに `a.isLoading || b.isLoading || ...` と `a.isError || b.isError || ...` が
 * 同じ形で並記されており、取得を1本増やすたびに複数の羅列へ書き足す必要があった。書き足しを
 * 忘れると、失敗しているのに読み込み中の表示のまま止まる。機械的に同じこの部分だけを
 * ここへ集約する（CODING_RULES.md「①DRYの原則」）。
 *
 * 一方「取得は成功したがデータが無い」の扱いは画面ごとに異なる。表示に必須の取得もあれば、
 * 取得できなくても `?? []` として扱い他カテゴリの表示を妨げない取得もあり、一律に判定すると
 * 振る舞いが変わる。データの有無は各画面のguard側で明示的に確認する（そうすることで
 * TypeScriptの絞り込みが効き、guardの戻り値へ非nullのまま載せられる）。
 */

/** useQueryの結果のうち、表示可否の判定に必要な部分だけを表す型。
 * react-queryの`UseQueryResult`と構造的に互換であり、テストからは素のオブジェクトを渡せる。 */
export type QueryLike<T> = {
  isLoading: boolean
  isError: boolean
  error: unknown
  data: T | undefined
}

/** 1本でも取得が進行中か。1本でも待っている間は、揃っている分だけを先に描画せず
 * 画面全体を読み込み中として扱う（途中まで描画してから差し替わるのを避ける）。 */
export function isAnyLoading(queries: readonly QueryLike<unknown>[]): boolean {
  return queries.some((query) => query.isLoading)
}

/** 最初に失敗した取得を返す（すべて成功していればundefined）。
 * 渡した順がそのままエラー表示の優先順になるため、呼び出し側は表示したい順に並べる。 */
export function findFailedQuery(
  queries: readonly QueryLike<unknown>[],
): QueryLike<unknown> | undefined {
  return queries.find((query) => query.isError)
}
