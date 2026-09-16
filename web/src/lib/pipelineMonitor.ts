import { Api, PipelineStatusResponse } from '../api'

export type PipelineStatus = 'idle' | 'running' | 'cancelling' | 'completed' | 'failed' | 'cancelled'

export interface MonitorState {
  taskId: string | null
  status: PipelineStatus
  logs: string[]
  bookFolder: string | null
}

const STORAGE_KEY = 'tome_active_pipeline_task'
const MAX_LOG_LINES = 3000

type Listener = (state: MonitorState) => void

let state: MonitorState = { taskId: null, status: 'idle', logs: [], bookFolder: null }
const listeners = new Set<Listener>()
let eventSource: EventSource | null = null
let lastTs = 0

function persist() {
  if (typeof window === 'undefined') return
  if (state.taskId && (state.status === 'running' || state.status === 'cancelling')) {
    window.localStorage.setItem(STORAGE_KEY, state.taskId)
  } else {
    window.localStorage.removeItem(STORAGE_KEY)
  }
}

function emit() {
  const snapshot: MonitorState = { ...state, logs: [...state.logs] }
  listeners.forEach((l) => l(snapshot))
}

export function getMonitorState(): MonitorState {
  return { ...state, logs: [...state.logs] }
}

export function subscribePipeline(listener: Listener): () => void {
  listeners.add(listener)
  listener(getMonitorState())
  if (!eventSource && typeof window !== 'undefined' && !state.taskId) {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (saved) attach(saved)
  }
  return () => {
    listeners.delete(listener)
  }
}

export function appendMonitorLog(line: string, ts?: number) {
  if (ts !== undefined) {
    if (ts <= lastTs) return
    lastTs = ts
  }
  if (!line) return
  state.logs.push(line)
  if (state.logs.length > MAX_LOG_LINES) state.logs = state.logs.slice(-MAX_LOG_LINES)
  emit()
}

function formatLine(payload: any): string {
  const evt = payload.event
  const data = payload.data || {}
  switch (evt) {
    case 'stage_start':
      return `▸ [STAGE] Starting ${String(data.stage || '').replace(/_/g, ' ').toUpperCase()}...`
    case 'conversion_complete':
      return `✓ [CONVERSION] Loaded ${data.page_count || 1} pages in ${data.duration || 0}s`
    case 'images_extracted':
      return `✓ [IMAGES] Extracted ${data.image_count || 0} illustrations in ${data.duration || 0}s`
    case 'genre_detected':
      return `ℹ [GENRE] Detected: ${data.genre}`
    case 'metadata_extracted':
      return `ℹ [METADATA] ${data.title || 'Extracted metadata'}`
    case 'chapterization_complete':
      return `✓ [CHAPTERS] Found ${data.chapter_count || 0} chapters in ${data.duration || 0}s`
    case 'extraction_complete':
      return `✓ [ENTITIES] Extracted ${data.entity_count || 0} entities in ${data.duration || 0}s`
    case 'glossary_translation_complete':
      return '✓ [GLOSSARY] Bilingual entity glossary compiled'
    case 'graph_built':
      return '✓ [GRAPH] Character relationship graph constructed'
    case 'chapter_translation_complete':
      return `✓ [TRANSLATED] Chapter ${data.chapter} in ${data.duration || 0}s`
    case 'translation_attempt':
      return (data.attempt || 1) > 1
        ? `▸ [ATTEMPT ${data.attempt}/${data.max_attempts || 3}] ${data.chapter || ''}`
        : ''
    case 'warning':
      return `⚠ [WARN] ${data.warning || JSON.stringify(data)}`
    case 'error':
      return `✖ [ERROR] ${data.error || JSON.stringify(data)}`
    case 'pipeline_complete':
      return '★ [COMPLETED] Pipeline execution completed successfully!'
    case 'pipeline_cancelled':
      return `■ [CANCELLED] ${data.message || 'Pipeline cancelled by user'}`
    case 'cancelling':
      return `▸ [CANCEL] ${data.message || 'Cancellation requested'}`
    default:
      if (data.log) return String(data.log)
      if (typeof data === 'string') return data
      return ''
  }
}

function applyServerLogs(res: PipelineStatusResponse) {
  const lines: string[] = []
  for (const item of res.logs || []) {
    if (item.timestamp && item.timestamp > lastTs) lastTs = item.timestamp
    const line = formatLine(item)
    if (line) lines.push(line)
  }
  state.logs = lines
  if (state.logs.length > MAX_LOG_LINES) state.logs = state.logs.slice(-MAX_LOG_LINES)
}

function setStatus(s: PipelineStatus, bookFolder?: string | null) {
  state.status = s
  if (bookFolder) state.bookFolder = bookFolder
  persist()
  emit()
}

function syncTerminalStatus(st: string) {
  if (st === 'completed') setStatus('completed', state.bookFolder)
  else if (st === 'failed') setStatus('failed')
  else if (st === 'cancelled') setStatus('cancelled')
  else if (st === 'running' || st === 'cancelling') setStatus(st)
}

function detach() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

async function verifyFailure(taskId: string, streamClosed = false) {
  try {
    const res = await Api.getPipelineStatus(taskId)
    const st = res.status
    if (st === 'failed' || st === 'completed' || st === 'cancelled') {
      if (res.book_folder) state.bookFolder = res.book_folder
      syncTerminalStatus(st)
      detach()
    } else if (streamClosed) {
      attach(taskId)
    }
  } catch {
    if (streamClosed) {
      setStatus('failed')
      detach()
    }
  }
}

function resync(taskId: string) {
  Api.getPipelineStatus(taskId)
    .then((res) => {
      if (res && Array.isArray(res.logs)) {
        applyServerLogs(res)
        if (res.book_folder) state.bookFolder = res.book_folder
        syncTerminalStatus(res.status)
        emit()
      }
    })
    .catch(() => {})
}

function attach(taskId: string) {
  detach()
  state.taskId = taskId
  persist()
  emit()
  resync(taskId)
  eventSource = new EventSource(`/api/pipeline/events/${taskId}`)
  eventSource.onopen = () => resync(taskId)
  eventSource.onmessage = (e) => {
    try {
      const payload = JSON.parse(e.data)
      const line = formatLine(payload)
      if (line) appendMonitorLog(line, payload.timestamp)
      const evt = payload.event
      const data = payload.data || {}
      if (evt === 'pipeline_complete' || data.status === 'completed') {
        setStatus('completed', data.book_folder || state.bookFolder)
        detach()
      } else if (evt === 'pipeline_cancelled') {
        setStatus('cancelled')
        detach()
      } else if (evt === 'error') {
        verifyFailure(taskId)
      }
    } catch {
      appendMonitorLog(e.data)
    }
  }
  eventSource.onerror = () => {
    verifyFailure(taskId, true)
  }
}

export function startPipelineMonitor(taskId: string) {
  lastTs = 0
  state = { taskId, status: 'running', logs: [], bookFolder: null }
  persist()
  appendMonitorLog('Pipeline initialized. Starting execution harness...')
  attach(taskId)
}

export async function cancelPipelineTask(taskId: string): Promise<void> {
  try {
    await Api.cancelPipeline(taskId)
    setStatus('cancelling')
    appendMonitorLog('▸ [CANCEL] Cancellation requested by user...')
  } catch (err: any) {
    appendMonitorLog(`✖ [ERROR] Cancel failed: ${err?.message || err}`)
  }
}

if (typeof window !== 'undefined' && Api.getToken()) {
  const saved = window.localStorage.getItem(STORAGE_KEY)
  if (saved) attach(saved)
}
