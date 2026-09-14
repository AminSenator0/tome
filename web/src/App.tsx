import React, { useState, useEffect } from 'react'
import { Api, User } from './api'
import { Navbar } from './components/Navbar'
import { Sidebar, TabType } from './components/Sidebar'
import { LoginView } from './views/LoginView'
import { BookshelfView } from './views/BookshelfView'
import { BookDetailView } from './views/BookDetailView'
import { PipelineView } from './views/PipelineView'
import { ToolsView } from './views/ToolsView'
import { PromptsView } from './views/PromptsView'
import { SettingsView } from './views/SettingsView'

export const App: React.FC = () => {
  const [user, setUser] = useState<User | null>(null)
  const [authChecking, setAuthChecking] = useState(true)
  const [isDark, setIsDark] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [currentTab, setCurrentTab] = useState<TabType>('bookshelf')
  const [selectedBookFolder, setSelectedBookFolder] = useState<string | null>(null)

  useEffect(() => {
    // 1. Auto-detect system theme on first visit
    const savedTheme = localStorage.getItem('tome_theme')
    let dark = true
    if (savedTheme) {
      dark = savedTheme === 'dark'
    } else {
      dark = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)').matches : true
    }
    setIsDark(dark)
    if (dark) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }

    const checkAuth = async () => {
      if (Api.getToken()) {
        try {
          const u = await Api.getMe()
          setUser(u)
        } catch {
          Api.setToken(null)
          setUser(null)
        }
      }
      setAuthChecking(false)
    }

    checkAuth()

    return () => {
    }
  }, [])

  const toggleTheme = () => {
    const nextDark = !isDark
    setIsDark(nextDark)
    if (nextDark) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('tome_theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('tome_theme', 'light')
    }
  }

  const handleLogout = async () => {
    await Api.logout()
    setUser(null)
    setSelectedBookFolder(null)
  }

  const handleLoginSuccess = async () => {
    const u = await Api.getMe()
    setUser(u)
  }

  const handleSelectBook = (folder: string) => {
    setSelectedBookFolder(folder)
  }

  const handleOpenBookFromPipeline = (folder: string) => {
    setCurrentTab('bookshelf')
    setSelectedBookFolder(folder)
  }

  if (authChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-muted-foreground">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!user) {
    return <LoginView onSuccess={handleLoginSuccess} />
  }

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground font-sans">
      <Navbar
        user={user}
        onLogout={handleLogout}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        isDark={isDark}
        onToggleTheme={toggleTheme}
      />

      <div className="flex-1 flex min-h-0">
        <Sidebar
          currentTab={currentTab}
          onSelectTab={(tab) => {
            setCurrentTab(tab)
            setSelectedBookFolder(null)
          }}
          isOpen={sidebarOpen}
          onCloseMobile={() => setSidebarOpen(false)}
        />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full overflow-y-auto">
          {selectedBookFolder ? (
            <BookDetailView
              bookFolder={selectedBookFolder}
              onBack={() => setSelectedBookFolder(null)}
              isDark={isDark}
            />
          ) : (
            <>
              {currentTab === 'bookshelf' && (
                <BookshelfView
                  onSelectBook={handleSelectBook}
                  onNavigateToPipeline={() => setCurrentTab('pipeline')}
                />
              )}
              {currentTab === 'pipeline' && (
                <PipelineView onOpenBook={handleOpenBookFromPipeline} />
              )}
              {currentTab === 'tools' && <ToolsView />}
              {currentTab === 'prompts' && <PromptsView />}
              {currentTab === 'settings' && <SettingsView />}
            </>
          )}
        </main>
      </div>
    </div>
  )
}
