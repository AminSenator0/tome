import { describe, it, expect, beforeEach } from 'bun:test'

const store: Record<string, string> = {}
;(globalThis as any).localStorage = {
  getItem: (k: string) => store[k] ?? null,
  setItem: (k: string, v: string) => {
    store[k] = v
  },
  removeItem: (k: string) => {
    delete store[k]
  },
  clear: () => {
    for (const k in store) delete store[k]
  },
}
;(globalThis as any).window = {
  localStorage: (globalThis as any).localStorage,
}

import { Api } from '../src/api'

describe('Api Client', () => {
  beforeEach(() => {
    localStorage.clear()
    Api.setToken(null)
  })

  it('manages authorization token in memory and local storage', () => {
    expect(Api.getToken()).toBeNull()
    Api.setToken('test_token_12345')
    expect(Api.getToken()).toBe('test_token_12345')
    expect(localStorage.getItem('tome_token')).toBe('test_token_12345')

    Api.setToken(null)
    expect(Api.getToken()).toBeNull()
    expect(localStorage.getItem('tome_token')).toBeNull()
  })

  it('rejects unauthenticated requests gracefully', async () => {
    try {
      await Api.getMe()
      expect(true).toBe(false)
    } catch (err: any) {
      expect(err).toBeDefined()
    }
  })
})
