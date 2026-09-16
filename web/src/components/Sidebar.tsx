import React from 'react'
import {
  Library,
  Layers,
  Wrench,
  FileCode2,
  BarChart3,
  Settings,
  Languages,
  ChevronLeft,
} from 'lucide-react'
import { Logo } from './ui/Logo'
import { useI18n } from '../lib/i18n'

export type TabType = 'bookshelf' | 'pipeline' | 'tools' | 'prompts' | 'metrics' | 'settings'

interface SidebarProps {
  currentTab: TabType
  onSelectTab: (tab: TabType) => void
  isOpen: boolean
  onCloseMobile: () => void
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  isOpen,
  onCloseMobile,
}) => {
  const { t, lang, setLang } = useI18n()

  const menuItems = [
    { id: 'bookshelf' as TabType, label: t('nav.bookshelf'), icon: Library },
    { id: 'pipeline' as TabType, label: t('nav.pipeline'), icon: Layers },
    { id: 'metrics' as TabType, label: t('nav.metrics'), icon: BarChart3 },
    { id: 'tools' as TabType, label: t('nav.tools'), icon: Wrench },
    { id: 'prompts' as TabType, label: t('nav.prompts'), icon: FileCode2 },
    { id: 'settings' as TabType, label: t('nav.settings'), icon: Settings },
  ]

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm lg:hidden transition-opacity"
          onClick={onCloseMobile}
        />
      )}

      <aside
        className={`fixed lg:sticky top-0 lg:top-16 bottom-0 left-0 z-[70] lg:z-30 w-64 lg:h-[calc(100vh-4rem)] bg-sidebar flex flex-col transition-transform duration-300 ease-in-out select-none border-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="flex h-16 items-center justify-between px-6 lg:hidden">
          <Logo size={24} withText={true} />
          <button
            onClick={onCloseMobile}
            className="p-2 text-muted-foreground hover:text-foreground rounded-full hover:bg-secondary transition-colors"
          >
            <ChevronLeft className="h-5 w-5" strokeWidth={1.5} />
          </button>
        </div>

        <div className="p-4 space-y-4 flex-1 overflow-y-auto custom-scrollbar">
          <div className="px-3 pt-2 pb-1">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              {t('menu.label')}
            </span>
          </div>

          <nav className="space-y-1.5">
            {menuItems.map((item) => {
              const Icon = item.icon
              const active = currentTab === item.id

              return (
                <button
                  key={item.id}
                  onClick={() => {
                    onSelectTab(item.id)
                    onCloseMobile()
                  }}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-full text-sm font-medium transition-all text-left border-0 ${
                    active
                      ? 'bg-foreground text-background shadow-xs'
                      : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
                  }`}
                >
                  <Icon
                    className="h-5 w-5 shrink-0"
                    strokeWidth={1.5}
                  />
                  <span>{item.label}</span>
                </button>
              )
            })}
          </nav>
        </div>
        <div className="p-4 border-t border-border/40">
          <button
            onClick={() => setLang(lang === 'fa' ? 'en' : 'fa')}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-full text-xs font-medium bg-secondary text-muted-foreground hover:text-foreground transition-colors border-0 cursor-pointer"
          >
            <Languages className="h-4 w-4" strokeWidth={1.5} />
            <span>{t('lang.switch')}</span>
          </button>
        </div>
      </aside>
    </>
  )
}
