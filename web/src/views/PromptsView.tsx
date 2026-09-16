import React, { useState, useEffect } from 'react'
import { Eye, Code, Variable, Check, RotateCcw } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { Api } from '../api'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { useI18n } from '../lib/i18n'

const KNOWN_VARIABLES: Record<string, { label: string; color: string; badge: string }> = {
  '{target_language}': {
    label: 'Target Language',
    color: 'bg-sky-500/15 text-sky-600 dark:text-sky-400 border border-sky-500/25',
    badge: 'bg-sky-500/15 text-sky-600 dark:text-sky-400 border border-sky-500/25',
  },
  '{user_style_rules}': {
    label: 'Style Directives',
    color: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/25',
    badge: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/25',
  },
  '{graph}': {
    label: 'Character Graph',
    color: 'bg-purple-500/15 text-purple-600 dark:text-purple-400 border border-purple-500/25',
    badge: 'bg-purple-500/15 text-purple-600 dark:text-purple-400 border border-purple-500/25',
  },
  '{glossary}': {
    label: 'Glossary Mapping',
    color: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25',
    badge: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25',
  },
  '{manuscript_filename}': {
    label: 'Source Filename',
    color: 'bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/25',
    badge: 'bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/25',
  },
  '{front_matter}': {
    label: 'Front Matter Excerpt',
    color: 'bg-orange-500/15 text-orange-600 dark:text-orange-400 border border-orange-500/25',
    badge: 'bg-orange-500/15 text-orange-600 dark:text-orange-400 border border-orange-500/25',
  },
  '{first_chapter}': {
    label: 'First Chapter Sample',
    color: 'bg-fuchsia-500/15 text-fuchsia-600 dark:text-fuchsia-400 border border-fuchsia-500/25',
    badge: 'bg-fuchsia-500/15 text-fuchsia-600 dark:text-fuchsia-400 border border-fuchsia-500/25',
  },
  '{metadata}': {
    label: 'Refined Metadata',
    color: 'bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/25',
    badge: 'bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/25',
  },
}

const VAR_LABEL_KEYS: Record<string, string> = {
  '{target_language}': 'prompts.varTargetLanguage',
  '{user_style_rules}': 'prompts.varStyle',
  '{graph}': 'prompts.varGraph',
  '{glossary}': 'prompts.varGlossary',
  '{manuscript_filename}': 'prompts.varFilename',
  '{front_matter}': 'prompts.varFrontMatter',
  '{first_chapter}': 'prompts.varFirstChapter',
  '{metadata}': 'prompts.varMetadata',
}

export const PromptsView: React.FC = () => {
  const { t } = useI18n()
  const [prompts, setPrompts] = useState<Record<string, string>>({})
  const [originalPrompts, setOriginalPrompts] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [activePromptKey, setActivePromptKey] = useState<string>('chapter_translation_with_glossary_system_prompt')
  const [viewMode, setViewMode] = useState<'preview' | 'edit'>('preview')

  const promptNames: Record<
    string,
    { label: string; desc: string; vars: string[] }
  > = {
    chapter_translation_with_glossary_system_prompt: {
      label: t('prompts.name1'),
      desc: t('prompts.name1Desc'),
      vars: ['{target_language}', '{user_style_rules}', '{graph}'],
    },
    chapter_translation_no_gliner_system_prompt: {
      label: t('prompts.name2'),
      desc: t('prompts.name2Desc'),
      vars: ['{target_language}', '{user_style_rules}', '{graph}'],
    },
    fantasy_translation_guidelines: {
      label: t('prompts.name3'),
      desc: t('prompts.name3Desc'),
      vars: ['{target_language}'],
    },
    glossary_translation_system_prompt: {
      label: t('prompts.name4'),
      desc: t('prompts.name4Desc'),
      vars: ['{target_language}'],
    },
    metadata_refinement_system_prompt: {
      label: t('prompts.name5'),
      desc: t('prompts.name5Desc'),
      vars: ['{metadata}'],
    },
    user_style_rules: {
      label: t('prompts.name6'),
      desc: t('prompts.name6Desc'),
      vars: [],
    },
  }

  const loadPrompts = async () => {
    setLoading(true)
    try {
      const data = await Api.getPrompts()
      setPrompts(data)
      setOriginalPrompts(data)
    } catch (err: any) {
      alert(err.message || t('prompts.loadFail'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadPrompts()
  }, [])

  const hasChanges = JSON.stringify(prompts) !== JSON.stringify(originalPrompts)

  const handleSave = async () => {
    if (!hasChanges || saving) return
    setSaving(true)
    try {
      await Api.updatePrompts(prompts)
      setOriginalPrompts(prompts)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err: any) {
      alert(err.message || t('prompts.saveFail'))
    } finally {
      setSaving(false)
    }
  }

  const handlePromptChange = (val: string) => {
    setPrompts((prev) => ({
      ...prev,
      [activePromptKey]: val,
    }))
  }

  const renderHighlightedMarkdown = (text: string) => {
    // Custom replacer for text nodes to highlight {variable} tokens inside markdown
    const renderWithVariables = (content: string) => {
      const parts = content.split(/({[a-zA-Z0-9_]+})/g)
      return parts.map((part, i) => {
        if (KNOWN_VARIABLES[part]) {
          return (
            <span
              key={i}
              className={`${KNOWN_VARIABLES[part].color} font-mono font-medium px-1.5 py-0.5 rounded-md inline-block`}
              title={t(VAR_LABEL_KEYS[part])}
            >
              {part.replace(/^\{|\}$/g, "")}
            </span>
          )
        }
        if (part.startsWith('{') && part.endsWith('}')) {
          return (
            <span
              key={i}
              className="bg-destructive/15 text-destructive border border-destructive/30 font-mono font-medium px-1.5 py-0.5 rounded-md inline-block"
              title={t('prompts.unknownVar')}
            >
              {part.replace(/^\{|\}$/g, "")}
            </span>
          )
        }
        return part
      })
    }

    return (
      <div className="p-6 rounded-3xl bg-secondary/30 text-xs text-foreground/90 max-h-[580px] overflow-y-auto custom-scrollbar select-text prose dark:prose-invert max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw]}
          components={{
            p: ({ children }) => (
              <p className="my-2.5 leading-relaxed text-foreground/90">
                {React.Children.map(children, (child) =>
                  typeof child === 'string' ? renderWithVariables(child) : child
                )}
              </p>
            ),
            li: ({ children }) => (
              <li className="my-1 leading-relaxed">
                {React.Children.map(children, (child) =>
                  typeof child === 'string' ? renderWithVariables(child) : child
                )}
              </li>
            ),
            h1: ({ node, ...props }) => <h3 className="text-sm font-semibold text-foreground mt-4 mb-2" {...props} />,
            h2: ({ node, ...props }) => <h4 className="text-xs font-semibold text-foreground mt-3 mb-1.5 uppercase tracking-wider" {...props} />,
            h3: ({ node, ...props }) => <h5 className="text-xs font-medium text-foreground mt-2 mb-1" {...props} />,
            code: ({ node, className, children, ...props }: any) => {
              const str = String(children)
              return (
                <code className="bg-secondary/80 font-mono px-1.5 py-0.5 rounded text-foreground font-normal" {...props}>
                  {renderWithVariables(str)}
                </code>
              )
            },
          }}
        >
          {text || t('prompts.noTemplate')}
        </ReactMarkdown>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-foreground">{t('nav.prompts')}</h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
            {t('prompts.subtitle')}
          </p>
        </div>

        <div className="w-full sm:w-auto">
          <Button
            onClick={handleSave}
            disabled={!hasChanges || saving}
            loading={saving}
            className="w-full sm:w-auto h-10 px-5 text-sm font-medium rounded-full justify-center"
            title={hasChanges ? t('prompts.savedTitle') : t('prompts.noChangesTitle')}
          >
            {saved ? (
              <span className="flex items-center gap-1.5">
                <Check className="h-4 w-4" />
                <span>{t('common.saved')}</span>
              </span>
            ) : (
              <span>{t('prompts.save')}</span>
            )}
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-16 text-muted-foreground text-xs">
          {t('prompts.loading')}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-1 rounded-3xl bg-card p-3 space-y-1.5 h-fit border-0">
            <div className="text-[11px] font-semibold text-muted-foreground uppercase px-3 py-2 tracking-wider">
              {t('prompts.systemTemplates')}
            </div>
            {Object.keys(promptNames).map((k) => {
              const info = promptNames[k]
              const active = activePromptKey === k
              return (
                <button
                  key={k}
                  onClick={() => setActivePromptKey(k)}
                  className={`w-full flex flex-col p-3 rounded-lg text-xs transition-all text-left border-0 cursor-pointer ${
                    active
                      ? 'bg-foreground text-background font-medium shadow-xs'
                      : 'text-foreground hover:bg-secondary/70'
                  }`}
                >
                  <span className="truncate font-medium">{info.label}</span>
                  <span
                    className={`text-[11px] line-clamp-1 mt-0.5 ${
                      active ? 'text-background/80' : 'text-muted-foreground'
                    }`}
                  >
                    {info.desc}
                  </span>
                </button>
              )
            })}
          </div>

          <div className="lg:col-span-3 space-y-4">
            <Card>
              <CardHeader className="space-y-4 pb-3">
                {/* Row 1: Full-width Title & Description */}
                <div className="text-left space-y-1">
                  <CardTitle className="text-base sm:text-lg">
                    {promptNames[activePromptKey]?.label}
                  </CardTitle>
                  <CardDescription>
                    {promptNames[activePromptKey]?.desc}
                  </CardDescription>
                </div>

                {/* Row 2: Animated Mode Switch + Variables Bar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1 border-t border-muted/20">
                  {/* Fluid Animated Sliding Pill */}
                  <div className="relative inline-flex p-1 rounded-full bg-secondary text-xs font-medium w-full sm:w-auto shrink-0">
                    <div
                      className={`absolute top-1 bottom-1 rounded-full bg-foreground transition-all duration-250 ease-out shadow-xs ${
                        viewMode === 'preview'
                          ? 'left-1 w-[calc(50%-4px)] sm:w-[96px]'
                          : 'left-[calc(50%+2px)] sm:left-[102px] w-[calc(50%-4px)] sm:w-[96px]'
                      }`}
                    />
                    <button
                      type="button"
                      onClick={() => setViewMode('preview')}
                      className={`relative z-10 flex-1 sm:w-[96px] flex items-center justify-center gap-1.5 h-8 rounded-full transition-colors border-0 cursor-pointer ${
                        viewMode === 'preview'
                          ? 'text-background font-medium'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      <Eye className="h-3.5 w-3.5" />
                      <span>{t('common.preview')}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setViewMode('edit')}
                      className={`relative z-10 flex-1 sm:w-[96px] flex items-center justify-center gap-1.5 h-8 rounded-full transition-colors border-0 cursor-pointer ${
                        viewMode === 'edit'
                          ? 'text-background font-medium'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      <Code className="h-3.5 w-3.5" />
                      <span>{t('common.editRaw')}</span>
                    </button>
                  </div>

                  {/* Variables Badges */}
                  {promptNames[activePromptKey]?.vars.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-[11px] text-muted-foreground flex items-center gap-1 mr-0.5">
                        <Variable className="h-3 w-3" />
                        <span>{t('prompts.vars')}</span>
                      </span>
                      {promptNames[activePromptKey].vars.map((v) => {
                        const meta = KNOWN_VARIABLES[v]
                        return (
                          <span
                            key={v}
                            className={`font-mono text-[11px] px-2 py-0.5 rounded-lg font-medium ${
                              meta ? meta.badge : 'bg-secondary text-foreground/80 border border-border/40'
                            }`}
                          >
                            {v.replace(/^\{|\}$/g, "")}
                          </span>
                        )
                      })}
                    </div>
                  )}
                </div>
              </CardHeader>

              <CardContent>
                {viewMode === 'preview' ? (
                  renderHighlightedMarkdown(prompts[activePromptKey] || '')
                ) : (
                  <div className="space-y-3">
                    <div className="rounded-3xl bg-secondary/30 p-4">
                      <textarea
                        value={prompts[activePromptKey] || ''}
                        onChange={(e) => handlePromptChange(e.target.value)}
                        className="w-full font-mono text-xs min-h-[460px] leading-relaxed border-0 bg-transparent focus:outline-none select-text text-foreground resize-y custom-scrollbar"
                        placeholder={t('prompts.writePrompt')}
                      />
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-muted-foreground px-2">
                      <span>{t('prompts.supportedVars')}</span>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={loadPrompts}
                        disabled={!hasChanges}
                        className="h-8 text-xs px-3 rounded-full"
                      >
                        <RotateCcw className="h-3.5 w-3.5 mr-1" />
                        <span>{t('prompts.discard')}</span>
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}
