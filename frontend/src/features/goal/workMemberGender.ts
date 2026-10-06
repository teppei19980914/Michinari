/** チームメンバーの性別の選択肢（任意入力、要件定義書6.11）。
 * 部品（WorkMemberFormFields.tsx）と分けてあるのは、React Fast Refresh が「コンポーネントだけを
 * export するファイル」を要求するため。 */
export const GENDER_OPTIONS = ['MALE', 'FEMALE', 'OTHER'] as const
export type GenderOption = (typeof GENDER_OPTIONS)[number]
