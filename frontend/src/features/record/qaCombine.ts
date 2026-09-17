/**
 * 質問への回答と「自由に書く」欄を結合し、1本の本文として返す（仕様書6.5改、
 * 記録画面改善タスク2026-09-17）。
 *
 * 「自由に書く」はラベルを付けずそのまま連結する。従来の単一自由記述欄からの移行者
 * （質問欄に一切触れず「自由に書く」欄だけを使う利用者、および進捗のみ登録で保存済みの
 * 本文を引き継ぐ場合を含む）が、従来と全く同じ本文（ラベルなしの原文そのもの）を送信
 * し続けられるようにするため（後方互換。diary_body/recall_body/bodyの保存形式・AIへの
 * 注入内容を変えない）。
 *
 * @param questions 質問文の配列（カテゴリごとに固定、ロケールから取得）
 * @param answers 質問ごとの回答（questionsと同じ長さを想定。インデックス対応）
 * @param freeText 「自由に書く」欄の入力
 * @returns 結合済みの本文。すべて空なら空文字列
 *
 * @example
 * combineQaAnswers(['Q1', 'Q2'], ['A1', ''], '') // => '【Q1】\nA1'
 * combineQaAnswers(['Q1', 'Q2'], ['', ''], '自由記述') // => '自由記述'
 */
export function combineQaAnswers(questions: string[], answers: string[], freeText: string): string {
  const labeledAnswers = questions
    .map((question, index): [string, string] => [question, answers[index] ?? ''])
    .filter(([, answer]) => answer.trim() !== '')
    .map(([question, answer]) => `【${question}】\n${answer}`)
  const pieces = freeText.trim() !== '' ? [...labeledAnswers, freeText] : labeledAnswers
  return pieces.join('\n\n')
}

/** 質問への回答・自由記述のいずれかに入力があるか（離脱確認・確定可否の判定に使う）。 */
export function hasAnyQaInput(answers: string[], freeText: string): boolean {
  return freeText.trim() !== '' || answers.some((answer) => answer.trim() !== '')
}
