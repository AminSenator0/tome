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

interface PipelineViewProps {
  onOpenBook: (bookFolder: string) => void
}



export const PipelineView: React.FC<PipelineViewProps> = ({ onOpenBook }) => {
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
      alert(err.message || 'Failed to inspect book')
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
        alert(err.message || 'Upload failed')
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
        alert(err.message || 'Upload failed')
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
      appendMonitorLog(`[ERR] Launch failed: ${err.message}`)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-foreground">Pipeline Studio</h1>
        <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
          End-to-end manuscript processing, entity extraction, translation, and compilation
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <Card>
            <CardHeader className="pb-4">
              <CardTitle>1. Source Manuscript</CardTitle>
              <CardDescription>Upload PDF, EPUB, MOBI, or Markdown file</CardDescription>
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
                  {file ? file.name : 'Choose file or drag & drop'}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  PDF, EPUB, MOBI, Markdown, TXT
                </div>
              </div>

              {uploading && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                  <span>Processing manuscript & extracting metadata...</span>
                </div>
              )}

              {existingBooks.length > 0 && (
                <div className="space-y-2 pt-2">
                  <Select
                    label="Or Select Existing Manuscript"
                    value={selectedExisting}
                    onChange={(e) => handleSelectExistingBook(e.target.value)}
                  >
                    <option value="">Choose from Library...</option>
                    {existingBooks.map((b) => (
                      <option key={b.folder} value={b.folder}>
                        {b.title} ({b.total_chapters} chapters)
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
              <CardTitle>2. Run Options</CardTitle>
              <CardDescription>Configure extraction and translation settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Select
                label="Genre Preset"
                value={genre}
                onChange={(e) => setGenre(e.target.value)}
              >
                <option value="auto">Auto (Detect from text)</option>
                <option value="fantasy">Fantasy & Adventure</option>
                <option value="scifi">Science Fiction</option>
                <option value="romance">Romance & Drama</option>
                <option value="thriller_mystery">Thriller & Mystery</option>
                <option value="horror">Horror & Supernatural</option>
                <option value="historical_fiction">Historical Fiction</option>
                <option value="business">Business & Economics</option>
                <option value="self_help_psychology">Self-Help & Personal Development</option>
                <option value="health_fitness">Health & Fitness</option>
                <option value="psychology_communication">Psychology & Communication</option>
                <option value="spirituality_mindset">Spirituality & Mindset</option>
                <option value="academic_research">Academic & Research</option>
                <option value="biography_memoir">Biography & Memoir</option>
                <option value="general">General Literature</option>
              </Select>

              <Input
                label="Target Language"
                value={targetLanguage}
                onChange={(e) => setTargetLanguage(e.target.value)}
                placeholder="e.g. Persian"
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
                      <label className="text-xs font-medium text-muted-foreground">Chapter Range (Optional)</label>
                      <div className="flex gap-1.5">
                        <button
                          type="button"
                          onClick={() => setChapters('all')}
                          className="px-2.5 py-0.5 rounded-full text-xs bg-secondary hover:bg-accent text-foreground font-medium transition-colors border-0"
                        >
                          All
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
                      placeholder="e.g. all, 5, 1-3, 1,3,5"
                    />
                  </div>
                )}
              </div>

              <div className="flex flex-col gap-3.5 pt-3 border-t border-muted/30">
                <Checkbox
                  checked={translate}
                  onChange={(e) => setTranslate(e.target.checked)}
                  label="Full translation"
                  title="Translate chapters using contextual LLM agent"
                />

                <Checkbox
                  checked={extractImages}
                  onChange={(e) => setExtractImages(e.target.checked)}
                  label="Extract illustrations"
                  title="Extract embedded raster figures, plates, and charts"
                />

                <Checkbox
                  checked={persianNlp}
                  onChange={(e) => setPersianNlp(e.target.checked)}
                  label="NLP copyediting"
                  title="Apply Persian orthographic normalizer and ZWNJ correction"
                />

                <Checkbox
                  checked={skipGliner}
                  onChange={(e) => setSkipGliner(e.target.checked)}
                  label="Skip entity model (Fast)"
                  title="Bypass local entity model for faster LLM-only execution"
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
                <span>Start Pipeline</span>
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2 space-y-4">
          <Card className="h-full flex flex-col">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div className="flex items-center gap-2.5">
                <Terminal className="h-4 w-4 text-primary" />
                <CardTitle className="text-base">Live Execution Console</CardTitle>
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
                    {mon.status}
                  </span>
                )}
              </div>
              {mon.status === 'running' && mon.taskId && (
                <Button
                  size="sm"
                  className="gap-1.5 bg-rose-500/15 text-rose-600 dark:text-rose-400 hover:bg-rose-500/25"
                  onClick={() => {
                    if (window.confirm('Cancel this pipeline run? The current chapter will finish, then it stops.')) {
                      cancelPipelineTask(mon.taskId as string)
                    }
                  }}
                >
                  <Square className="h-3.5 w-3.5" />
                  <span>Cancel</span>
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
                    Awaiting pipeline execution. Logs will stream in real time.
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
                    <span>Manuscript processing finished. Artifacts are ready!</span>
                  </div>
                  <Button
                    size="sm"
                    className="gap-1.5"
                    onClick={() => onOpenBook(completedBookFolder)}
                  >
                    <span>Open Book Studio</span>
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
