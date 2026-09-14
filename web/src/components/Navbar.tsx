import React from 'react'
import { Menu, Moon, Sun, LogOut, ChevronRight, Home, User } from 'lucide-react'
import { Logo } from './ui/Logo'

interface NavbarProps {
  onToggleSidebar: () => void
  isDark: boolean
  onToggleTheme: () => void
  user: any
  onLogout: () => void
  currentTabName: string
  bookTitle?: string
}

export const Navbar: React.FC<NavbarProps> = ({
  onToggleSidebar,
  isDark,
  onToggleTheme,
  user,
  onLogout,
  currentTabName,
  bookTitle,
}) => {
  return (
    <header className="sticky top-0 z-50 w-full bg-background/95 backdrop-blur-xl select-none border-b border-muted/20">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onToggleSidebar}
            className="inline-flex lg:hidden items-center justify-center p-2 rounded-full text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
          >
            <Menu className="h-5 w-5" strokeWidth={1.5} />
          </button>

          <Logo size={28} withText={true} className="hidden lg:flex" />

          <div className="h-4 w-px bg-muted hidden lg:block mx-2 opacity-50" />

          <nav className="hidden md:flex items-center gap-2 text-sm text-muted-foreground">
            <Home className="h-4 w-4 opacity-60" strokeWidth={1.5} />
            <ChevronRight className="h-3.5 w-3.5 opacity-40" />
            <span className="text-foreground font-medium capitalize">{currentTabName}</span>
            {bookTitle && (
              <>
                <ChevronRight className="h-3.5 w-3.5 opacity-40" />
                <span className="text-foreground font-medium truncate max-w-[200px]">{bookTitle}</span>
              </>
            )}
          </nav>
        </div>

        <div className="flex items-center gap-2.5">
          {user && (
            <div className="flex items-center gap-2 h-10 px-4 rounded-full bg-secondary text-muted-foreground text-sm font-medium">
              <User className="h-4 w-4 text-muted-foreground" />
              <span className="capitalize">{user.username}</span>
            </div>
          )}

          <button
            type="button"
            onClick={onToggleTheme}
            className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-secondary text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            title="Toggle theme"
          >
            {isDark ? <Sun className="h-4 w-4" strokeWidth={1.5} /> : <Moon className="h-4 w-4" strokeWidth={1.5} />}
          </button>

          {user && (
            <button
              type="button"
              onClick={onLogout}
              className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-secondary text-muted-foreground hover:text-destructive hover:bg-destructive/15 transition-colors"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" strokeWidth={1.5} />
            </button>
          )}
        </div>
      </div>
    </header>
  )
}
