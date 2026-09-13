/** 時間スロットの設定（SlotList.tsx・DayTypeDefaultsCard.tsx）の選択肢。
 *
 * コンポーネントと同じファイルに置くと Fast Refresh が効かなくなるため
 * （oxlint react/only-export-components）、値だけをこのファイルへ分ける。
 * 型と配列の関係は features/goal/materialOptions.ts と同じ方針。 */
import type { components } from '../../types/api.d.ts'

type Environment = components['schemas']['Environment']

/** スロットが選べる環境。`ANY`（どこでもよい）は教材側の条件にしか無いため**意図的に除く**
 * （教材の ENVIRONMENTS とは別物。materialOptions.ts）。 */
export const SLOT_ENVIRONMENTS = ['PC', 'MOBILE'] as const satisfies readonly Environment[]
/** 0=月 始まりの曜日番号（`resources.weekdays.*` のキーに対応）。
 * 時間スロットの曜日指定と、日種別の既定設定（曜日ごとの計画日/バッファ日）で共用する。 */
export const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6] as const

export type SlotEnvironment = (typeof SLOT_ENVIRONMENTS)[number]
