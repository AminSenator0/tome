import React, { useState, useEffect } from 'react'
import { Shield, Cpu, Type, Languages, Eye, EyeOff } from 'lucide-react'
import { Api } from '../api'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { Checkbox } from '../components/ui/Checkbox'
import { useI18n } from '../lib/i18n'

const PROVIDER_PRESETS: Record<string, { label: string; baseUrl: string; defaultModel: string }> = {
  avalai: {
    labelKey: 'settings.providerAvalai',
    baseUrl: 'https://api.avalai.ir/v1',
    defaultModel: 'qwen3.8-flash',
  },
  openai: {
    labelKey: 'settings.providerOpenai',
    baseUrl: 'https://api.openai.com/v1',
    defaultModel: 'gpt-5.6-luna',
  },
  deepseek: {
    labelKey: 'settings.providerDeepseek',
    baseUrl: 'https://api.deepseek.com/v1',
    defaultModel: 'deepseek-v4-flash',
  },
  anthropic: {
    labelKey: 'settings.providerAnthropic',
    baseUrl: 'https://api.anthropic.com/v1',
    defaultModel: 'claude-sonnet-5',
  },
  gemini: {
    labelKey: 'settings.providerGemini',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai',
    defaultModel: 'gemini-flash-latest',
  },
  groq: {
    labelKey: 'settings.providerGroq',
    baseUrl: 'https://api.groq.com/openai/v1',
    defaultModel: 'llama-3.3-70b-versatile',
  },
  openrouter: {
    labelKey: 'settings.providerOpenrouter',
    baseUrl: 'https://openrouter.ai/api/v1',
    defaultModel: 'deepseek/deepseek-chat',
  },
  ollama: {
    labelKey: 'settings.providerOllama',
    baseUrl: 'http://localhost:11434/v1',
    defaultModel: 'qwen2.5:14b',
  },
}

const AVAILABLE_MODELS = [
  { value: 'qwen3.8-flash', labelKey: 'settings.mdl.qwen3_8_flash_Alibaba_Default', },
  { value: 'gemini-flash-latest', labelKey: 'settings.mdl.gemini_flash_latest_Google', },
  { value: 'glm-5.3-flash', labelKey: 'settings.mdl.glm_5_3_flash_ZAI_Zhipu', },
  { value: 'deepseek-v4-flash', labelKey: 'settings.mdl.deepseek_v4_flash_DeepSeek', },
  { value: 'deepseek-v4-pro', labelKey: 'settings.mdl.deepseek_v4_pro_DeepSeek', },
  { value: 'claude-sonnet-5', labelKey: 'settings.mdl.claude_sonnet_5_Anthropic', },
  { value: 'gpt-5.6-luna', labelKey: 'settings.mdl.gpt_5_6_luna_OpenAI', },
  { value: 'custom', labelKey: 'settings.mdl.Custom_Model_Specify_name', },
]

const GLINER_MODELS = [
  { value: 'urchade/gliner_medium-v2.1', labelKey: 'settings.mdl.urchade_gliner_medium_v2_1_Medium_Default', },
  { value: 'urchade/gliner_small-v2.1', labelKey: 'settings.mdl.urchade_gliner_small_v2_1_Small_Fast', },
  { value: 'urchade/gliner_large-v2.1', labelKey: 'settings.mdl.urchade_gliner_large_v2_1_Large_High_Accuracy', },
  { value: 'urchade/gliner_multi-v2.1', labelKey: 'settings.mdl.urchade_gliner_multi_v2_1_Multilingual', },
  { value: 'custom', labelKey: 'settings.mdl.Custom_Model_Specify_identifier', },
]

export const SettingsView: React.FC = () => {
  const { t } = useI18n()
  const [config, setConfig] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState('avalai')
  const [showApiKey, setShowApiKey] = useState(false)
  const [isCustomModel, setIsCustomModel] = useState(false)
  const [isCustomGliner, setIsCustomGliner] = useState(false)

  const loadConfig = async () => {
    setLoading(true)
    try {
      const data = await Api.getConfig()
      setConfig(data)

      const baseUrl = data.llm?.base_url || ''
      let matchedProvider = 'custom'
      for (const [pKey, pVal] of Object.entries(PROVIDER_PRESETS)) {
        if (pVal.baseUrl && baseUrl.startsWith(pVal.baseUrl)) {
          matchedProvider = pKey
          break
        }
      }
      setSelectedProvider(matchedProvider)

      const currentModel = data.llm?.model || 'qwen3.8-flash'
      const isKnown = AVAILABLE_MODELS.some((m) => m.value === currentModel && m.value !== 'custom')
      setIsCustomModel(!isKnown)

      const currentGliner = data.nlp?.gliner?.model || 'urchade/gliner_medium-v2.1'
      const isKnownGliner = GLINER_MODELS.some((m) => m.value === currentGliner && m.value !== 'custom')
      setIsCustomGliner(!isKnownGliner)
    } catch (err: any) {
      alert(err.message || t('settings.loadFail'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadConfig()
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await Api.updateConfig(config)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err: any) {
      alert(err.message || t('settings.saveFail'))
    } finally {
      setSaving(false)
    }
  }

  const updateSection = (section: string, field: string, value: any) => {
    setConfig((prev) => ({
      ...prev,
      [section]: {
        ...(prev[section] || {}),
        [field]: value,
      },
    }))
  }

  const updateNestedSection = (section: string, subSection: string, field: string, value: any) => {
    setConfig((prev) => ({
      ...prev,
      [section]: {
        ...(prev[section] || {}),
        [subSection]: {
          ...((prev[section] && prev[section][subSection]) || {}),
          [field]: value,
        },
      },
    }))
  }

  const handleProviderChange = (provKey: string) => {
    setSelectedProvider(provKey)
    const preset = PROVIDER_PRESETS[provKey]
    if (preset && preset.baseUrl) {
      updateSection('llm', 'base_url', preset.baseUrl)
      if (preset.defaultModel) {
        updateSection('llm', 'model', preset.defaultModel)
        setIsCustomModel(false)
      }
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-16 text-muted-foreground">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent mb-2" />
        <span className="text-xs">{t('settings.loading')}</span>
      </div>
    )
  }

  const llm = config.llm || {}
  const proxy = config.proxy || {}
  const nlp = config.nlp || {}
  const gliner = nlp.gliner || {}
  const typography = config.typography || {}

  const currentModel = llm.model || 'qwen3.8-flash'
  const currentGlinerModel = gliner.model || 'urchade/gliner_medium-v2.1'

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-foreground">{t('nav.settings')}</h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
            {t('settings.subtitle')}
          </p>
        </div>
        <Button onClick={handleSave} loading={saving} size="lg">
          <span>{saved ? t('settings.savedMsg') : t('settings.save')}</span>
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2.5">
              <Cpu className="h-5 w-5 text-primary" strokeWidth={1.5} />
              <CardTitle>{t('settings.llmTitle')}</CardTitle>
            </div>
            <CardDescription>{t('settings.llmDesc')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Select
              label={t('settings.provider')}
              value={selectedProvider}
              onChange={(e) => handleProviderChange(e.target.value)}
            >
              {Object.entries(PROVIDER_PRESETS).map(([k, v]) => (
                <option key={k} value={k}>
                  {t(v.labelKey)}
                </option>
              ))}
            </Select>

            <Input
              label={t('settings.baseUrl')}
              value={llm.base_url || ''}
              onChange={(e) => updateSection('llm', 'base_url', e.target.value)}
              placeholder="https://api.avalai.ir/v1"
            />

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground px-1">{t('settings.apiKey')}</label>
              <div className="relative">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={llm.api_key || ''}
                  onChange={(e) => updateSection('llm', 'api_key', e.target.value)}
                  placeholder="aa-..."
                  className="flex h-11 w-full rounded-2xl border-0 bg-secondary px-4 pr-11 py-2 text-sm text-foreground transition-all placeholder:text-muted-foreground/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-muted-foreground hover:text-foreground cursor-pointer"
                >
                  {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <Select
              label={t('settings.defaultModel')}
              value={isCustomModel ? 'custom' : currentModel}
              onChange={(e) => {
                if (e.target.value === 'custom') {
                  setIsCustomModel(true)
                  updateSection('llm', 'model', '')
                } else {
                  setIsCustomModel(false)
                  updateSection('llm', 'model', e.target.value)
                }
              }}
            >
              {AVAILABLE_MODELS.map((m) => (
                <option key={m.value} value={m.value}>
                  {t(m.labelKey)}
                </option>
              ))}
            </Select>

            {isCustomModel && (
              <Input
                label={t('settings.customModelName')}
                value={currentModel}
                onChange={(e) => updateSection('llm', 'model', e.target.value)}
                placeholder="e.g. meta-llama/llama-3.3-70b-instruct"
              />
            )}

            <div className="grid grid-cols-2 gap-3 pt-1">
              <Input
                label={t('settings.timeout')}
                type="number"
                value={llm.timeout ?? 300}
                onChange={(e) => updateSection('llm', 'timeout', parseInt(e.target.value, 10))}
              />
              <Input
                label={t('settings.maxTokens')}
                type="number"
                value={llm.max_tokens ?? 16384}
                onChange={(e) => updateSection('llm', 'max_tokens', parseInt(e.target.value, 10))}
              />
            </div>

            <div className="flex flex-col gap-3 pt-2">
              <Checkbox
                checked={llm.stream_response ?? true}
                onChange={(e) => updateSection('llm', 'stream_response', e.target.checked)}
                label={t('settings.streamResponses')}
                title={t('settings.streamTitle')}
              />
              <Checkbox
                checked={llm.thinking ?? true}
                onChange={(e) => updateSection('llm', 'thinking', e.target.checked)}
                label={t('settings.extendedReasoning')}
                title={t('settings.reasoningTitle')}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2.5">
              <Shield className="h-5 w-5 text-primary" strokeWidth={1.5} />
              <CardTitle>{t('settings.proxyTitle')}</CardTitle>
            </div>
            <CardDescription>{t('settings.proxyDesc')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Checkbox
              checked={proxy.enabled ?? false}
              onChange={(e) => updateSection('proxy', 'enabled', e.target.checked)}
              label={t('settings.proxyRouting')}
            />
            <Select
              label={t('settings.proxyProtocol')}
              value={proxy.type || 'socks5'}
              onChange={(e) => updateSection('proxy', 'type', e.target.value)}
            >
              <option value="socks5">SOCKS5</option>
              <option value="http">HTTP</option>
              <option value="https">HTTPS</option>
            </Select>
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <Input
                  label={t('settings.proxyHost')}
                  value={proxy.host || '127.0.0.1'}
                  onChange={(e) => updateSection('proxy', 'host', e.target.value)}
                />
              </div>
              <div>
                <Input
                  label={t('settings.port')}
                  type="number"
                  value={proxy.port ?? 10808}
                  onChange={(e) => updateSection('proxy', 'port', parseInt(e.target.value, 10))}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2.5">
              <Languages className="h-5 w-5 text-primary" strokeWidth={1.5} />
              <CardTitle>{t('settings.nlpTitle')}</CardTitle>
            </div>
            <CardDescription>{t('settings.nlpDesc')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-col gap-3.5">
              <Checkbox
                checked={nlp.refine_metadata ?? true}
                onChange={(e) => updateSection('nlp', 'refine_metadata', e.target.checked)}
                label={t('settings.metadataRefinement')}
                title={t('settings.metadataTitle')}
              />
              <Checkbox
                checked={nlp.persian_nlp ?? true}
                onChange={(e) => updateSection('nlp', 'persian_nlp', e.target.checked)}
                label={t('settings.nlpCopyediting')}
                title={t('settings.nlpCopyeditingTitle')}
              />
              <Checkbox
                checked={nlp.fast_mode ?? false}
                onChange={(e) => updateSection('nlp', 'fast_mode', e.target.checked)}
                label={t('settings.fastMode')}
                title={t('settings.fastModeTitle')}
              />
            </div>

            <div className="pt-2 border-t border-muted/30 space-y-3">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block">
{t('settings.glinerSection')}
              </span>
              <Checkbox
                checked={gliner.enabled ?? true}
                onChange={(e) => updateNestedSection('nlp', 'gliner', 'enabled', e.target.checked)}
                label={t('settings.entityExtraction')}
                title={t('settings.entityTitle')}
              />

              <Select
                label={t('settings.glinerPreset')}
                value={isCustomGliner ? 'custom' : currentGlinerModel}
                onChange={(e) => {
                  if (e.target.value === 'custom') {
                    setIsCustomGliner(true)
                    updateNestedSection('nlp', 'gliner', 'model', '')
                  } else {
                    setIsCustomGliner(false)
                    updateNestedSection('nlp', 'gliner', 'model', e.target.value)
                  }
                }}
              >
                {GLINER_MODELS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {t(m.labelKey)}
                  </option>
                ))}
              </Select>

              {isCustomGliner && (
                <Input
                  label={t('settings.customGliner')}
                  value={currentGlinerModel}
                  onChange={(e) => updateNestedSection('nlp', 'gliner', 'model', e.target.value)}
                  placeholder="e.g. urchade/gliner_large-v2.1"
                />
              )}

              <div className="grid grid-cols-2 gap-3">
                <Input
                  label={t('settings.batchSize')}
                  type="number"
                  value={gliner.batch_size ?? 16}
                  onChange={(e) => updateNestedSection('nlp', 'gliner', 'batch_size', parseInt(e.target.value, 10))}
                />
                <Input
                  label={t('settings.chunkSize')}
                  type="number"
                  value={gliner.chunk_size_words ?? 280}
                  onChange={(e) => updateNestedSection('nlp', 'gliner', 'chunk_size_words', parseInt(e.target.value, 10))}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2.5">
              <Type className="h-5 w-5 text-primary" strokeWidth={1.5} />
              <CardTitle>{t('settings.typoTitle')}</CardTitle>
            </div>
            <CardDescription>{t('settings.typoDesc')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Checkbox
              checked={typography.compile_docx ?? true}
              onChange={(e) => updateSection('typography', 'compile_docx', e.target.checked)}
              label={t('settings.autoCompileDocx')}
            />
            <div className="grid grid-cols-2 gap-3">
              <Select
                label={t('settings.easternFont')}
                value={typography.eastern_font || 'B Nazanin'}
                onChange={(e) => updateSection('typography', 'eastern_font', e.target.value)}
              >
                <option value="B Nazanin">B Nazanin (B-Nazanin.ttf)</option>
                <option value="Vazirmatn">Vazirmatn (Vazirmatn.ttf)</option>
              </Select>

              <Select
                label={t('settings.westernFont')}
                value={typography.western_font || 'Times New Roman'}
                onChange={(e) => updateSection('typography', 'western_font', e.target.value)}
              >
                <option value="Times New Roman">Times New Roman (Times.ttf)</option>
                <option value="Vactory Sans">Vactory Sans (VactorySans.ttf)</option>
                <option value="Bileha">Bileha (Bileha.otf)</option>
                <option value="OVSoge">OVSoge (OVSoge.otf)</option>
              </Select>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <Input
                label={t('settings.lineSpacing')}
                value={typography.line_spacing || '1.35x'}
                onChange={(e) => updateSection('typography', 'line_spacing', e.target.value)}
                onBlur={(e) => {
                  let v = e.target.value.trim().toLowerCase()
                  if (v && !v.endsWith('x')) v = `${v}x`
                  updateSection('typography', 'line_spacing', v || '1.35x')
                }}
              />
              <Input
                label={t('settings.indent')}
                value={typography.paragraph_indent || '0.4cm'}
                onChange={(e) => updateSection('typography', 'paragraph_indent', e.target.value)}
                onBlur={(e) => {
                  let v = e.target.value.trim().toLowerCase()
                  if (v && !v.endsWith('cm') && !v.endsWith('in') && !v.endsWith('pt')) v = `${v}cm`
                  updateSection('typography', 'paragraph_indent', v || '0.4cm')
                }}
              />
              <Input
                label={t('settings.margin')}
                type="number"
                step="0.1"
                value={typography.margin_cm ?? 2.5}
                onChange={(e) => updateSection('typography', 'margin_cm', parseFloat(e.target.value))}
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
