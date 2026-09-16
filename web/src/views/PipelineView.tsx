import React, { useState, useRef, useEffect } from 'react'
import {
  UploadCloud,
  FileText,
  Play,
  CheckCircle2,
  Terminal,
  ArrowRight,
  Square,
} from 'lucide-react'
import { Api, BookSummary } from '../api'
import {
  getMonitorState,
  subscribePipeline,
  startPipelineMonitor,
  cancelPipelineTask,
  appendMonitorLog,
  MonitorState,
} from '../lib/pipelineMonitor'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { Checkbox } from '../components/ui/Checkbox'
import { ChapterSelector, ChapterItem } from '../components/ui/ChapterSelector'
import { useI18n } from '../lib/i18n'

interface PipelineViewProps {
  onOpenBook: (bookFolder: string) => void
}

const GENRE_VALUES = [
  'auto',
  'fantasy',
  'scifi',
  'romance',
  'thriller_mystery',
  'horror',
  'historical_fiction',
  'business',
  'self_help_psychology',
  'health_fitness',
  'psychology_communication',
  'spirituality_mindset',
  'academic_research',
  'biography_memoir',
  'general',
]

export const PipelineView: React.FC<PipelineViewProps> = ({ onOpenBook }) => {
  const { t, tGenre, tStatus } = useI18n()
  const [file, setFile] = useState<File | null>(null)
  const [uploadedPath, setUploadedPath] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  const [genre, setGenre] = useState('auto')
  const [targetLanguage, setTargetLanguage] = useState('Persian')
  const [llmModel, setLlmModel] = useState('')
  const [translate, setTranslate] = useState(true)
  const [extractImages, setExtractImages] = useState(true)
  const [persianNlp, setPersianNlp] = useState(true)

  const [skipGliner, setSkipGliner] = useState(false)
  const [chapters, setChapters] = useState('')

  const [mon, setMon] = useState<MonitorState>(() => getMonitorState())
  const running = mon.status === 'running' || mon.status === 'cancelling'
  const logs = mon.logs
  const completedBookFolder = mon.bookFolder
  const status = mon.status

  useEffect(() => subscribePipeline(setMon), [])

  useEffect(() => {
    const t = setTimeout(() => {
      if (terminalRef.current) {
        terminalRef.current.scrollTop = terminalRef.current.scrollHeight
      }
    }, 50)
    return () => clearTimeout(t)
  }, [mon.logs])

  const [existingBooks, setExistingBooks] = useState<BookSummary[]>([])
  const [selectedExisting, setSelectedExisting] = useState('')
  const [detectedChapters, setDetectedChapters] = useState<ChapterItem[]>([])

  const terminalRef = useRef<HTMLDivElement>(null)

  const loadExistingBooks = async () => {
    try {
      const data = await Api.getBooks()
      setExistingBooks(data)
    } catch {}
  }

  useEffect(() => {
    loadExistingBooks()
  }, [])

  const handleSelectExistingBook = async (folder: string) => {
    setSelectedExisting(folder)
    if (!folder) {
      setUploadedPath(null)
      setDetectedChapters([])
      return
    }
    try {
      const b = await Api.getBook(folder)
      if (b.metadata && b.metadata.genre) {
        setGenre(b.metadata.genre)
      }
      setDetectedChapters(
        b.chapters.map((c, idx) => ({
          slug: c.slug,
          index: idx + 1,
          title: c.slug,
          word_count: c.word_count,
          is_translated: c.is_translated,
        }))
      )
      setUploadedPath(`output/${folder}/original/book.md`)
    } catch (err: any) {
      alert(err.message || t('pipeline.inspectFail'))
    }
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0]
      setFile(selected)
      setUploading(true)
      try {
        const res = await Api.uploadFile(selected)
        setUploadedPath(res.path)
        if (res.genre) setGenre(res.genre)
        loadExistingBooks()
      } catch (err: any) {
        alert(err.message || t('pipeline.uploadFail'))
      } finally {
        setUploading(false)
      }
    }
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const selected = e.dataTransfer.files[0]
      setFile(selected)
      setUploading(true)
      try {
        const res = await Api.uploadFile(selected)
        setUploadedPath(res.path)
        if (res.genre) setGenre(res.genre)
        loadExistingBooks()
      } catch (err: any) {
        alert(err.message || t('pipeline.uploadFail'))
      } finally {
        setUploading(false)
      }
    }
  }

  const startPipeline = async () => {
    if (!uploadedPath) return

    try {
      const res = await Api.runPipeline({
        file_path: uploadedPath,
        genre,
        target_language: targetLanguage,
        llm_model: llmModel || undefined,
        translate,
        skip_gliner: skipGliner,
        extract_images: extractImages,
        persian_nlp: persianNlp,
        chapters: chapters || undefined,
      })

      startPipelineMonitor(res.task_id)
    } catch (err: any) {
      appendMonitorLog(t('pipeline.launchFailed', { msg: err.message }))
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-foreground">{t('nav.pipeline')}</h1>
        <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
          {t('pipeline.subtitle')}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <Card>
            <CardHeader className="pb-4">
              <CardTitle>{t('pipeline.sourceTitle')}</CardTitle>
              <CardDescription>{t('pipeline.sourceDesc')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                className="relative rounded-3xl p-8 flex flex-col items-center justify-center text-center cursor-pointer bg-secondary/40 hover:bg-secondary/70 transition-colors"
              >
                <input
                  type="file"
                  accept=".pdf,.epub,.mobi,.md,.txt"
                  onChange={handleFileChange}
                  className="absolute inset-0 opacity-0 cursor-pointer"
                />
                <UploadCloud className="h-10 w-10 text-muted-foreground/60 mb-3" />
                <div className="text-sm font-medium text-foreground">
                  {file ? file.name : t('pipeline.chooseFile')}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t('pipeline.fileTypes')}
                </div>
              </div>

              {uploading && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                  <span>{t('pipeline.processing')}</span>
                </div>
              )}

              {existingBooks.length > 0 && (
                <div className="space-y-2 pt-2">
                  <Select
                    label={t('pipeline.selectExisting')}
                    value={selectedExisting}
                    onChange={(e) => handleSelectExistingBook(e.target.value)}
                  >
                    <option value="">{t('pipeline.chooseFromLibrary')}</option>
                    {existingBooks.map((b) => (
                      <option key={b.folder} value={b.folder}>
                        {t('pipeline.bookOption', { title: b.title, n: b.total_chapters })}
                      </option>
                    ))}
                  </Select>
                </div>
              )}

              {uploadedPath && !uploading && (
                <div className="flex items-center justify-between p-3 rounded-2xl bg-success-light text-success text-xs font-medium">
                  <div className="flex items-center gap-2.5 truncate">
                    <FileText className="h-4 w-4 shrink-0" />
                    <span className="truncate">{file ? file.name : selectedExisting}</span>
                  </div>
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-4">
              <CardTitle>{t('pipeline.optionsTitle')}</CardTitle>
              <CardDescription>{t('pipeline.optionsDesc')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Select
                label={t('pipeline.genrePreset')}
                value={genre}
                onChange={(e) => setGenre(e.target.value)}
              >
                {GENRE_VALUES.map((gv) => (
                  <option key={gv} value={gv}>
                    {tGenre(gv)}
                  </option>
                ))}
              </Select>

              <Input
                label={t('pipeline.targetLanguage')}
                value={targetLanguage}
                onChange={(e) => setTargetLanguage(e.target.value)}
                placeholder={t('pipeline.targetLanguagePh')}
              />

              <div className="space-y-2">
                {detectedChapters.length > 0 ? (
                  <ChapterSelector
                    chapters={detectedChapters}
                    value={chapters}
                    onChange={setChapters}
                  />
                ) : (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between px-1">
                      <label className="text-xs font-medium text-muted-foreground">{t('pipeline.chapterRange')}</label>
                      <div className="flex gap-1.5">
                        <button
                          type="button"
                          onClick={() => setChapters('all')}
                          className="px-2.5 py-0.5 rounded-full text-xs bg-secondary hover:bg-accent text-foreground font-medium transition-colors border-0"
                        >
                          {t('pipeline.all')}
                        </button>
                        <button
                          type="button"
                          onClick={() => setChapters('1-3')}
                          className="px-2.5 py-0.5 rounded-full text-xs bg-secondary hover:bg-accent text-foreground font-medium transition-colors border-0"
                        >
                          1-3
                        </button>
                        <button
                          type="button"
                          onClick={() => setChapters('1-5')}
                          className="px-2.5 py-0.5 rounded-full text-xs bg-secondary hover:bg-accent text-foreground font-medium transition-colors border-0"
                        >
                          1-5
                        </button>
                      </div>
                    </div>
                    <Input
                      value={chapters}
                      onChange={(e) => setChapters(e.target.value)}
                      placeholder={t('pipeline.chapterRangePh')}
                    />
                  </div>
                )}
              </div>

              <div className="flex flex-col gap-3.5 pt-3 border-t border-muted/30">
                <Checkbox
                  checked={translate}
                  onChange={(e) => setTranslate(e.target.checked)}
                  label={t('pipeline.fullTranslation')}
                  title={t('pipeline.fullTranslationTitle')}
                />

                <Checkbox
                  checked={extractImages}
                  onChange={(e) => setExtractImages(e.target.checked)}
                  label={t('pipeline.extractImages')}
                  title={t('pipeline.extractImagesTitle')}
                />

                <Checkbox
                  checked={persianNlp}
                  onChange={(e) => setPersianNlp(e.target.checked)}
                  label={t('pipeline.nlpCopyedit')}
                  title={t('pipeline.nlpCopyeditTitle')}
                />

                <Checkbox
                  checked={skipGliner}
                  onChange={(e) => setSkipGliner(e.target.checked)}
                  label={t('pipeline.skipGliner')}
                  title={t('pipeline.skipGlinerTitle')}
                />
              </div>

              <Button
                variant="primary"
                size="lg"
                className="w-full justify-center mt-4 text-sm font-medium rounded-full h-11"
                onClick={startPipeline}
                disabled={!uploadedPath || running}
                loading={running}
              >
                <span>{t('pipeline.start')}</span>
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2 space-y-4">
          <Card className="h-full flex flex-col">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div className="flex items-center gap-2.5">
                <Terminal className="h-4 w-4 text-primary" />
                <CardTitle className="text-base">{t('pipeline.console')}</CardTitle>
                {mon.status !== 'idle' && (
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide ${
                      mon.status === 'running'
                        ? 'bg-primary/15 text-primary'
                        : mon.status === 'completed'
                          ? 'bg-success-light text-success'
                          : 'bg-destructive/15 text-destructive'
                    }`}
                  >
                    {tStatus(mon.status)}
                  </span>
                )}
              </div>
              {mon.status === 'running' && mon.taskId && (
                <Button
                  size="sm"
                  className="gap-1.5 bg-rose-500/15 text-rose-600 dark:text-rose-400 hover:bg-rose-500/25"
                  onClick={() => {
                    if (window.confirm(t('pipeline.cancelConfirm'))) {
                      cancelPipelineTask(mon.taskId as string)
                    }
                  }}
                >
                  <Square className="h-3.5 w-3.5" />
                  <span>{t('common.cancel')}</span>
                </Button>
              )}
            </CardHeader>
            <CardContent className="flex-1 flex flex-col p-6 pt-0">
              <div
                ref={terminalRef}
                className="flex-1 min-h-[420px] max-h-[580px] rounded-3xl bg-secondary/40 p-6 font-mono text-xs text-foreground overflow-y-auto custom-scrollbar space-y-1.5 border-0 select-text"
              >
                {logs.length === 0 ? (
                  <div className="text-muted-foreground/60 p-8 text-center">
                    {t('pipeline.awaiting')}
                  </div>
                ) : (
                  logs.map((line, idx) => (
                    <div key={idx} className="leading-relaxed">
                      {line}
                    </div>
                  ))
                )}
              </div>

              {status === 'completed' && completedBookFolder && (
                <div className="mt-4 p-4 rounded-2xl bg-success-light text-success flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-medium">
                    <CheckCircle2 className="h-4 w-4" />
                    <span>{t('pipeline.finished')}</span>
                  </div>
                  <Button
                    size="sm"
                    className="gap-1.5"
                    onClick={() => onOpenBook(completedBookFolder)}
                  >
                    <span>{t('pipeline.openBook')}</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
