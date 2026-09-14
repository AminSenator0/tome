export interface User {
  id: number
  username: string
  is_admin: boolean
}

export interface BookSummary {
  folder: string
  title: string
  authors: string[]
  genre: string
  year?: string
  reading_time?: string
  page_count: number
  word_count: number
  synopsis?: string
  keywords?: string[]
  total_chapters: number
  translated_chapters: number
  image_count: number
  has_docx: boolean
  has_pdf: boolean
  has_original: boolean
  original_filename?: string
  has_glossary: boolean
  has_graph: boolean
  has_metrics: boolean
  total_tokens: number
  total_cost_toman: number
}

export interface BookDetail {
  folder: string
  metadata: Record<string, any>
  metrics: Record<string, any>
  chapters: {
    slug: string
    filename: string
    is_translated: boolean
    word_count: number
  }[]
  glossary: string
  graph: string
  images: string[]
  has_docx: boolean
  has_pdf: boolean
}

const getStorageItem = (key: string): string | null => {
  if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
    return localStorage.getItem(key)
  }
  return null
}

const setStorageItem = (key: string, val: string | null): void => {
  if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
    if (val === null) localStorage.removeItem(key)
    else localStorage.setItem(key, val)
  }
}

export class Api {
  private static token: string | null = getStorageItem('tome_token')

  static setToken(token: string | null) {
    this.token = token
    setStorageItem('tome_token', token)
  }

  static getToken(): string | null {
    return this.token
  }

  static async request<T = any>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string> || {}),
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    const res = await fetch(endpoint, {
      ...options,
      headers,
    })

    if (res.status === 401) {
      this.setToken(null)
      throw new Error('Authentication required')
    }

    if (!res.ok) {
      let msg = `HTTP error ${res.status}`
      try {
        const errJson = await res.json()
        if (errJson.detail) msg = errJson.detail
      } catch {
        // ignore
      }
      throw new Error(msg)
    }

    return res.json()
  }

  static async login(username: string, password: string): Promise<{ token: string; username: string }> {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      let msg = 'Login failed'
      try {
        const d = await res.json()
        if (d.detail) msg = d.detail
      } catch {}
      throw new Error(msg)
    }
    const data = await res.json()
    this.setToken(data.token)
    return data
  }

  static async logout(): Promise<void> {
    try {
      await this.request('/api/auth/logout', { method: 'POST' })
    } catch {}
    this.setToken(null)
  }

  static async getMe(): Promise<User> {
    return this.request<User>('/api/auth/me')
  }

  static async listBooks(): Promise<BookSummary[]> {
    return this.request<BookSummary[]>('/api/books')
  }

  static async getBooks(): Promise<BookSummary[]> {
    return this.listBooks()
  }

  static async deleteBook(title: string): Promise<void> {
    await this.request(`/api/books/${encodeURIComponent(title)}`, { method: 'DELETE' })
  }

  static async getBook(title: string): Promise<BookDetail> {
    return this.request<BookDetail>(`/api/books/${encodeURIComponent(title)}`)
  }

  static async getChapter(title: string, slug: string): Promise<{ slug: string; original: string; translated: string }> {
    return this.request(`/api/books/${encodeURIComponent(title)}/chapters/${encodeURIComponent(slug)}`)
  }

  static async saveGlossary(title: string, content: string): Promise<void> {
    await this.request(`/api/books/${encodeURIComponent(title)}/glossary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    })
  }

  static async uploadFile(file: File): Promise<{ filename: string; path: string }> {
    const form = new FormData()
    form.append('file', file)
    return this.request('/api/tools/upload', {
      method: 'POST',
      body: form,
    })
  }

  static async detectGenre(text?: string, filename?: string): Promise<{ genre: string; detected: string }> {
    return this.request('/api/tools/detect-genre', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, filename }),
    })
  }

  static async extractImages(file?: File, path?: string): Promise<{
    book_title: string
    count: number
    duration_seconds: number
    images: Array<{
      index: number
      page_num: number
      filename: string
      path: string
      width: number
      height: number
      url: string
    }>
  }> {
    const form = new FormData()
    if (file) form.append('file', file)
    if (path) form.append('path', path)
    return this.request('/api/tools/extract-images', {
      method: 'POST',
      body: form,
    })
  }

  static async extractMetadata(file?: File, path?: string, refine: boolean = true): Promise<any> {
    const form = new FormData()
    if (file) form.append('file', file)
    if (path) form.append('path', path)
    form.append('refine', refine ? 'true' : 'false')
    return this.request('/api/tools/extract-metadata', {
      method: 'POST',
      body: form,
    })
  }

  static async convertDocument(file?: File, path?: string, keepRaw: boolean = false): Promise<{
    book_title: string
    markdown_path: string
    page_count: number
    confidence: number
    preview: string
  }> {
    const form = new FormData()
    if (file) form.append('file', file)
    if (path) form.append('path', path)
    form.append('keep_raw', keepRaw ? 'true' : 'false')
    return this.request('/api/tools/convert', {
      method: 'POST',
      body: form,
    })
  }

  static async chapterize(file?: File, markdown?: string, bookTitle: string = 'Book'): Promise<{
    book_title: string
    total_chapters: number
    chapter_count?: number
    chapters: Array<{
      slug: string
      title: string
      word_count: number
      preview: string
    }>
  }> {
    const form = new FormData()
    if (file) form.append('file', file)
    if (markdown) form.append('markdown', markdown)
    form.append('book_title', bookTitle)
    const res = await this.request('/api/tools/chapterize', {
      method: 'POST',
      body: form,
    })
    return {
      ...res,
      chapter_count: res.chapter_count || res.total_chapters,
    }
  }

  static async segmentChapters(markdown: string, bookTitle: string = 'Book') {
    return this.chapterize(undefined, markdown, bookTitle)
  }

  static async extractEntities(text: string, genre: string = 'general', model: string = 'urchade/gliner_medium-v2.1', book_folder?: string): Promise<{
    raw_count: number
    clustered: Record<string, Array<{ canonical: string; category: string; confidence: number; aliases: string[] }>>
  }> {
    return this.request('/api/tools/extract-entities', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, genre, model, book_folder }),
    })
  }

  static async buildGraph(chapters: Array<{ slug: string; title: string }> = [], entities: any[] = [], title: string = 'Book', book_folder?: string): Promise<{ graph: string; graph_markdown?: string }> {
    const res = await this.request('/api/tools/build-graph', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chapters, entities, title, book_folder: book_folder || title }),
    })
    return {
      graph: res.graph || '',
      graph_markdown: res.graph || '',
    }
  }

  static async copyedit(text: string, book_folder?: string): Promise<{
    edited_text: string
    normalized?: string
    words_processed: number
    words_modified: number
    changes: Record<string, number>
    summary: string
    duration_seconds: number
  }> {
    return this.request('/api/tools/edit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, book_folder }),
    })
  }

  static async copyeditPersian(text: string) {
    return this.copyedit(text)
  }

  static async translateText(
    text: string,
    target_language: string = 'Persian',
    glossary: string = '',
    style_rules: string = '',
    genre?: string,
    book_folder?: string
  ): Promise<{
    translated: string
    translated_text: string
    metrics: Record<string, any>
    genre?: string
  }> {
    return this.request('/api/tools/translate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, target_language, style_rules, glossary, genre, book_folder }),
    })
  }

  static async compileDocx(book_title: string, eastern_font?: string, western_font?: string): Promise<{
    docx_path: string
    pdf_path?: string
    docx_url: string
    pdf_url?: string
  }> {
    return this.request('/api/tools/compile-docx', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ book_title, eastern_font, western_font }),
    })
  }

  static async runPipeline(params: {
    file_path: string
    genre?: string
    llm_model?: string
    target_language?: string
    translate?: boolean
    skip_gliner?: boolean
    persian_nlp?: boolean
    extract_images?: boolean
    chapters?: string
  }): Promise<{ task_id: string; status: string }> {
    return this.request('/api/pipeline/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
  }

  static async getPrompts(): Promise<Record<string, string>> {
    return this.request('/api/prompts')
  }

  static async updatePrompts(prompts: Record<string, string>): Promise<void> {
    await this.request('/api/prompts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompts }),
    })
  }

  static async getConfig(): Promise<Record<string, any>> {
    return this.request('/api/config')
  }

  static async updateConfig(config: Record<string, any>): Promise<void> {
    await this.request('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    })
  }
}
