import React from 'react'
import { useI18n } from '../lib/i18n'
import { ThemeToggle } from './ThemeToggle'
import { LanguageSwitcher } from './LanguageSwitcher'
import { MobileMenuButton } from './MobileMenuButton'

interface NavbarProps {
  onMenuClick: () => void
  isSidebarOpen: boolean
  currentTabName?: string
  userName?: string
  onSignOut: () => void
}

export const Navbar: React.FC<NavbarProps> = ({
  onMenuClick,
  isSidebarOpen,
  currentTabName = 'Overview',
  userName,
  onSignOut,
}) => {
  const { t } = useI18n()

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/80 backdrop-blur-md">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-2">
          <MobileMenuButton onClick={onMenuClick} isOpen={isSidebarOpen} />
          <h2 className="text-lg font-semibold tracking-tight text-foreground">
            {currentTabName}
          </h2>
        </div>

        <div className="flex items-center gap-1.5 sm:gap-3">
          <LanguageSwitcher />
          <ThemeToggle title={t('nav.toggleTheme')} />
          <div className="h-6 w-px bg-border mx-1 hidden sm:block" />
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-foreground hidden sm:block">
              {userName}
            </span>
            <button
              onClick={onSignOut}
              className="inline-flex items-center justify-center rounded-full text-xs font-medium transition-colors hover:bg-accent hover:text-accent-foreground h-9 px-3 text-muted-foreground border-0 cursor-pointer"
            >
              {t('nav.signOut')}
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}
