import React, { useState, useEffect } from 'react'
import {
  Book,
  FileDown,
  Layers,
  Search,
  ExternalLink,
  RefreshCw,
  Plus,
  FileCode,
  FileArchive,
} from 'lucide-react'
import { Api, BookSummary } from '../api'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

interface BookshelfViewProps {
  onSelectBook: (bookFolder: string) => void
  onNavigateToPipeline?: () => void
}

export const BookshelfView: React.FC<BookshelfViewProps> = ({ onSelectBook, onNavigateToPipeline }) => {
  const [books, setBooks] = useState<BookSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = async () => {
    setRefreshing(true)
    await loadBooks()
    setRefreshKey((k) => k + 1)
    setTimeout(() => setRefreshing(false), 500)
  }

  const loadBooks = async () => {
    setLoading(true)
    try {
      const data = await Api.getBooks()
      setBooks(data)
    } catch (err: any) {
      alert(err.message || 'Failed to load library catalog')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadBooks()
  }, [])

  const handleDelete = async (folder: string, title: string) => {
    if (!window.confirm(`Delete "${title}" permanently?`)) return
    try {
      await Api.deleteBook(folder)
      setBooks((prev) => prev.filter((b) => b.folder !== folder))
    } catch (err: any) {
      alert(err.message || 'Failed to delete book')
    }
  }

  const filtered = books.filter((b) => {
    const q = searchTerm.toLowerCase()
    return (
      b.title.toLowerCase().includes(q) ||
      b.genre?.toLowerCase().includes(q) ||
      b.authors.some((a) => a.toLowerCase().includes(q))
    )
  })

  const totalWords = books.reduce((acc, b) => acc + (b.word_count || 0), 0)
  const totalChapters = books.reduce((acc, b) => acc + b.total_chapters, 0)
  const totalTransChapters = books.reduce((acc, b) => acc + b.translated_chapters, 0)
  const totalCostToman = books.reduce((acc, b) => acc + (b.total_cost_toman || 0), 0)
  const totalTokens = books.reduce((acc, b) => acc + (b.total_tokens || 0), 0)

  const overallPercent =
    totalChapters > 0 ? Math.round((totalTransChapters / totalChapters) * 100) : 0

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-10 gap-4">
        <div className="lg:col-span-3 rounded-3xl bg-card p-6 flex flex-col justify-between soft-shadow border-0">
          <div>
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Total Volume
            </div>
            <div className="text-3xl font-semibold text-foreground tracking-tight mt-1">
              {totalWords.toLocaleString()}
              <span className="text-sm font-normal text-muted-foreground ml-2">words</span>
            </div>
          </div>
          <div className="pt-4 flex items-center justify-between text-xs text-muted-foreground">
            <span>Active Books</span>
            <span className="text-foreground font-semibold">{books.length} volumes</span>
          </div>
        </div>

        <div className="lg:col-span-4 rounded-3xl bg-card p-6 flex flex-col justify-between soft-shadow border-0">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Translation Progress
              </span>
              <Badge variant="success">
                {overallPercent}% Complete
              </Badge>
            </div>
            <div className="h-2 w-full bg-secondary overflow-hidden rounded-full mt-4">
              <div
                className="h-full bg-success transition-all duration-500 rounded-full"
                style={{ width: `${overallPercent}%` }}
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 pt-4 text-xs">
            <div>
              <div className="text-[11px] text-muted-foreground">Chapters</div>
              <div className="text-foreground font-semibold mt-0.5">
                {totalTransChapters}/{totalChapters}
              </div>
            </div>
            <div>
              <div className="text-[11px] text-muted-foreground">Tokens</div>
              <div className="text-foreground font-semibold mt-0.5">
                {totalTokens > 0 ? `${(totalTokens / 1000).toFixed(1)}k` : '0'}
              </div>
            </div>
            <div>
              <div className="text-[11px] text-muted-foreground">Est. Cost</div>
              <div className="text-foreground font-semibold mt-0.5">
                {totalCostToman.toLocaleString()} T
              </div>
            </div>
          </div>
        </div>

        <div className="lg:col-span-3 rounded-3xl bg-card p-6 flex flex-col justify-between space-y-4 soft-shadow border-0">
          <div>
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Actions
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              Manage manuscripts and library
            </div>
          </div>

          <div className="space-y-2">
            <Button
              variant="action"
              size="lg"
              className="w-full justify-center h-11 px-4 text-xs sm:text-sm font-medium gap-2"
              onClick={() => {
                if (onNavigateToPipeline) {
                  onNavigateToPipeline()
                } else {
                  const pipelineTab = document.querySelector('[data-tab="pipeline"]') as HTMLElement
                  if (pipelineTab) pipelineTab.click()
                }
              }}
            >
              <Plus className="h-4 w-4" strokeWidth={2} />
              <span>Ingest Manuscript</span>
            </Button>

            <Button
              variant="secondary"
              size="lg"
              className="w-full justify-center h-11 px-4 text-xs sm:text-sm font-medium gap-2"
              onClick={handleRefresh}
              disabled={loading || refreshing}
            >
              <RefreshCw className={`h-4 w-4 ${(loading || refreshing) ? 'animate-spin' : ''}`} strokeWidth={1.5} />
              <span>Refresh Library</span>
            </Button>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold tracking-tight text-foreground">Manuscripts Catalog</h2>
            <Badge variant="secondary">{filtered.length} items</Badge>
          </div>

          <div className="w-full sm:w-64 md:w-72 lg:w-72 xl:w-72">
            <Input
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search title, genre, author..."
              className="h-11"
            />
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center p-16 text-muted-foreground rounded-3xl bg-card soft-shadow">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent mb-2" />
            <span className="text-xs">Scanning output directory...</span>
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-3xl p-12 text-center bg-card soft-shadow">
            <Book className="mx-auto h-10 w-10 text-muted-foreground/40 mb-3" strokeWidth={1.5} />
            <h3 className="text-base font-semibold text-foreground">No manuscripts found</h3>
            <p className="text-xs text-muted-foreground mt-1">
              Upload a book in Pipeline Studio or place files in output/
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filtered.map((b, idx) => {
              const pct =
                b.total_chapters > 0
                  ? Math.round((b.translated_chapters / b.total_chapters) * 100)
                  : 0

              return (
                <div
                  key={b.folder}
                  className="rounded-3xl bg-card hover:opacity-95 transition-all p-6 flex flex-col justify-between space-y-4 cursor-pointer soft-shadow border-0 group"
                  onClick={() => onSelectBook(b.folder)}
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-1">
                        <h4 className="font-semibold text-base text-foreground line-clamp-1">
                          {b.title}
                        </h4>
                        <div className="text-xs text-muted-foreground line-clamp-1">
                          {b.authors && b.authors.length > 0 ? b.authors.join(', ') : 'Unknown Author'}
                        </div>
                      </div>
                      <Badge variant="outline" className="capitalize shrink-0">
                        {b.genre || 'General'}
                      </Badge>
                    </div>

                    <div className="pt-2">
                      <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
                        <span>Progress</span>
                        <span>{b.translated_chapters}/{b.total_chapters} ch. ({pct}%)</span>
                      </div>
                      <div className="h-1.5 w-full bg-secondary overflow-hidden rounded-full">
                        <div
                          className="h-full bg-foreground transition-all duration-500 rounded-full"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="pt-3 flex items-center justify-between gap-2 text-xs">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {b.has_docx && (
                        <a
                          href={`/api/books/${b.folder}/download/docx`}
                          download
                          onClick={(e) => e.stopPropagation()}
                          className="px-2.5 py-1 rounded-full bg-sky-500/15 text-sky-600 dark:text-sky-400 hover:bg-sky-500/25 transition-colors font-medium text-[11px]"
                          title="Download Docx"
                        >
                          Docx
                        </a>
                      )}
                      {b.has_pdf && (
                        <a
                          href={`/api/books/${b.folder}/download/pdf`}
                          download
                          onClick={(e) => e.stopPropagation()}
                          className="px-2.5 py-1 rounded-full bg-rose-500/15 text-rose-600 dark:text-rose-400 hover:bg-rose-500/25 transition-colors font-medium text-[11px]"
                          title="Download Pdf"
                        >
                          Pdf
                        </a>
                      )}
                      {b.has_original && (
                        <a
                          href={`/api/books/${b.folder}/download/original`}
                          download
                          onClick={(e) => e.stopPropagation()}
                          className="px-2.5 py-1 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 hover:bg-amber-500/25 transition-colors font-medium text-[11px]"
                          title="Download Original Manuscript"
                        >
                          Original
                        </a>
                      )}
                      {b.image_count > 0 && (
                        <a
                          href={`/api/books/${b.folder}/download/images_zip`}
                          download
                          onClick={(e) => e.stopPropagation()}
                          className="px-2.5 py-1 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/25 transition-colors font-medium text-[11px]"
                          title="Download Extracted Images (.zip)"
                        >
                          Images
                        </a>
                      )}
                    </div>

                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDelete(b.folder, b.title)
                      }}
                      className="px-2.5 py-1 rounded-full bg-rose-500/15 text-rose-600 dark:text-rose-400 hover:bg-rose-500/25 transition-colors font-medium text-[11px]"
                    >
                      Delete
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        onSelectBook(b.folder)
                      }}
                      className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground font-medium transition-colors"
                    >
                      <span>Studio</span>
                      <ExternalLink className="h-3.5 w-3.5" strokeWidth={1.5} />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
