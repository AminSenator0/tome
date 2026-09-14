import React, { useState, useEffect } from 'react'
import { Shield, Cpu, Type, Languages, Eye, EyeOff } from 'lucide-react'
import { Api } from '../api'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { Checkbox } from '../components/ui/Checkbox'

const PROVIDER_PRESETS: Record<string, { label: string; baseUrl: string; defaultModel: string }> = {
  avalai: {
    label: 'AvalAI (Iran Route)',
    baseUrl: 'https://api.avalai.ir/v1',
    defaultModel: 'qwen3.8-flash',
  },
  openai: {
    label: 'OpenAI Direct',
    baseUrl: 'https://api.openai.com/v1',
    defaultModel: 'gpt-5.6-luna',
  },
  deepseek: {
    label: 'DeepSeek Direct',
    baseUrl: 'https://api.deepseek.com/v1',
    defaultModel: 'deepseek-v4-flash',
  },
  anthropic: {
    label: 'Anthropic Direct',
    baseUrl: 'https://api.anthropic.com/v1',
    defaultModel: 'claude-sonnet-5',
  },
  gemini: {
    label: 'Google Gemini',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai',
    defaultModel: 'gemini-flash-latest',
  },
  groq: {
    label: 'Groq Cloud',
    baseUrl: 'https://api.groq.com/openai/v1',
    defaultModel: 'llama-3.3-70b-versatile',
  },
  openrouter: {
    label: 'OpenRouter',
    baseUrl: 'https://openrouter.ai/api/v1',
    defaultModel: 'deepseek/deepseek-chat',
  },
  ollama: {
    label: 'Ollama (Localhost)',
    baseUrl: 'http://localhost:11434/v1',
    defaultModel: 'qwen2.5:14b',
  },
}

const AVAILABLE_MODELS = [
  { value: 'qwen3.8-flash', label: 'qwen3.8-flash (Alibaba) [Default]' },
  { value: 'gemini-flash-latest', label: 'gemini-flash-latest (Google)' },
  { value: 'glm-5.3-flash', label: 'glm-5.3-flash (ZAI / Zhipu)' },
  { value: 'deepseek-v4-flash', label: 'deepseek-v4-flash (DeepSeek)' },
  { value: 'deepseek-v4-pro', label: 'deepseek-v4-pro (DeepSeek)' },
  { value: 'claude-sonnet-5', label: 'claude-sonnet-5 (Anthropic)' },
  { value: 'gpt-5.6-luna', label: 'gpt-5.6-luna (OpenAI)' },
  { value: 'custom', label: 'Custom Model (Specify name)' },
]

const GLINER_MODELS = [
  { value: 'urchade/gliner_medium-v2.1', label: 'urchade/gliner_medium-v2.1 (Medium - Default)' },
  { value: 'urchade/gliner_small-v2.1', label: 'urchade/gliner_small-v2.1 (Small - Fast)' },
  { value: 'urchade/gliner_large-v2.1', label: 'urchade/gliner_large-v2.1 (Large - High Accuracy)' },
  { value: 'urchade/gliner_multi-v2.1', label: 'urchade/gliner_multi-v2.1 (Multilingual)' },
  { value: 'custom', label: 'Custom Model (Specify identifier)' },
]

export const SettingsView: React.FC = () => {
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
      alert(err.message || 'Failed to load configuration')
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
      alert(err.message || 'Failed to save settings')
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
        <span className="text-xs">Loading engine settings...</span>
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
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-foreground">System Configuration</h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
            Full parameters for LLM endpoints, proxy routing, Persian NLP, and document typography
          </p>
        </div>
        <Button onClick={handleSave} loading={saving} size="lg">
          <span>{saved ? 'Saved to tome.json' : 'Save Settings'}</span>
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2.5">
              <Cpu className="h-5 w-5 text-primary" strokeWidth={1.5} />
              <CardTitle>LLM Engine & Inference</CardTitle>
            </div>
            <CardDescription>Configure provider endpoints, API keys, and model parameters</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Select
              label="Provider"
              value={selectedProvider}
              onChange={(e) => handleProviderChange(e.target.value)}
            >
              {Object.entries(PROVIDER_PRESETS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v.label}
                </option>
              ))}
            </Select>

            <Input
              label="Base URL"
              value={llm.base_url || ''}
              onChange={(e) => updateSection('llm', 'base_url', e.target.value)}
              placeholder="https://api.avalai.ir/v1"
            />

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground px-1">API Key</label>
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
              label="Default Model"
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
                  {m.label}
                </option>
              ))}
            </Select>

            {isCustomModel && (
              <Input
                label="Custom Model Name"
                value={currentModel}
                onChange={(e) => updateSection('llm', 'model', e.target.value)}
                placeholder="e.g. meta-llama/llama-3.3-70b-instruct"
              />
            )}

            <div className="grid grid-cols-2 gap-3 pt-1">
              <Input
                label="Timeout (seconds)"
                type="number"
                value={llm.timeout ?? 300}
                onChange={(e) => updateSection('llm', 'timeout', parseInt(e.target.value, 10))}
              />
              <Input
                label="Max Tokens"
                type="number"
                value={llm.max_tokens ?? 16384}
                onChange={(e) => updateSection('llm', 'max_tokens', parseInt(e.target.value, 10))}
              />
            </div>

            <div className="flex flex-col gap-3 pt-2">
              <Checkbox
                checked={llm.stream_response ?? true}
                onChange={(e) => updateSection('llm', 'stream_response', e.target.checked)}
                label="Stream responses"
                title="Stream real-time tokens via SSE during chapter translation"
              />
              <Checkbox
                checked={llm.thinking ?? true}
                onChange={(e) => updateSection('llm', 'thinking', e.target.checked)}
                label="Extended reasoning"
                title="Enable chain-of-thought reasoning tokens from supported models"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2.5">
              <Shield className="h-5 w-5 text-primary" strokeWidth={1.5} />
              <CardTitle>Proxy & Tunneling</CardTitle>
            </div>
            <CardDescription>SOCKS5 / HTTP proxy routing for restricted network environments</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Checkbox
              checked={proxy.enabled ?? false}
              onChange={(e) => updateSection('proxy', 'enabled', e.target.checked)}
              label="Proxy routing"
            />
            <Select
              label="Proxy Protocol"
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
                  label="Proxy Host"
                  value={proxy.host || '127.0.0.1'}
                  onChange={(e) => updateSection('proxy', 'host', e.target.value)}
                />
              </div>
              <div>
                <Input
                  label="Port"
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
              <CardTitle>NLP & Linguistic Normalization</CardTitle>
            </div>
            <CardDescription>Persian orthographic copyediting and entity extraction settings</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-col gap-3.5">
              <Checkbox
                checked={nlp.refine_metadata ?? true}
                onChange={(e) => updateSection('nlp', 'refine_metadata', e.target.checked)}
                label="Metadata Refinement (LLM)"
                title="Use LLM to refine bibliographic synopsis, genre, and keywords"
              />
              <Checkbox
                checked={nlp.persian_nlp ?? true}
                onChange={(e) => updateSection('nlp', 'persian_nlp', e.target.checked)}
                label="NLP copyediting"
                title="Apply Persian orthographic normalizer and ZWNJ correction"
              />
              <Checkbox
                checked={nlp.fast_mode ?? false}
                onChange={(e) => updateSection('nlp', 'fast_mode', e.target.checked)}
                label="Fast mode"
                title="Skip heavy character clustering for faster execution"
              />
            </div>

            <div className="pt-2 border-t border-muted/30 space-y-3">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block">
                Entity Extractor (GLiNER)
              </span>
              <Checkbox
                checked={gliner.enabled ?? true}
                onChange={(e) => updateNestedSection('nlp', 'gliner', 'enabled', e.target.checked)}
                label="Entity extraction"
                title="Extract named entities, characters, and places using local entity model"
              />

              <Select
                label="GLiNER Model Preset"
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
                    {m.label}
                  </option>
                ))}
              </Select>

              {isCustomGliner && (
                <Input
                  label="Custom GLiNER Model Identifier"
                  value={currentGlinerModel}
                  onChange={(e) => updateNestedSection('nlp', 'gliner', 'model', e.target.value)}
                  placeholder="e.g. urchade/gliner_large-v2.1"
                />
              )}

              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="Batch Size"
                  type="number"
                  value={gliner.batch_size ?? 16}
                  onChange={(e) => updateNestedSection('nlp', 'gliner', 'batch_size', parseInt(e.target.value, 10))}
                />
                <Input
                  label="Chunk Size (words)"
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
              <CardTitle>Typography & Publication Layout</CardTitle>
            </div>
            <CardDescription>Fonts from fonts/ directory, spacing, and layout configurations</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Checkbox
              checked={typography.compile_docx ?? true}
              onChange={(e) => updateSection('typography', 'compile_docx', e.target.checked)}
              label="Auto-compile DOCX"
            />
            <div className="grid grid-cols-2 gap-3">
              <Select
                label="Eastern / Persian Font"
                value={typography.eastern_font || 'B Nazanin'}
                onChange={(e) => updateSection('typography', 'eastern_font', e.target.value)}
              >
                <option value="B Nazanin">B Nazanin (B-Nazanin.ttf)</option>
                <option value="Vazirmatn">Vazirmatn (Vazirmatn.ttf)</option>
              </Select>

              <Select
                label="Western / Latin Font"
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
                label="Line Spacing"
                value={typography.line_spacing || '1.35x'}
                onChange={(e) => updateSection('typography', 'line_spacing', e.target.value)}
                onBlur={(e) => {
                  let v = e.target.value.trim().toLowerCase()
                  if (v && !v.endsWith('x')) v = `${v}x`
                  updateSection('typography', 'line_spacing', v || '1.35x')
                }}
              />
              <Input
                label="Indent"
                value={typography.paragraph_indent || '0.4cm'}
                onChange={(e) => updateSection('typography', 'paragraph_indent', e.target.value)}
                onBlur={(e) => {
                  let v = e.target.value.trim().toLowerCase()
                  if (v && !v.endsWith('cm') && !v.endsWith('in') && !v.endsWith('pt')) v = `${v}cm`
                  updateSection('typography', 'paragraph_indent', v || '0.4cm')
                }}
              />
              <Input
                label="Margin (cm)"
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
