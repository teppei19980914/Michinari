/** 復習クイズの進行状況（テスト容易性のためJSXから分離、CODING_RULES.md）。
 * 問題集（単語帳）と共通の判定のため`utils/sessionProgress.ts`へ切り出し済み、
 * ここでは既存の呼び出し元（QuizSession.tsx）との互換のため re-export する。 */
export { isLastQuestion, nextIndex } from '../../utils/sessionProgress'
