/** 全画面に出す「ヘルプに質問する」ボタンと、開いたドロワーの切り替え（Phase43、開発Todo F-04）。 */
import { useState } from 'react'
import { Button } from '../../components/Button'
import { t } from '../../locales/t'
import { HelpAssistantDrawer } from './HelpAssistantDrawer'

export function HelpAssistantLauncher() {
  const [open, setOpen] = useState(false)

  return (
    <>
      {!open && (
        <div className="fixed bottom-4 right-4 z-30">
          <Button onClick={() => setOpen(true)}>
            {t('helpAssistant.launcherLabel')}
          </Button>
        </div>
      )}
      {open && <HelpAssistantDrawer onClose={() => setOpen(false)} />}
    </>
  )
}
