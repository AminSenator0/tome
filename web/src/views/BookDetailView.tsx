import React, { useState, useEffect } from 'react'
import {
  ArrowLeft,
  Code,
  BookOpen,
  FileText,
  Users,
  Image as ImageIcon,
  ImageOff,
  BarChart3,
  GitGraph,
  FileDown,
  FolderDown,
  X,
  Archive,
  Layers,
  Download,
  Eye,
  Edit3,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { Api, BookDetail } from '../api'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Textarea, Input } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import { Select } from '../components/ui/Select'
import { Checkbox } from '../components/ui/Checkbox'
import { MermaidGraph } from '../components/ui/MermaidGraph'
import { useI18n } from '../lib/i18n'

interface BookDetailViewProps {
  bookFolder: string
  onBack: () => void
  isDark?: boolean
}

type TabType = 'overview' | 'reader' | 'glossary' | 'graph' | 'images' | 'metrics'

export const BookDetailView: React.FC<BookDetailViewProps> = ({ bookFolder, onBack, isDark = true }) => {
  const { t, tGenre, formatNumber } = useI18n()
  const [book, setBook] = useState<BookDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabType>('overview')

  const [selectedChapterSlug, setSelectedChapterSlug] = useState<string>('')
  const [chapterContent, setChapterContent] = useState<{ original: string; translated: string } | null>(null)
  const [loadingChapter, setLoadingChapter] = useState(false)

  const [glossaryDraft, setGlossaryDraft] = useState('')
  const [glossaryMode, setGlossaryMode] = useState<'preview' | 'editor' | 'edit'>('preview')
  const [glossaryRows, setGlossaryRows] = useState<Array<{ canonical: string; aliases: string; translation: string; confidence: string }>>([])
  const [glossarySearch, setGlossarySearch] = useState('')
  const [savingGlossary, setSavingGlossary] = useState(false)
  const [glossarySaved, setGlossarySaved] = useState(false)

  const [graphMode, setGraphMode] = useState<'preview' | 'edit'>('preview')

  const [compiling, setCompiling] = useState(false)
  const [compileMsg, setCompileMsg] = useState<string | null>(null)

  const [checkedChapters, setCheckedChapters] = useState<Set<string>>(new Set())
  const [translatingChapters, setTranslatingChapters] = useState(false)
  const [quality, setQuality] = useState<Record<string, { score: number; reason: string }>>({})

  useEffect(() => {
    Api.getBookQuality(bookFolder)
      .then(setQuality)
      .catch(() => {})
  }, [bookFolder])
  const [transStatusMsg, setTransStatusMsg] = useState<string | null>(null)

  const [imageErrors, setImageErrors] = useState<Record<number, boolean>>({})
  const [activeLightboxImg, setActiveLightboxImg] = useState<{ url: string; page_num: number } | null>(null)

  // Unified Export Hub State
  const [showExportHub, setShowExportHub] = useState(false)
  const [exportWatermark, setExportWatermark] = useState('')
  const [exportFontSize, setExportFontSize] = useState('12pt')

  const isPersian = (text: any): boolean => {
    if (typeof text !== 'string') {
      if (Array.isArray(text)) return text.some(isPersian)
      if (text && typeof text === 'object' && text.props && text.props.children) {
        return isPersian(text.props.children)
      }
      return false
    }
    return /[\u0600-\u06FF]/.test(text)
  }

  const toggleChapterCheck = (slug: string) => {
    setCheckedChapters((prev) => {
      const next = new Set(prev)
      if (next.has(slug)) next.delete(slug)
      else next.add(slug)
      return next
    })
  }

  const toggleAllChapters = () => {
    if (!book) return
    if (checkedChapters.size === book.chapters.length) {
      setCheckedChapters(new Set())
    } else {
      setCheckedChapters(new Set(book.chapters.map((c) => c.slug)))
    }
  }

  const runChapterTranslation = async (slugs: string[]) => {
    if (slugs.length === 0 || !book) return
    setTranslatingChapters(true)
    setTransStatusMsg(t('book.transInit', { n: slugs.length }))
    try {
      const res = await Api.runPipeline({
        file_path: `output/${bookFolder}/original/book.md`,
        translate: true,
        chapters: slugs.join(','),
      })
      setTransStatusMsg(t('book.transLaunched'))
      const ev = new EventSource(`/api/pipeline/events/${res.task_id}`)
      ev.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data)
          if (d.event === 'chapter_translation_complete') {
            const ch = d.data?.chapter || d.data?.slug || ''
            setTransStatusMsg(t('book.translatedMsg', { ch }))
          } else if (d.event === 'pipeline_complete' || d.status === 'completed' || d.data?.status === 'completed') {
            ev.close()
            setTranslatingChapters(false)
            setTransStatusMsg(t('book.transDone'))
            loadBook()
            Api.getBookQuality(bookFolder).then(setQuality).catch(() => {})
            setTimeout(() => setTransStatusMsg(null), 4000)
          } else if (d.event === 'pipeline_cancelled') {
            ev.close()
            setTranslatingChapters(false)
            setTransStatusMsg(t('book.transCancelled'))
            loadBook()
          } else if (d.event === 'error' || d.status === 'failed') {
            ev.close()
            setTranslatingChapters(false)
            setTransStatusMsg(t('book.transError', { msg: d.data?.error || d.error || 'Failed' }))
            loadBook()
          }
        } catch {}
      }
      ev.onerror = () => {
        ev.close()
        setTranslatingChapters(false)
        loadBook()
      }
    } catch (err: any) {
      setTranslatingChapters(false)
      setTransStatusMsg(t('book.errorPrefix', { msg: err.message }))
    }
  }

  const handleTranslateSelected = () => {
    runChapterTranslation(Array.from(checkedChapters))
  }

  const handleTranslateRemaining = () => {
    if (!book) return
    const pending = book.chapters.filter((c) => !c.is_translated).map((c) => c.slug)
    runChapterTranslation(pending)
  }

  const handleRetryChapter = (slug: string) => {
    runChapterTranslation([slug])
  }

  const loadBook = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await Api.getBook(bookFolder)
      setBook(data)
      setGlossaryDraft(data.glossary || '')
      if (data.chapters && data.chapters.length > 0 && !selectedChapterSlug) {
        setSelectedChapterSlug(data.chapters[0].slug)
      }
    } catch (err: any) {
      setError(err.message || t('book.loadFail'))
    } finally {
      setLoading(false)
    }
  }

  const loadChapter = async (slug: string) => {
    setSelectedChapterSlug(slug)
    setLoadingChapter(true)
    try {
      const data = await Api.getChapter(bookFolder, slug)
      setChapterContent(data)
    } catch (err: any) {
      alert(err.message || t('book.loadChapterFail'))
    } finally {
      setLoadingChapter(false)
    }
  }

  useEffect(() => {
    loadBook()
  }, [bookFolder])

  useEffect(() => {
    if (selectedChapterSlug && activeTab === 'reader') {
      loadChapter(selectedChapterSlug)
    }
  }, [selectedChapterSlug, activeTab])

  const parseGlossaryRows = (text: string) => {
    const rows: Array<{ canonical: string; aliases: string; translation: string; confidence: string }> = []
    for (const line of text.split('\n')) {
      if (!line.startsWith('|') || /^[|\s:-]+$/.test(line)) continue
      const cols = line.split('|').slice(1, -1).map((c) => c.trim())
      if (cols.length < 3 || !cols[0] || /canonical/i.test(cols[0])) continue
      rows.push({ canonical: cols[0], aliases: cols[1] || '', translation: cols[2] || '', confidence: cols[3] || '' })
    }
    return rows
  }

  const serializeGlossaryRows = (rows: Array<{ canonical: string; aliases: string; translation: string; confidence: string }>) => {
    const lines = glossaryDraft.split('\n')
    const headerIdx = lines.findIndex((l) => l.startsWith('|') && /canonical/i.test(l))
    const header = headerIdx >= 0 ? lines[headerIdx] : '| Canonical Term | Aliases | Term Translation | Confidence |'
    const sep = headerIdx >= 0 && (lines[headerIdx + 1] || '').startsWith('|') ? lines[headerIdx + 1] : '| --- | --- | --- | --- |'
    const prefix = headerIdx >= 0 ? lines.slice(0, headerIdx) : []
    const body = rows
      .filter((r) => r.canonical.trim())
      .map((r) => `| ${r.canonical.trim()} | ${r.aliases} | ${r.translation} | ${r.confidence} |`)
    return [...prefix, header, sep, ...body].join('\n')
  }

  const mergeDuplicateRows = () => {
    const seen = new Map<string, { canonical: string; aliases: string; translation: string; confidence: string }>()
    for (const r of glossaryRows) {
      const key = r.canonical.trim().toLowerCase()
      if (!key) continue
      const existing = seen.get(key)
      if (!existing) {
        seen.set(key, { ...r })
        continue
      }
      const aliasSet = new Set([...existing.aliases.split(','), ...r.aliases.split(',')].map((a) => a.trim()).filter(Boolean))
      seen.set(key, {
        canonical: existing.canonical,
        aliases: Array.from(aliasSet).join(', '),
        translation: existing.translation || r.translation,
        confidence: existing.confidence || r.confidence,
      })
    }
    setGlossaryRows(Array.from(seen.values()))
  }

  const handleEditorSave = async () => {
    const md = serializeGlossaryRows(glossaryRows)
    setGlossaryDraft(md)
    setSavingGlossary(true)
    try {
      await Api.saveGlossary(bookFolder, md)
      setGlossarySaved(true)
      setTimeout(() => setGlossarySaved(false), 2000)
    } catch (err: any) {
      alert(err.message || t('book.saveGlossaryFail'))
    } finally {
      setSavingGlossary(false)
    }
  }

  const handleSaveGlossary = async () => {
    setSavingGlossary(true)
    try {
      await Api.saveGlossary(bookFolder, glossaryDraft)
      setGlossarySaved(true)
      setTimeout(() => setGlossarySaved(false), 2000)
    } catch (err: any) {
      alert(err.message || t('book.saveGlossaryFail'))
    } finally {
      setSavingGlossary(false)
    }
  }

  const handleCompile = async () => {
    setCompiling(true)
    setCompileMsg(null)
    try {
      await Api.compileDocx(bookFolder)
      setCompileMsg(`Compiled volume successfully!`)
      loadBook()
    } catch (err: any) {
      alert(err.message || t('book.compileFail'))
    } finally {
      setCompiling(false)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-16 text-muted-foreground">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent mb-2" />
        <span className="text-xs">{t('book.loading')}</span>
      </div>
    )
  }

  if (error || !book) {
    return (
      <div className="p-8 text-center space-y-4">
        <div className="text-destructive font-medium text-sm">{error || t('book.notFound')}</div>
        <Button onClick={onBack} size="sm">
{t('book.returnToLibrary')}
        </Button>
      </div>
    )
  }

  const meta = book.metadata || {}
  const metrics = book.metrics || {}

  const navTabs: { id: TabType; label: string; icon: React.ReactNode }[] = [
    { id: 'overview', label: t('book.tabOverview'), icon: <BookOpen className="h-4 w-4" /> },
    { id: 'reader', label: t('book.tabReader'), icon: <FileText className="h-4 w-4" /> },
    { id: 'glossary', label: t('book.tabGlossary'), icon: <Users className="h-4 w-4" /> },
    { id: 'graph', label: t('book.tabGraph'), icon: <GitGraph className="h-4 w-4" /> },
    { id: 'images', label: t('book.tabImages', { n: book.images.length }), icon: <ImageIcon className="h-4 w-4" /> },
    { id: 'metrics', label: t('book.tabMetrics'), icon: <BarChart3 className="h-4 w-4" /> },
  ]

  const isAllChecked = book.chapters.length > 0 && checkedChapters.size === book.chapters.length

  return (
    <div className="space-y-3.5 relative pb-12">
      {/* Top Header & Action Controls with reduced bottom spacing */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pb-0.5">
        <div className="flex items-center gap-3">
          <Button variant="secondary" size="icon" onClick={onBack} title={t('book.backToLibrary')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold tracking-tight text-foreground">
                {meta.title || book.folder.replace(/_/g, ' ')}
              </h1>
              <Badge variant="outline" className="capitalize">
                {tGenre(meta.genre)}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              {meta.authors && meta.authors.length > 0 ? meta.authors.join(', ') : t('book.unknownAuthor')}
              {meta.year ? ` • ${meta.year}` : ''}
              {meta.reading_time ? t('book.estReading', { time: meta.reading_time }) : ''}
            </p>
          </div>
        </div>

        {/* Mobile: 50/50 Export Hub and Compile Volume */}
        <div className="flex sm:hidden w-full items-center gap-2.5 pt-1">
          <Button
            variant="action"
            onClick={() => setShowExportHub(true)}
            className="flex-1 h-10 text-xs font-medium gap-1.5 rounded-full justify-center"
            title={t('book.exportHubTitle')}
          >
            <FolderDown className="h-3.5 w-3.5" />
            <span>{t('book.exportHub')}</span>
          </Button>
          <Button
            variant="secondary"
            onClick={handleCompile}
            loading={compiling}
            className="flex-1 h-10 text-xs font-medium gap-1.5 rounded-full justify-center"
            title={t('book.compileTitle')}
          >
            <Layers className="h-3.5 w-3.5" strokeWidth={1.5} />
            <span>{t('book.compileVolume')}</span>
          </Button>
        </div>

        {/* Desktop: Full toolbar */}
        <div className="hidden sm:flex items-center gap-2">
          <Button
            variant="action"
            onClick={() => setShowExportHub(true)}
            className="h-10 px-4 text-xs font-medium gap-1.5 rounded-full shrink-0"
            title={t('book.exportHubTitle')}
          >
            <FolderDown className="h-3.5 w-3.5" />
            <span>{t('book.exportHub')}</span>
          </Button>

          {book.has_docx && (
            <a
              href={`/api/books/${bookFolder}/download/docx`}
              download
              className="inline-flex items-center gap-1.5 h-10 px-4 rounded-full bg-sky-500/15 text-sky-600 dark:text-sky-400 hover:bg-sky-500/25 transition-colors font-medium text-xs shrink-0"
              title={t('book.downloadDocxTitle')}
            >
              <FileDown className="h-3.5 w-3.5" strokeWidth={1.5} />
              <span>Docx</span>
            </a>
          )}
          {book.has_pdf && (
            <a
              href={`/api/books/${bookFolder}/download/pdf`}
              download
              className="inline-flex items-center gap-1.5 h-10 px-4 rounded-full bg-rose-500/15 text-rose-600 dark:text-rose-400 hover:bg-rose-500/25 transition-colors font-medium text-xs shrink-0"
              title={t('book.downloadPdfTitle')}
            >
              <FileDown className="h-3.5 w-3.5" strokeWidth={1.5} />
              <span>Pdf</span>
            </a>
          )}
          {book.has_original && (
            <a
              href={`/api/books/${bookFolder}/download/original`}
              download
              className="inline-flex items-center gap-1.5 h-10 px-4 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 hover:bg-amber-500/25 transition-colors font-medium text-xs shrink-0"
              title={t('book.downloadOriginalTitle')}
            >
              <FileDown className="h-3.5 w-3.5" strokeWidth={1.5} />
              <span>{t('book.original')}</span>
            </a>
          )}

          <Button
            variant="secondary"
            onClick={handleCompile}
            loading={compiling}
            className="h-10 px-4 text-xs font-medium gap-1.5 rounded-full shrink-0"
            title={t('book.compileTitle')}
          >
            <Layers className="h-3.5 w-3.5" strokeWidth={1.5} />
            <span>{t('book.compileVolume')}</span>
          </Button>
        </div>
      </div>

      {compileMsg && (
        <div className="p-3 rounded-2xl bg-success-light text-success text-xs flex items-center justify-between">
          <span>{compileMsg}</span>
          <button type="button" onClick={() => setCompileMsg(null)} className="cursor-pointer border-0 bg-transparent">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Navigation Tabs with hidden scrollbar on mobile */}
      <div className="flex items-center gap-1 overflow-x-auto p-1 rounded-full bg-secondary/50 w-fit max-w-full [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
        {navTabs.map((tab) => {
          const active = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium transition-all whitespace-nowrap border-0 cursor-pointer ${
                active
                  ? 'bg-foreground text-background shadow-xs'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
          )
        })}
      </div>

      {/* Unified Export Hub Modal */}
      {showExportHub && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-background/80 backdrop-blur-md">
          <div className="max-w-md w-full rounded-3xl bg-card p-6 space-y-5 border-0 shadow-2xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <FolderDown className="h-5 w-5 text-primary" />
                <h3 className="text-base font-semibold text-foreground">{t('book.exportHubModal')}</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowExportHub(false)}
                className="h-8 w-8 rounded-full flex items-center justify-center bg-secondary hover:bg-accent text-muted-foreground hover:text-foreground cursor-pointer border-0"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="text-xs text-muted-foreground">
              {t('book.exportHubDesc')}
            </p>

            <div className="space-y-3">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block">
{t('book.availableArtifacts')}
              </span>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {book.has_docx && (
                  <a
                    href={`/api/books/${bookFolder}/download/docx`}
                    download
                    className="flex items-center justify-between p-3 rounded-2xl bg-sky-500/15 text-sky-600 dark:text-sky-400 font-medium"
                  >
                    <span>{t('book.artDocx')}</span>
                    <FileDown className="h-4 w-4" />
                  </a>
                )}
                {book.has_pdf && (
                  <a
                    href={`/api/books/${bookFolder}/download/pdf`}
                    download
                    className="flex items-center justify-between p-3 rounded-2xl bg-rose-500/15 text-rose-600 dark:text-rose-400 font-medium"
                  >
                    <span>{t('book.artPdf')}</span>
                    <FileDown className="h-4 w-4" />
                  </a>
                )}
                {book.has_original && (
                  <a
                    href={`/api/books/${bookFolder}/download/original`}
                    download
                    className="flex items-center justify-between p-3 rounded-2xl bg-amber-500/15 text-amber-600 dark:text-amber-400 font-medium"
                  >
                    <span>{t('book.artOriginal')}</span>
                    <FileDown className="h-4 w-4" />
                  </a>
                )}
                {book.images.length > 0 && (
                  <a
                    href={`/api/books/${bookFolder}/download/images_zip`}
                    download
                    className="flex items-center justify-between p-3 rounded-2xl bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-medium"
                  >
                    <span>{t('book.artImages')}</span>
                    <FileDown className="h-4 w-4" />
                  </a>
                )}
              </div>
            </div>

            <div className="pt-3 border-t border-muted/30 space-y-3">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block">
{t('book.exportOptions')}
              </span>
              <Input
                label={t('book.watermark')}
                placeholder={t('book.watermarkPh')}
                value={exportWatermark}
                onChange={(e) => setExportWatermark(e.target.value)}
              />
              <Select
                label={t('book.fontSize')}
                value={exportFontSize}
                onChange={(e) => setExportFontSize(e.target.value)}
              >
                <option value="11pt">{t('book.fsCompact')}</option>
                <option value="12pt">{t('book.fsStandard')}</option>
                <option value="13pt">{t('book.fsLarge')}</option>
              </Select>
            </div>

            <div className="pt-2">
              <a
                href={`/api/books/${bookFolder}/download/unified_zip`}
                download
                className="w-full flex items-center justify-center gap-2 h-11 px-5 rounded-full bg-primary text-primary-foreground text-xs font-medium transition-opacity hover:opacity-90"
              >
                <Archive className="h-4 w-4" />
                <span>{t('book.downloadAll')}</span>
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Lightbox Modal for Individual Image Preview & Single Download */}
      {activeLightboxImg && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-background/80 backdrop-blur-md">
          <div className="max-w-2xl w-full rounded-3xl bg-card p-6 space-y-4 border-0 shadow-2xl flex flex-col items-center">
            <div className="w-full flex items-center justify-between">
              <span className="text-sm font-semibold text-foreground">
                Illustration — Page {activeLightboxImg.page_num}
              </span>
              <button
                type="button"
                onClick={() => setActiveLightboxImg(null)}
                className="h-8 w-8 rounded-full flex items-center justify-center bg-secondary hover:bg-accent text-muted-foreground hover:text-foreground cursor-pointer border-0"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="w-full max-h-[65vh] overflow-hidden rounded-2xl bg-secondary/30 flex items-center justify-center p-2">
              <img
                src={activeLightboxImg.url}
                alt={t('book.page', { n: activeLightboxImg.page_num })}
                className="max-h-[60vh] max-w-full object-contain rounded-lg shadow-sm"
              />
            </div>

            <div className="w-full flex items-center justify-end gap-3 pt-2">
              <a
                href={activeLightboxImg.url}
                download={`illustration_p${activeLightboxImg.page_num}`}
                className="inline-flex items-center gap-2 h-10 px-5 rounded-full bg-primary text-primary-foreground text-xs font-medium hover:opacity-90 transition-opacity"
              >
                <Download className="h-4 w-4" />
                <span>{t('book.downloadImage')}</span>
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Overview */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Top Row: Synopsis and Volume Metadata */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <Card className="h-full">
                <CardHeader>
                  <CardTitle>{t('book.synopsisTitle')}</CardTitle>
                  <CardDescription>{t('book.synopsisDesc')}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 text-xs">
                  <p className="leading-relaxed text-foreground/90">
                    {meta.synopsis || t('book.noSynopsis')}
                  </p>
                  {meta.keywords && meta.keywords.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-2">
                      {meta.keywords.map((kw: string, i: number) => (
                        <Badge key={i} variant="secondary">
                          {kw}
                        </Badge>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            <div className="lg:col-span-1">
              <Card className="h-full">
                <CardHeader>
                  <CardTitle>{t('book.volumeMetadata')}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-xs">
                  <div>
                    <span className="text-muted-foreground block text-[11px]">{t('book.metaTitle')}</span>
                    <span className="font-medium text-foreground">{meta.title || t('common.na')}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block text-[11px]">{t('book.metaAuthors')}</span>
                    <span className="font-medium text-foreground">{meta.authors?.join(', ') || t('common.na')}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block text-[11px]">{t('book.metaGenre')}</span>
                    <span className="font-medium text-foreground capitalize">{tGenre(meta.genre)}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block text-[11px]">{t('book.metaYear')}</span>
                    <span className="font-medium text-foreground">{meta.year || t('common.na')}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block text-[11px]">{t('book.metaReading')}</span>
                    <span className="font-medium text-foreground">{meta.reading_time || t('common.na')}</span>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Bottom Row: Chapter Index */}
          <Card>
            <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
              <div className="text-left">
                <CardTitle>{t('book.chapterIndex', { n: book.chapters.length })}</CardTitle>
                <CardDescription>{t('book.chapterIndexDesc')}</CardDescription>
              </div>
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 w-full sm:w-auto">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={toggleAllChapters}
                  className="h-9 text-xs font-medium px-4 rounded-full w-full sm:w-auto justify-center whitespace-nowrap"
                >
                  <span>{isAllChecked ? t('book.deselectAll') : t('book.selectAll')}</span>
                </Button>
                <Button
                  size="sm"
                  variant="primary"
                  disabled={checkedChapters.size === 0 || translatingChapters}
                  onClick={handleTranslateSelected}
                  loading={translatingChapters}
                  className="h-9 text-xs font-medium px-4 rounded-full w-full sm:w-auto justify-center whitespace-nowrap"
                >
                  <span>{t('book.translateSelected', { n: checkedChapters.size })}</span>
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={translatingChapters || book.chapters.filter((c) => !c.is_translated).length === 0}
                  onClick={handleTranslateRemaining}
                  loading={translatingChapters}
                  className="h-9 text-xs font-medium px-4 rounded-full w-full sm:w-auto justify-center whitespace-nowrap"
                >
                  <span>{t('book.translateRemaining', { n: book.chapters.filter((c) => !c.is_translated).length })}</span>
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-secondary/40">
                {book.chapters.map((ch, idx) => {
                  const isChecked = checkedChapters.has(ch.slug)
                  return (
                    <div
                      key={ch.slug}
                      className="flex items-center justify-between p-4 hover:bg-secondary/30 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <Checkbox
                          checked={isChecked}
                          onChange={() => toggleChapterCheck(ch.slug)}
                        />
                        <div>
                          <span className="font-medium text-xs text-foreground">
                            {idx + 1}. {ch.slug}
                          </span>
                          <span className="text-[11px] text-muted-foreground block">
                            {t('book.words', { n: formatNumber(ch.word_count) })}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <div
                          className={`h-8 px-3 rounded-full flex items-center justify-center text-xs font-medium ${
                            ch.is_translated
                              ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                              : 'bg-secondary text-muted-foreground'
                          }`}
                        >
                          {ch.is_translated ? t('book.translated') : t('book.pending')}
                        </div>
                        {ch.is_translated && (quality[ch.slug] || quality[`${ch.slug}.md`]) && (
                          (() => {
                            const q = quality[ch.slug] || quality[`${ch.slug}.md`]
                            return (
                              <span
                                title={q.reason || `Quality: ${q.score}/10`}
                                className={`h-8 px-2.5 rounded-full flex items-center justify-center text-[11px] font-semibold ${
                                  q.score >= 8
                                    ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                                    : q.score >= 6
                                      ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
                                      : 'bg-rose-500/15 text-rose-600 dark:text-rose-400'
                                }`}
                              >
                                {q.score}/10
                              </span>
                            )
                          })()
                        )}
                        {!ch.is_translated && (
                          <Button
                            size="sm"
                            variant="primary"
                            disabled={translatingChapters}
                            onClick={() => handleRetryChapter(ch.slug)}
                            className="h-8 text-xs px-3.5 rounded-full"
                          >
{t('common.retry')}
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => {
                            setSelectedChapterSlug(ch.slug)
                            setActiveTab('reader')
                          }}
                          className="h-8 text-xs px-3.5 rounded-full"
                        >
{t('book.read')}
                        </Button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tab: Reader with Markdown & HTML rendering */}
      {activeTab === 'reader' && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-1 rounded-3xl bg-card p-3 max-h-[700px] overflow-hidden border-0 flex flex-col">
            <div className="text-[11px] font-semibold text-muted-foreground uppercase px-3 py-2 tracking-wider">
              Select Chapter
            </div>
            <div className="space-y-1.5 overflow-y-auto pr-1.5 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden flex-1">
              {book.chapters.map((ch, idx) => {
                const active = selectedChapterSlug === ch.slug
                return (
                  <button
                    key={ch.slug}
                    onClick={() => loadChapter(ch.slug)}
                    className={`w-full flex items-center justify-between p-3 rounded-2xl text-xs transition-all text-left border-0 cursor-pointer ${
                      active
                        ? 'bg-foreground text-background font-medium'
                        : 'text-foreground hover:bg-secondary'
                    }`}
                  >
                    <span className="truncate">
                      {idx + 1}. {ch.slug}
                    </span>
                    {!active && ch.is_translated && (
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
{t('book.done')}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="lg:col-span-3 space-y-4">
            {loadingChapter ? (
              <div className="flex items-center justify-center p-16 text-muted-foreground text-xs">
                {t('book.loadingChapter')}
              </div>
            ) : chapterContent ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm">{t('book.original')}</CardTitle>
                    <CardDescription>{t('book.sourceSuffix', { slug: selectedChapterSlug })}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="text-xs sm:text-sm font-sans leading-relaxed max-h-[600px] overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden pr-4 text-foreground/90 select-text prose dark:prose-invert max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                        {chapterContent.original || t('book.noSource')}
                      </ReactMarkdown>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm">{t('book.translation')}</CardTitle>
                    <CardDescription>{t('book.outputSuffix', { slug: selectedChapterSlug })}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div
                      dir="rtl"
                      className="text-sm font-persian leading-relaxed max-h-[600px] overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden pr-4 text-foreground select-text prose dark:prose-invert max-w-none"
                    >
                      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                        {chapterContent.translated || t('book.notTranslatedYet')}
                      </ReactMarkdown>
                    </div>
                  </CardContent>
                </Card>
              </div>
            ) : (
              <div className="p-12 text-center text-xs text-muted-foreground bg-card rounded-3xl">
                {t('book.selectChapterHint')}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab: Glossary with Preview / Raw Data */}
      {activeTab === 'glossary' && (
        <Card>
          <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1">
            <div className="text-left space-y-0.5">
              <CardTitle>{t('book.glossaryTitle')}</CardTitle>
              <CardDescription>
                {t('book.glossaryDesc')}
              </CardDescription>
            </div>

            <div className="w-full sm:w-auto grid grid-cols-3 sm:flex items-center p-1 rounded-full bg-secondary text-xs font-medium shrink-0">
              <button
                type="button"
                onClick={() => { setGlossaryMode('preview') }}
                className={`flex items-center justify-center gap-1.5 h-8 px-4 rounded-full transition-all duration-200 border-0 cursor-pointer ${
                  glossaryMode === 'preview'
                    ? 'bg-foreground text-background shadow-xs font-medium'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Eye className="h-3.5 w-3.5" />
                <span>{t('common.preview')}</span>
              </button>
              <button
                type="button"
                onClick={() => { setGlossaryMode('editor'); setGlossaryRows(parseGlossaryRows(glossaryDraft)) }}
                className={`flex items-center justify-center gap-1.5 h-8 px-4 rounded-full transition-all duration-200 border-0 cursor-pointer ${
                  glossaryMode === 'editor'
                    ? 'bg-foreground text-background shadow-xs font-medium'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Edit3 className="h-3.5 w-3.5" />
                <span>{t('common.editor')}</span>
              </button>
              <button
                type="button"
                onClick={() => setGlossaryMode('edit')}
                className={`flex items-center justify-center gap-1.5 h-8 px-4 rounded-full transition-all duration-200 border-0 cursor-pointer ${
                  glossaryMode === 'edit'
                    ? 'bg-foreground text-background shadow-xs font-medium'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Code className="h-3.5 w-3.5" />
                <span>{t('common.rawData')}</span>
              </button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {glossaryMode === 'preview' ? (
              <div className="rounded-3xl bg-secondary/30 p-4 sm:p-6 overflow-x-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
                {glossaryDraft.trim() ? (
                  <div className="prose prose-sm dark:prose-invert max-w-none text-xs">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeRaw]}
                      components={{
                        h1: ({ node, ...props }) => <h3 className="text-base font-semibold text-foreground mt-6 mb-2" {...props} />,
                        h2: ({ node, ...props }) => <h4 className="text-sm font-semibold text-foreground mt-6 mb-2" {...props} />,
                        h3: ({ node, ...props }) => <h5 className="text-xs font-semibold text-foreground mt-5 mb-1.5 uppercase tracking-wider" {...props} />,
                        p: ({ node, ...props }) => <p className="text-xs text-muted-foreground my-2" {...props} />,
                        table: ({ node, ...props }) => (
                          <div className="my-4 overflow-x-auto rounded-2xl bg-secondary/20 border border-secondary/40">
                            <table className="w-full text-xs border-collapse" {...props} />
                          </div>
                        ),
                        thead: ({ node, ...props }) => (
                          <thead className="bg-secondary text-foreground font-semibold" {...props} />
                        ),
                        th: ({ node, ...props }) => (
                          <th className="p-3 text-left border-b border-muted/30 whitespace-nowrap" {...props} />
                        ),
                        td: ({ node, children, ...props }) => {
                          const persian = isPersian(children)
                          return (
                            <td
                              dir={persian ? 'rtl' : 'ltr'}
                              className={`p-3 border-b border-secondary/30 align-top ${
                                persian ? 'font-persian text-right text-foreground' : 'font-sans text-left text-foreground/90'
                              }`}
                              {...props}
                            >
                              {children}
                            </td>
                          )
                        },
                      }}
                    >
                      {glossaryDraft}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="p-8 text-center text-xs text-muted-foreground">
                    No glossary definitions generated yet. Click Edit Raw to create terms.
                  </div>
                )}
              </div>
            ) : glossaryMode === 'editor' ? (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Input
                    placeholder={t('book.searchTerms')}
                    value={glossarySearch}
                    onChange={(e) => setGlossarySearch(e.target.value)}
                    className="h-9 w-64 text-xs"
                  />
                  <Button size="sm" variant="secondary" onClick={() => setGlossaryRows((prev) => [...prev, { canonical: '', aliases: '', translation: '', confidence: '' }])}>
{t('book.addRow')}
                  </Button>
                  <Button size="sm" variant="secondary" onClick={mergeDuplicateRows}>
{t('book.mergeDuplicates')}
                  </Button>
                  <span className="text-[11px] text-muted-foreground ms-auto tabular-nums">{t('common.rows', { n: glossaryRows.length })}</span>
                </div>
                <div className="rounded-2xl overflow-hidden bg-secondary/30 max-h-[520px] overflow-y-auto custom-scrollbar">
                  <table className="w-full text-xs">
                    <thead className="bg-secondary sticky top-0">
                      <tr className="text-left text-muted-foreground">
                        <th className="p-2.5 font-medium">{t('book.colCanonical')}</th>
                        <th className="p-2.5 font-medium">{t('book.colAliases')}</th>
                        <th className="p-2.5 font-medium">{t('book.colTranslation')}</th>
                        <th className="p-2.5 font-medium w-24">{t('book.colConfidence')}</th>
                        <th className="p-2.5 w-10" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-secondary/40">
                      {glossaryRows.map((r, i) => {
                        if (glossarySearch && !`${r.canonical} ${r.aliases} ${r.translation}`.toLowerCase().includes(glossarySearch.toLowerCase())) return null
                        return (
                          <tr key={i} className="hover:bg-secondary/40">
                            {(['canonical', 'aliases', 'translation', 'confidence'] as const).map((field) => (
                              <td key={field} className="p-1.5">
                                <input
                                  value={r[field]}
                                  onChange={(e) => {
                                    const val = e.target.value
                                    setGlossaryRows((prev) => prev.map((row, j) => (j === i ? { ...row, [field]: val } : row)))
                                  }}
                                  className="w-full h-8 px-2 rounded-lg bg-background/60 border-0 text-xs outline-none focus:ring-1 ring-primary/40"
                                />
                              </td>
                            ))}
                            <td className="p-1.5 text-center">
                              <button
                                type="button"
                                onClick={() => setGlossaryRows((prev) => prev.filter((_, j) => j !== i))}
                                className="h-7 w-7 rounded-full bg-destructive/10 text-destructive hover:bg-destructive/20 border-0 cursor-pointer inline-flex items-center justify-center"
                                title={t('book.deleteRow')}
                              >
                                <X className="h-3.5 w-3.5" />
                              </button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="flex items-center gap-2">
                  <Button size="sm" onClick={handleEditorSave} loading={savingGlossary}>
                    {glossarySaved ? t('common.saved') : t('book.saveGlossary')}
                  </Button>
                  <span className="text-[11px] text-muted-foreground">{t('book.glossaryNote')}</span>
                </div>
              </div>
            ) : (
              <div className="rounded-3xl bg-secondary/30 p-4 overflow-hidden space-y-3">
                <Textarea
                  value={glossaryDraft}
                  onChange={(e) => setGlossaryDraft(e.target.value)}
                  className="font-mono text-xs min-h-[400px] bg-background/60"
                />
                <div className="flex items-center gap-2">
                  <Button size="sm" onClick={handleSaveGlossary} loading={savingGlossary}>
                    {glossarySaved ? t('common.saved') : t('book.saveRawGlossary')}
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tab: Character Graph with responsive compact mode switch */}
      {activeTab === 'graph' && (
        <Card>
          <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
            <div className="text-left space-y-0.5">
              <CardTitle>{t('book.graphTitle')}</CardTitle>
              <CardDescription>
                {t('book.graphDesc')}
              </CardDescription>
            </div>
            {book.graph_markdown && (
              <div className="w-full sm:w-auto grid grid-cols-2 sm:flex items-center p-1 rounded-full bg-secondary text-xs font-medium shrink-0">
                <button
                  type="button"
                  onClick={() => setGraphMode('preview')}
                  className={`flex items-center justify-center gap-1.5 h-8 px-4 rounded-full transition-all duration-200 border-0 cursor-pointer ${
                    graphMode === 'preview'
                      ? 'bg-foreground text-background shadow-xs font-medium'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Eye className="h-3.5 w-3.5" />
                  <span>{t('common.preview')}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setGraphMode('edit')}
                  className={`flex items-center justify-center gap-1.5 h-8 px-4 rounded-full transition-all duration-200 border-0 cursor-pointer ${
                    graphMode === 'edit'
                      ? 'bg-foreground text-background shadow-xs font-medium'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Code className="h-3.5 w-3.5" />
                  <span>{t('common.rawData')}</span>
                </button>
              </div>
            )}
          </CardHeader>
          <CardContent className="space-y-6">
            {book.graph_markdown ? (
              graphMode === 'preview' ? (
                <MermaidGraph content={book.graph_markdown} isDark={isDark} />
              ) : (
                <div className="rounded-3xl bg-secondary/40 p-5 overflow-hidden">
                  <pre className="font-mono text-xs max-h-[450px] overflow-y-auto custom-scrollbar select-text text-foreground">
                    {book.graph_markdown}
                  </pre>
                </div>
              )
            ) : (
              <div className="p-12 text-center text-xs text-muted-foreground bg-secondary/20 rounded-3xl">
                No character relationship graph generated for this volume.
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tab: Images with Lazy Loading, Lightbox and Full-Width Mobile ZIP Button */}
      {activeTab === 'images' && (
        <Card>
          <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
            <div className="text-left">
              <CardTitle>{t('book.imagesTitle', { n: book.images.length })}</CardTitle>
              <CardDescription>{t('book.imagesDesc')}</CardDescription>
            </div>
            {book.images.length > 0 && (
              <a
                href={`/api/books/${bookFolder}/download/images_zip`}
                download
                className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 h-10 px-5 rounded-full bg-primary text-primary-foreground text-xs font-medium transition-opacity hover:opacity-90 whitespace-nowrap"
              >
                <FileDown className="h-3.5 w-3.5" />
                <span>{t('book.downloadZip')}</span>
              </a>
            )}
          </CardHeader>
          <CardContent>
            {book.images.length === 0 ? (
              <div className="p-12 text-center text-xs text-muted-foreground bg-secondary/20 rounded-3xl">
                No embedded illustrations found in this manuscript.
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                {book.images.map((img: any, idx: number) => {
                  const imgUrl =
                    typeof img === 'string'
                      ? `/api/books/${bookFolder}/images/${img}`
                      : img.url || `/api/books/${bookFolder}/images/${img.filename}`
                  const pNum = typeof img === 'object' && img.page_num ? img.page_num : idx + 1
                  const hasError = imageErrors[idx]

                  return (
                    <div
                      key={idx}
                      onClick={() => !hasError && setActiveLightboxImg({ url: imgUrl, page_num: pNum })}
                      className="group rounded-2xl p-2 bg-secondary/40 text-center flex flex-col justify-between cursor-pointer hover:bg-secondary/70 transition-all"
                    >
                      {hasError ? (
                        <div className="h-28 w-full flex flex-col items-center justify-center rounded-lg bg-background/50 text-muted-foreground">
                          <ImageOff className="h-6 w-6 mb-1 opacity-50" />
                          <span className="text-[10px]">{t('book.unavailable')}</span>
                        </div>
                      ) : (
                        <div className="relative overflow-hidden rounded-lg bg-background/50">
                          <img
                            src={imgUrl}
                            alt={`Page ${pNum}`}
                            className="h-28 w-full object-contain mx-auto group-hover:scale-105 transition-transform duration-200"
                            loading="lazy"
                            onError={() => {
                              setImageErrors((prev) => ({ ...prev, [idx]: true }))
                            }}
                          />
                        </div>
                      )}
                      <span className="text-[11px] text-muted-foreground block truncate mt-1.5">
                        {t('book.page', { n: pNum })}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tab: Metrics */}
      {activeTab === 'metrics' && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div className="text-left">
              <CardTitle>{t('book.metricsTitle')}</CardTitle>
              <CardDescription>{t('book.metricsDesc')}</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-4 rounded-2xl bg-secondary">
                <span className="text-muted-foreground block text-[11px]">{t('book.mTotalTime')}</span>
                <span className="text-lg font-semibold text-foreground mt-0.5 block">
                  {metrics.total_duration_seconds ? `${metrics.total_duration_seconds.toFixed(1)}s` : t('common.na')}
                </span>
              </div>
              <div className="p-4 rounded-2xl bg-secondary">
                <span className="text-muted-foreground block text-[11px]">{t('book.mTotalTokens')}</span>
                <span className="text-lg font-semibold text-foreground mt-0.5 block">
                  {metrics.total_tokens ? metrics.total_tokens.toLocaleString() : t('common.na')}
                </span>
              </div>
              <div className="p-4 rounded-2xl bg-secondary">
                <span className="text-muted-foreground block text-[11px]">{t('book.mEstimatedCost')}</span>
                <span className="text-lg font-semibold text-foreground mt-0.5 block">
                  {metrics.total_cost_toman
                    ? `${Math.round(metrics.total_cost_toman).toLocaleString()} T`
                    : t('common.na')}
                </span>
              </div>
              <div className="p-4 rounded-2xl bg-secondary">
                <span className="text-muted-foreground block text-[11px]">{t('book.mAvgPerChapter')}</span>
                <span className="text-lg font-semibold text-foreground mt-0.5 block">
                  {metrics.average_cost_toman_per_chapter
                    ? `${Math.round(metrics.average_cost_toman_per_chapter).toLocaleString()} T`
                    : t('common.na')}
                </span>
              </div>
            </div>

            {metrics.chapters && metrics.chapters.length > 0 && (
              <div className="rounded-2xl overflow-hidden bg-secondary/30">
                <table className="w-full text-left text-xs">
                  <thead className="bg-secondary text-muted-foreground font-medium">
                    <tr>
                      <th className="p-3">{t('book.mColChapter')}</th>
                      <th className="p-3 text-right">{t('book.mColDuration')}</th>
                      <th className="p-3 text-right">{t('book.mColTokens')}</th>
                      <th className="p-3 text-right">{t('book.mColCost')}</th>
                      <th className="p-3 text-right">{t('book.mColNlp')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-secondary/40">
                    {metrics.chapters.map((ch: any) => (
                      <tr key={ch.chapter_index} className="hover:bg-secondary/40 transition-colors">
                        <td className="p-3 font-medium text-foreground">{ch.chapter_name}</td>
                        <td className="p-3 text-right text-muted-foreground">
                          {ch.duration_seconds ? `${ch.duration_seconds.toFixed(1)}s` : '-'}
                        </td>
                        <td className="p-3 text-right text-foreground">
                          {ch.total_tokens?.toLocaleString() || 0}
                        </td>
                        <td className="p-3 text-right text-foreground">
                          {ch.cost_toman ? `${Math.round(ch.cost_toman).toLocaleString()} T` : '0 T'}
                        </td>
                        <td className="p-3 text-right text-muted-foreground">{ch.nlp_mutations_count || 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
