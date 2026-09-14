import React, { useState } from 'react'
import { ArrowRight, Lock, User as UserIcon } from 'lucide-react'
import { Api } from '../api'
import { Button } from '../components/ui/Button'
import { Logo } from '../components/ui/Logo'

interface LoginViewProps {
  onSuccess: () => void
}

export const LoginView: React.FC<LoginViewProps> = ({ onSuccess }) => {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      await Api.login(username, password)
      onSuccess()
    } catch (err: any) {
      setError(err.message || 'Invalid username or password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-background select-none">
      <div className="w-full max-w-sm rounded-3xl bg-card p-8 space-y-6 soft-shadow border-0">
        <div className="flex flex-col items-center text-center space-y-3">
          <Logo size={48} withText={false} />
          <div className="space-y-1">
            <h1 className="text-xl font-semibold tracking-tight text-foreground">
              Sign in to Tome
            </h1>
            <p className="text-xs text-muted-foreground">
              Enter your credentials to access your library
            </p>
          </div>
        </div>

        {error && (
          <div className="p-3 rounded-2xl bg-destructive/15 text-destructive text-xs text-center font-medium">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground px-1">
              Username
            </label>
            <div className="relative">
              <UserIcon className="absolute left-3.5 top-3.5 h-4 w-4 text-muted-foreground" strokeWidth={1.5} />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Username"
                className="w-full h-11 rounded-2xl border-0 bg-secondary pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground px-1">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3.5 top-3.5 h-4 w-4 text-muted-foreground" strokeWidth={1.5} />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                className="w-full h-11 rounded-2xl border-0 bg-secondary pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              />
            </div>
          </div>

          <div className="pt-2">
            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={loading}
              className="w-full justify-center text-sm font-medium"
            >
              <span>Sign In</span>
              <ArrowRight className="h-4 w-4 ml-1.5" strokeWidth={1.5} />
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
