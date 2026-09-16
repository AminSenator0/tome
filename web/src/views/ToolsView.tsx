import React, { useState, useEffect } from 'react'
import {
  Compass,
  FileSearch,
  FileType2,
  ListOrdered,
  ScanFace,
  GitGraph,
  Languages,
  Wand2,
  FileCheck2,
  UploadCloud,
  Check,
  Copy,
  Image as ImageIcon,
  Download,
  BookOpen,
} from 'lucide-react'
import { Api, BookSummary } from '../api'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { DiffViewer } from '../components/ui/DiffViewer'
import { MermaidGraph } from '../components/ui/MermaidGraph'
import { useI18n } from '../lib/i18n'

type ToolType =
  | 'genre'
  | 'images'
  | 'metadata'
  | 'convert'
  | 'chapterize'
  | 'gliner'
  | 'graph'
  | 'translate'
  | 'copyedit'
  | 'compile'

export const ToolsView: React.FC = () => {
  const { t, tGenre } = useI18n()
  const [activeTool, setActiveTool] = useState<ToolType>('genre')
  const [books, setBooks] = useState<BookSummary[]>([])
  const [selectedBookFolder, setSelectedBookFolder] = useState<string>('')
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [uploadingShared, setUploadingShared] = useState(false)

  // Genre Detector state
  const [genreFilename, setGenreFilename] = useState('')
  const [genreResult, setGenreResult] = useState<any>(null)
  const [loadingGenre, setLoadingGenre] = useState(false)

  // Image Extractor state
  const [imageResult, setImageResult] = useState<any>(null)
  const [loadingImages, setLoadingImages] = useState(false)

  // Metadata Refiner state
  const [metaResult, setMetaResult] = useState<any>(null)
  const [loadingMeta, setLoadingMeta] = useState(false)

  // Manuscript Converter state
  const [convResult, setConvResult] = useState<any>(null)
  const [loadingConv, setLoadingConv] = useState(false)

  // Chapter Segmenter state
  const [chapText, setChapText] = useState('')
  const [chapTitle, setChapTitle] = useState('MyBook')
  const [chapResult, setChapResult] = useState<any>(null)
  const [loadingChap, setLoadingChap] = useState(false)

  // GLiNER state
  const [glinerGenre, setGlinerGenre] = useState('auto')
  const [glinerResult, setGlinerResult] = useState<any>(null)
  const [loadingGliner, setLoadingGliner] = useState(false)

  // Character Graph state
  const [graphMarkdown, setGraphMarkdown] = useState('')
  const [loadingGraph, setLoadingGraph] = useState(false)

  // Single Translator state
  const [transText, setTransText] = useState('')
  const [transLang, setTransLang] = useState('Persian')
  const [transGlossary, setTransGlossary] = useState('')
  const [transResult, setTransResult] = useState<any>(null)
  const [loadingTrans, setLoadingTrans] = useState(false)

  // Persian NLP Copyeditor state
  const [copyeditText, setCopyeditText] = useState('')
  const [copyeditResult, setCopyeditResult] = useState<any>(null)
  const [loadingCopyedit, setLoadingCopyedit] = useState(false)

  // Compiler state
  const [compileBookTitle, setCompileBookTitle] = useState('')
  const [compileResult, setCompileResult] = useState<any>(null)
  const [loadingCompile, setLoadingCompile] = useState(false)

  const loadBooks = async () => {
    try {
      const data = await Api.getBooks()
      setBooks(data)
      if (data.length > 0 && !compileBookTitle) {
        setCompileBookTitle(data[0].folder)
      }
    } catch {}
  }

  useEffect(() => {
    loadBooks()
  }, [])

  const handleSelectBook = async (folder: string) => {
    setSelectedBookFolder(folder)
    if (!folder) return
    try {
      const b = await Api.getBook(folder)
      setGenreFilename(`${folder}.pdf`)
      setCompileBookTitle(folder)
      setChapTitle(folder)
      if (b.book_md) {
        setChapText(b.book_md)
        setTransText(b.book_md.slice(0, 1000))
        setCopyeditText(b.book_md.slice(0, 1000))
      }
      if (b.glossary) {
        setTransGlossary(b.glossary)
      }
      if (b.graph_markdown) {
        setGraphMarkdown(b.graph_markdown)
      }
    } catch (err) {
      console.error(err)
    }
  }

  const handleSharedFileUpload = async (file: File) => {
    setUploadedFile(file)
    setUploadingShared(true)
    try {
      const res = await Api.uploadFile(file)
      await loadBooks()
      if (res.book_folder) {
        setSelectedBookFolder(res.book_folder)
        setCompileBookTitle(res.book_folder)
        handleSelectBook(res.book_folder)
      }
      setGenreFilename(file.name)
    } catch (err: any) {
      alert(err.message || t('tools.uploadFail'))
    } finally {
      setUploadingShared(false)
    }
  }

  const toolMenu: { id: ToolType; label: string; icon: React.ReactNode }[] = [
    { id: 'genre', label: t('tools.toolGenre'), icon: <Compass className="h-4 w-4" /> },
    { id: 'images', label: t('tools.toolImages'), icon: <ImageIcon className="h-4 w-4" /> },
    { id: 'metadata', label: t('tools.toolMetadata'), icon: <FileSearch className="h-4 w-4" /> },
    { id: 'convert', label: t('tools.toolConvert'), icon: <FileType2 className="h-4 w-4" /> },
    { id: 'chapterize', label: t('tools.toolChapterize'), icon: <ListOrdered className="h-4 w-4" /> },
    { id: 'gliner', label: t('tools.toolGliner'), icon: <ScanFace className="h-4 w-4" /> },
    { id: 'graph', label: t('tools.toolGraph'), icon: <GitGraph className="h-4 w-4" /> },
    { id: 'translate', label: t('tools.toolTranslate'), icon: <Languages className="h-4 w-4" /> },
    { id: 'copyedit', label: t('tools.toolCopyedit'), icon: <Wand2 className="h-4 w-4" /> },
    { id: 'compile', label: t('tools.toolCompile'), icon: <FileCheck2 className="h-4 w-4" /> },
  ]

  const runGenre = async () => {
    setLoadingGenre(true)
    try {
      let text = ''
      let fn = selectedBookFolder || genreFilename
      if (!fn && uploadedFile) {
        fn = uploadedFile.name
      }
      const res = await Api.detectGenre(text, fn)
      setGenreResult(res)
    } catch (err: any) {
      alert(err.message || t('tools.genreFail'))
    } finally {
      setLoadingGenre(false)
    }
  }

  const runImages = async () => {
    setLoadingImages(true)
    try {
      const path = selectedBookFolder ? `output/${selectedBookFolder}` : undefined
      const res = await Api.extractImages(uploadedFile || undefined, path)
      setImageResult(res)
    } catch (err: any) {
      alert(err.message || t('tools.imagesFail'))
    } finally {
      setLoadingImages(false)
    }
  }

  const runMeta = async () => {
    setLoadingMeta(true)
    try {
      const path = selectedBookFolder ? `output/${selectedBookFolder}` : undefined
      const res = await Api.extractMetadata(uploadedFile || undefined, path, true)
      setMetaResult(res)
    } catch (err: any) {
      alert(err.message || t('tools.metadataFail'))
    } finally {
      setLoadingMeta(false)
    }
  }

  const runConvert = async () => {
    setLoadingConv(true)
    try {
      let res
      if (uploadedFile) {
        res = await Api.convertDocument(uploadedFile)
      } else if (selectedBookFolder) {
        res = await Api.convertDocument(undefined, `output/${selectedBookFolder}`)
      }
      setConvResult(res)
      await loadBooks()
    } catch (err: any) {
      alert(err.message || t('tools.convertFail'))
    } finally {
      setLoadingConv(false)
    }
  }

  const runChapterize = async () => {
    setLoadingChap(true)
    try {
      let text = chapText
      let title = chapTitle || 'book'
      if (!text && selectedBookFolder) {
        const b = await Api.getBook(selectedBookFolder)
        title = b.folder
        text = b.book_md || ''
      }
      if (!text && uploadedFile) {
        const converted = await Api.convertDocument(uploadedFile)
        text = converted.preview
        title = converted.book_title
      }
      if (!text) {
        alert(t('tools.chapterizeNeed'))
        return
      }
      const res = await Api.segmentChapters(text, title)
      setChapResult(res)
      await loadBooks()
    } catch (err: any) {
      alert(err.message || t('tools.chapterizeFail'))
    } finally {
      setLoadingChap(false)
    }
  }

  const runGliner = async () => {
    setLoadingGliner(true)
    try {
      let text = ''
      if (selectedBookFolder) {
        const b = await Api.getBook(selectedBookFolder)
        text = b.book_md ? b.book_md.slice(0, 15000) : ''
      } else if (uploadedFile) {
        const converted = await Api.convertDocument(uploadedFile)
        text = converted.preview
      }
      if (!text && !selectedBookFolder) {
        alert(t('tools.glinerNeed'))
        return
      }
      const res = await Api.extractEntities(text, glinerGenre, selectedBookFolder || undefined)
      setGlinerResult(res)
    } catch (err: any) {
      alert(err.message || t('tools.glinerFail'))
    } finally {
      setLoadingGliner(false)
    }
  }

  const runGraph = async () => {
    if (!selectedBookFolder) {
      alert(t('tools.graphNeed'))
      return
    }
    setLoadingGraph(true)
    try {
      const b = await Api.getBook(selectedBookFolder)
      const chaps = (b.chapters || []).map((c) => ({ slug: c.slug, title: c.slug }))
      const ents: any[] = []
      const res = await Api.buildGraph(chaps, ents, b.folder)
      setGraphMarkdown(res.graph_markdown || res.graph || '')
    } catch (err: any) {
      alert(err.message || t('tools.graphFail'))
    } finally {
      setLoadingGraph(false)
    }
  }

  const runTranslate = async () => {
    let text = transText
    if (!text && selectedBookFolder) {
      const b = await Api.getBook(selectedBookFolder)
      text = b.book_md ? b.book_md.slice(0, 1000) : ''
    }
    if (!text) {
      alert(t('tools.translateNeed'))
      return
    }
    setLoadingTrans(true)
    try {
      const res = await Api.translateText(
        text,
        transLang,
        transGlossary,
        '',
        glinerGenre !== 'auto' ? glinerGenre : undefined,
        selectedBookFolder || undefined
      )
      setTransResult(res)
    } catch (err: any) {
      alert(err.message || t('tools.translateFail'))
    } finally {
      setLoadingTrans(false)
    }
  }

  const runCopyedit = async () => {
    let text = copyeditText
    if (!text && selectedBookFolder) {
      const b = await Api.getBook(selectedBookFolder)
      text = b.book_md ? b.book_md.slice(0, 5000) : ''
      if (text) setCopyeditText(text)
    }
    if (!text && !selectedBookFolder) {
      alert(t('tools.copyeditNeed'))
      return
    }
    setLoadingCopyedit(true)
    try {
      const res = await Api.copyeditPersian(text || '', selectedBookFolder || undefined)
      setCopyeditResult(res)
      if (res.edited_text && !copyeditText) {
        setCopyeditText(res.edited_text)
      }
    } catch (err: any) {
      alert(err.message || t('tools.copyeditFail'))
    } finally {
      setLoadingCopyedit(false)
    }
  }

  const runCompile = async () => {
    const targetBook = compileBookTitle || selectedBookFolder
    if (!targetBook) {
      alert(t('tools.compileNeed'))
      return
    }
    setLoadingCompile(true)
    try {
      const res = await Api.compileDocx(targetBook)
      setCompileResult(res)
    } catch (err: any) {
      alert(err.message || t('tools.compileFail'))
    } finally {
      setLoadingCompile(false)
    }
  }

  const renderSharedSourceSelector = () => (
    <div className="space-y-3 pb-3 border-b border-muted/30">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-end">
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground px-1 block">
{t('tools.uploadManuscript')}
          </label>
          <label className="flex items-center justify-center h-11 w-full rounded-2xl border-0 bg-secondary px-4 py-2 text-sm text-foreground hover:opacity-90 cursor-pointer transition-all gap-2">
            <UploadCloud className="h-4 w-4 text-muted-foreground" />
            <span className="truncate">
              {uploadedFile ? uploadedFile.name : t('tools.chooseFile')}
            </span>
            <input
              type="file"
              accept=".pdf,.epub,.mobi,.txt,.md"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleSharedFileUpload(e.target.files[0])
                }
              }}
              className="hidden"
            />
          </label>
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground px-1 block">
{t('tools.orChooseFromLibrary')}
          </label>
          <Select
            value={selectedBookFolder}
            onChange={(e) => handleSelectBook(e.target.value)}
          >
            <option value="">{t('tools.chooseFromLibrary')}</option>
            {books.map((b) => (
              <option key={b.folder} value={b.folder}>
                {t('pipeline.bookOption', { title: b.title, n: b.total_chapters })}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {selectedBookFolder && (
        <div className="flex items-center justify-between px-3.5 py-2 rounded-2xl bg-secondary/60 text-xs mt-1">
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-primary shrink-0" />
            <span className="text-muted-foreground">{t('tools.activeManuscript')}</span>
            <span className="font-semibold text-foreground truncate max-w-[280px]">{selectedBookFolder}</span>
          </div>
          <button
            type="button"
            onClick={() => {
              setSelectedBookFolder('')
              setManualBookName('MyBook')
            }}
            className="text-[11px] font-medium text-muted-foreground hover:text-foreground cursor-pointer px-2 py-0.5 rounded-full hover:bg-secondary transition-colors"
          >
{t('common.clear')}
          </button>
        </div>
      )}

      {uploadingShared && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground pt-1">
          <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <span>{t('tools.ingesting')}</span>
        </div>
      )}
    </div>
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-foreground">{t('nav.tools')}</h1>
        <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
          {t('tools.subtitle')}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-1 rounded-3xl bg-card p-3 space-y-1.5 h-fit border-0">
          <div className="text-[11px] font-semibold text-muted-foreground uppercase px-3 py-2 tracking-wider">
{t('tools.availableTools')}
          </div>
          {toolMenu.map((tool) => {
            const active = activeTool === tool.id
            return (
              <button
                key={tool.id}
                onClick={() => setActiveTool(tool.id)}
                className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-full text-xs font-medium transition-all text-left border-0 cursor-pointer ${
                  active
                    ? 'bg-foreground text-background'
                    : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
                }`}
              >
                {tool.icon}
                <span>{tool.label}</span>
              </button>
            )
          })}
        </div>

        <div className="lg:col-span-3">
          {activeTool === 'genre' && (
            <Card>
              <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
                <div className="text-left">
                  <CardTitle>{t('tools.toolGenre')}</CardTitle>
                  <CardDescription>
                    {t('tools.genreDesc')}
                  </CardDescription>
                </div>
                <Button
                  onClick={runGenre}
                  disabled={!uploadedFile && !selectedBookFolder}
                  loading={loadingGenre}
                  className="h-10 px-5 text-sm font-medium rounded-full w-full sm:w-auto shrink-0 whitespace-nowrap"
                >
                  <span>{t('tools.genreRun')}</span>
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {renderSharedSourceSelector()}

                {genreResult && (
                  <div className="p-4 rounded-3xl bg-secondary/50 mt-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-muted-foreground">{t('tools.detectedClassification')}</span>
                      <Badge variant="success" className="capitalize text-xs font-semibold px-3 py-1">
                        {genreResult.genre}
                      </Badge>
                    </div>
                    {genreResult.detected && genreResult.detected.toLowerCase() !== genreResult.genre.toLowerCase() && (
                      <div className="text-xs text-muted-foreground flex items-center justify-between pt-1 border-t border-muted/20">
                        <span>{t('tools.matchedRule')}</span>
                        <span className="font-mono text-foreground font-medium">{genreResult.detected}</span>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {activeTool === 'images' && (
            <Card>
              <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
                <div className="text-left">
                  <CardTitle>{t('tools.toolImages')}</CardTitle>
                  <CardDescription>
                    {t('tools.imagesDesc')}
                  </CardDescription>
                </div>
                <Button
                  onClick={runImages}
                  disabled={!uploadedFile && !selectedBookFolder}
                  loading={loadingImages}
                  className="h-10 px-5 text-sm font-medium rounded-full w-full sm:w-auto shrink-0 whitespace-nowrap"
                >
                  <span>{t('tools.imagesRun')}</span>
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {renderSharedSourceSelector()}

                {imageResult && (
                  <div className="mt-4 space-y-4">
                    <div className="flex items-center justify-between p-4 rounded-2xl bg-secondary text-xs">
                      <span>
                        {t('tools.foundImages', { n: imageResult.count, s: imageResult.duration_seconds })}
                      </span>
                      {imageResult.count > 0 && (
                        <a
                          href={`/api/books/${imageResult.book_title}/download/images_zip`}
                          download
                          className="inline-flex items-center gap-1.5 h-10 px-4 rounded-full bg-foreground text-background text-xs font-medium"
                        >
                          <Download className="h-3.5 w-3.5" />
                          <span>{t('book.downloadZip')}</span>
                        </a>
                      )}
                    </div>

                    <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3">
                      {imageResult.images.map((img: any) => (
                        <div key={img.index} className="rounded-2xl p-2 bg-secondary/50 text-center">
                          <img src={img.url} alt={img.filename} className="h-20 w-full object-contain mx-auto rounded-lg" />
                          <span className="text-[11px] text-muted-foreground block truncate mt-1">
                            p.{img.page_num}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {activeTool === 'metadata' && (
            <Card>
              <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
                <div className="text-left">
                  <CardTitle>{t('tools.toolMetadata')}</CardTitle>
                  <CardDescription>
                    {t('tools.metadataDesc')}
                  </CardDescription>
                </div>
                <Button
                  onClick={runMeta}
                  disabled={!uploadedFile && !selectedBookFolder}
                  loading={loadingMeta}
                  className="h-10 px-5 text-sm font-medium rounded-full w-full sm:w-auto shrink-0 whitespace-nowrap"
                >
                  <span>{t('tools.metadataRun')}</span>
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {renderSharedSourceSelector()}

                {metaResult && (
                  <div className="p-4 rounded-2xl bg-secondary mt-4 space-y-2 text-xs">
                    <div className="text-base font-semibold text-foreground">{metaResult.title}</div>
                    <div className="text-muted-foreground">{t('tools.metaLine', { authors: metaResult.authors?.join(', ') || t('common.na'), year: metaResult.year || t('common.na'), reading: metaResult.reading_time })}</div>
                    <p className="pt-2 text-foreground/80 leading-relaxed">{metaResult.synopsis}</p>
                    {metaResult.keywords && (
                      <div className="flex flex-wrap gap-1.5 pt-2">
                        {metaResult.keywords.map((kw: string, i: number) => (
                          <Badge key={i} variant="secondary">
                            {kw}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {activeTool === 'convert' && (
            <Card>
              <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
                <div className="text-left">
                  <CardTitle>{t('tools.toolConvert')}</CardTitle>
                  <CardDescription>
                    {t('tools.convertDesc')}
                  </CardDescription>
                </div>
                <Button
                  onClick={runConvert}
                  disabled={!uploadedFile && !selectedBookFolder}
                  loading={loadingConv}
                  className="h-10 px-5 text-sm font-medium rounded-full w-full sm:w-auto shrink-0 whitespace-nowrap"
                >
                  <span>{t('tools.convertRun')}</span>
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {renderSharedSourceSelector()}

                {convResult && (
                  <div className="mt-4 p-4 rounded-2xl bg-secondary flex items-center justify-between text-xs">
                    <div className="space-y-0.5">
                      <div className="font-semibold text-foreground">{convResult.book_title}</div>
                      <div className="text-muted-foreground">
                        {t('tools.convertLine', { pages: convResult.page_count })}
                      </div>
                    </div>
                    <a
                      href={`/api/books/${convResult.book_title}/download/original`}
                      download={`${convResult.book_title}.md`}
                      className="inline-flex items-center gap-1.5 h-10 px-4 rounded-full bg-foreground text-background text-xs font-medium hover:opacity-90 transition-opacity"
                    >
                      <Download className="h-3.5 w-3.5" />
                      <span>{t('tools.downloadMarkdown')}</span>
                    </a>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {activeTool === 'chapterize' && (
            <Card>
              <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
                <div className="text-left">
                  <CardTitle>{t('tools.toolChapterize')}</CardTitle>
                  <CardDescription>
                    {t('tools.chapterizeDesc')}
                  </CardDescription>
                </div>
                <Button
                  onClick={runChapterize}
                  disabled={!selectedBookFolder && !uploadedFile && !chapText}
                  loading={loadingChap}
                  className="h-10 px-5 text-sm font-medium rounded-full w-full sm:w-auto shrink-0 whitespace-nowrap"
                >
                  <span>{t('tools.chapterizeRun')}</span>
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {renderSharedSourceSelector()}

                {chapResult && (
                  <div className="mt-4 p-4 rounded-2xl bg-secondary space-y-2 text-xs">
                    <div className="font-semibold text-foreground">
                      {t('tools.chapterizeLine', { n: chapResult.chapter_count || chapResult.total_chapters, dir: chapResult.output_dir })}
                    </div>
                    <div className="flex flex-wrap gap-1.5 pt-2">
                      {(chapResult.chapters || []).map((ch: any) => (
                        <Badge key={ch.slug} variant="secondary">
                          {ch.slug} ({ch.word_count}w)
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {activeTool === 'gliner' && (
            <Card>
              <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
                <div className="text-left">
                  <CardTitle>{t('tools.toolGliner')}</CardTitle>
                  <CardDescription>
                    {t('tools.glinerDesc')}
                  </CardDescription>
                </div>
                <Button
                  onClick={runGliner}
                  disabled={!selectedBookFolder && !uploadedFile}
                  loading={loadingGliner}
                  className="h-10 px-5 text-sm font-medium rounded-full w-full sm:w-auto shrink-0 whitespace-nowrap"
                >
                  <span>{t('tools.glinerRun')}</span>
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {renderSharedSourceSelector()}
                <Select
                  label={t('tools.taxonomyPreset')}
                  value={glinerGenre}
                  onChange={(e) => setGlinerGenre(e.target.value)}
                >
                  <option value="auto">{tGenre('auto')}</option>
                  <option value="general">{tGenre('general')}</option>
                  <option value="fantasy">{tGenre('fantasy')}</option>
                  <option value="scifi">{tGenre('scifi')}</option>
                  <option value="romance">{tGenre('romance')}</option>
                  <option value="thriller_mystery">{tGenre('thriller_mystery')}</option>
                  <option value="horror">{tGenre('horror')}</option>
                  <option value="historical_fiction">{tGenre('historical_fiction')}</option>
                  <option value="business">{tGenre('business')}</option>
                  <option value="self_help_psychology">{tGenre('self_help_psychology')}</option>
                  <option value="health_fitness">{tGenre('health_fitness')}</option>
                  <option value="psychology_communication">{tGenre('psychology_communication')}</option>
                  <option value="spirituality_mindset">{tGenre('spirituality_mindset')}</option>
                  <option value="academic_research">{tGenre('academic_research')}</option>
                  <option value="biography_memoir">{tGenre('biography_memoir')}</option>
                </Select>

                {glinerResult && (
                  <div className="mt-4 p-4 rounded-2xl bg-secondary space-y-3 text-xs">
                    <div className="font-semibold text-foreground">{t('tools.extractedEntities', { n: glinerResult.raw_count })}</div>
                    <div className="space-y-2">
                      {Object.entries(glinerResult.clustered).map(([cat, ents]: [string, any]) => (
                        <div key={cat} className="space-y-1">
                          <span className="font-semibold text-muted-foreground uppercase text-[10px]">{cat}</span>
                          <div className="flex flex-wrap gap-1.5">
                            {ents.map((item: any, idx: number) => (
                              <Badge key={idx} variant="secondary">
                                {item.canonical} {item.aliases?.length ? `(${item.aliases.join(', ')})` : ''}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {activeTool === 'graph' && (
            <Card>
              <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
                <div className="text-left">
                  <CardTitle>{t('tools.toolGraph')}</CardTitle>
                  <CardDescription>
                    {t('tools.graphDesc')}
                  </CardDescription>
                </div>
                <Button
                  onClick={runGraph}
                  disabled={!selectedBookFolder}
                  loading={loadingGraph}
                  className="h-10 px-5 text-sm font-medium rounded-full w-full sm:w-auto shrink-0 whitespace-nowrap"
                >
                  <span>{t('tools.graphRun')}</span>
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {renderSharedSourceSelector()}

                {graphMarkdown ? (
                  <div className="mt-4 space-y-4">
                    <MermaidGraph content={graphMarkdown} />
                    <pre className="p-4 rounded-2xl bg-secondary/50 text-xs font-mono max-h-[300px] overflow-y-auto custom-scrollbar">
                      {graphMarkdown}
                    </pre>
                  </div>
                ) : (
                  <div className="p-8 text-center text-xs text-muted-foreground bg-secondary/30 rounded-2xl">
                    {t('tools.graphEmpty')}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {activeTool === 'translate' && (
            <Card>
              <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
                <div className="text-left">
                  <CardTitle>{t('tools.toolTranslate')}</CardTitle>
                  <CardDescription>
                    {t('tools.translateDesc')}
                  </CardDescription>
                </div>
                <Button
                  onClick={runTranslate}
                  disabled={!transText && !selectedBookFolder}
                  loading={loadingTrans}
                  className="h-10 px-5 text-sm font-medium rounded-full w-full sm:w-auto shrink-0 whitespace-nowrap"
                >
                  <span>{t('tools.translateRun')}</span>
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {renderSharedSourceSelector()}
                <Input
                  label={t('tools.targetLanguage')}
                  value={transLang}
                  onChange={(e) => setTransLang(e.target.value)}
                />
                <Textarea
                  label={t('tools.sourceText')}
                  value={transText}
                  onChange={(e) => setTransText(e.target.value)}
                  className="min-h-[120px]"
                  placeholder={t('tools.sourceTextPh')}
                />
                <Textarea
                  label={t('tools.glossaryMapping')}
                  value={transGlossary}
                  onChange={(e) => setTransGlossary(e.target.value)}
                  className="min-h-[80px]"
                  placeholder="| Term | Translation |"
                />

                {transResult && (
                  <div className="mt-4 p-4 rounded-2xl bg-secondary space-y-2">
                    <span className="text-xs font-semibold text-muted-foreground uppercase">{t('tools.output')}</span>
                    <pre
                      dir="rtl"
                      className="font-persian text-sm whitespace-pre-wrap leading-relaxed text-foreground"
                    >
                      {transResult.translated || transResult.translated_text}
                    </pre>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {activeTool === 'copyedit' && (
            <Card>
              <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
                <div className="text-left">
                  <CardTitle>{t('tools.toolCopyedit')}</CardTitle>
                  <CardDescription>
                    {t('tools.copyeditDesc')}
                  </CardDescription>
                </div>
                <Button
                  onClick={runCopyedit}
                  disabled={!copyeditText && !selectedBookFolder}
                  loading={loadingCopyedit}
                  className="h-10 px-5 text-sm font-medium rounded-full w-full sm:w-auto shrink-0 whitespace-nowrap"
                >
                  <span>{t('tools.copyeditRun')}</span>
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {renderSharedSourceSelector()}
                <Textarea
                  dir="rtl"
                  label={t('tools.persianText')}
                  value={copyeditText}
                  onChange={(e) => setCopyeditText(e.target.value)}
                  className="min-h-[140px] font-persian text-sm"
                  placeholder="متن فارسی جهت ویرایش و نیم‌فاصله‌گذاری..."
                />

                {copyeditResult && (
                  <div className="mt-4 space-y-3">
                    <DiffViewer
                      original={copyeditText}
                      modified={copyeditResult.edited_text || copyeditResult.normalized}
                      changes={copyeditResult.changes}
                      onCommit={(txt) => setCopyeditText(txt)}
                    />
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {activeTool === 'compile' && (
            <Card>
              <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
                <div className="text-left">
                  <CardTitle>{t('tools.toolCompile')}</CardTitle>
                  <CardDescription>
                    {t('tools.compileDesc')}
                  </CardDescription>
                </div>
                <Button
                  onClick={runCompile}
                  disabled={!compileBookTitle}
                  loading={loadingCompile}
                  className="h-10 px-5 text-sm font-medium rounded-full w-full sm:w-auto shrink-0 whitespace-nowrap"
                >
                  <span>{t('tools.compileRun')}</span>
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                <Select
                  label={t('tools.targetBook')}
                  value={compileBookTitle}
                  onChange={(e) => setCompileBookTitle(e.target.value)}
                >
                  {books.map((b) => (
                    <option key={b.folder} value={b.folder}>
                      {t('tools.bookTranslatedOption', { title: b.title, done: b.translated_chapters, total: b.total_chapters })}
                    </option>
                  ))}
                </Select>

                {compileResult && (
                  <div className="p-4 rounded-2xl bg-secondary mt-4 flex items-center justify-between text-xs">
                    <div>
                      <span className="font-semibold text-foreground block">{t('tools.compileOk')}</span>
                      <span className="text-muted-foreground text-[11px] block mt-0.5">
                        {t('tools.compileOkSub')}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {compileResult.docx_url && (
                        <a
                          href={compileResult.docx_url}
                          download
                          className="inline-flex items-center gap-1.5 h-9 px-4 rounded-full bg-foreground text-background text-xs font-medium"
                        >
                          <Download className="h-3.5 w-3.5" />
                          <span>{t('tools.downloadDocx')}</span>
                        </a>
                      )}
                      {compileResult.pdf_url && (
                        <a
                          href={compileResult.pdf_url}
                          download
                          className="inline-flex items-center gap-1.5 h-9 px-4 rounded-full bg-secondary text-foreground text-xs font-medium"
                        >
                          <Download className="h-3.5 w-3.5" />
                          <span>{t('tools.downloadPdf')}</span>
                        </a>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
