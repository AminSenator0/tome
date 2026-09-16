#!/usr/bin/env python3
"""
Tome Phase 2 — resilient Pipeline Studio frontend.

Creates web/src/lib/pipelineMonitor.ts (module-level SSE singleton that survives
tab switches and page reloads) and patches api.ts + PipelineView.tsx.

Usage:  python tome_phase2.py            (dry-run)
        python tome_phase2.py --apply
"""

import argparse
import re
import sys
from pathlib import Path

MONITOR_TS = "import { Api, PipelineStatusResponse } from '../api'\n\nexport type PipelineStatus = 'idle' | 'running' | 'cancelling' | 'completed' | 'failed' | 'cancelled'\n\nexport interface MonitorState {\n  taskId: string | null\n  status: PipelineStatus\n  logs: string[]\n  bookFolder: string | null\n}\n\nconst STORAGE_KEY = 'tome_active_pipeline_task'\nconst MAX_LOG_LINES = 3000\n\ntype Listener = (state: MonitorState) => void\n\nlet state: MonitorState = { taskId: null, status: 'idle', logs: [], bookFolder: null }\nconst listeners = new Set<Listener>()\nlet eventSource: EventSource | null = null\nlet lastTs = 0\n\nfunction persist() {\n  if (typeof window === 'undefined') return\n  if (state.taskId && (state.status === 'running' || state.status === 'cancelling')) {\n    window.localStorage.setItem(STORAGE_KEY, state.taskId)\n  } else {\n    window.localStorage.removeItem(STORAGE_KEY)\n  }\n}\n\nfunction emit() {\n  const snapshot: MonitorState = { ...state, logs: [...state.logs] }\n  listeners.forEach((l) => l(snapshot))\n}\n\nexport function getMonitorState(): MonitorState {\n  return { ...state, logs: [...state.logs] }\n}\n\nexport function subscribePipeline(listener: Listener): () => void {\n  listeners.add(listener)\n  listener(getMonitorState())\n  if (!eventSource && typeof window !== 'undefined' && !state.taskId) {\n    const saved = window.localStorage.getItem(STORAGE_KEY)\n    if (saved) attach(saved)\n  }\n  return () => {\n    listeners.delete(listener)\n  }\n}\n\nexport function appendMonitorLog(line: string, ts?: number) {\n  if (ts !== undefined) {\n    if (ts <= lastTs) return\n    lastTs = ts\n  }\n  if (!line) return\n  state.logs.push(line)\n  if (state.logs.length > MAX_LOG_LINES) state.logs = state.logs.slice(-MAX_LOG_LINES)\n  emit()\n}\n\nfunction formatLine(payload: any): string {\n  const evt = payload.event\n  const data = payload.data || {}\n  switch (evt) {\n    case 'stage_start':\n      return `▸ [STAGE] Starting ${String(data.stage || '').replace(/_/g, ' ').toUpperCase()}...`\n    case 'conversion_complete':\n      return `✓ [CONVERSION] Loaded ${data.page_count || 1} pages in ${data.duration || 0}s`\n    case 'images_extracted':\n      return `✓ [IMAGES] Extracted ${data.image_count || 0} illustrations in ${data.duration || 0}s`\n    case 'genre_detected':\n      return `ℹ [GENRE] Detected: ${data.genre}`\n    case 'metadata_extracted':\n      return `ℹ [METADATA] ${data.title || 'Extracted metadata'}`\n    case 'chapterization_complete':\n      return `✓ [CHAPTERS] Found ${data.chapter_count || 0} chapters in ${data.duration || 0}s`\n    case 'extraction_complete':\n      return `✓ [ENTITIES] Extracted ${data.entity_count || 0} entities in ${data.duration || 0}s`\n    case 'glossary_translation_complete':\n      return '✓ [GLOSSARY] Bilingual entity glossary compiled'\n    case 'graph_built':\n      return '✓ [GRAPH] Character relationship graph constructed'\n    case 'chapter_translation_complete':\n      return `✓ [TRANSLATED] Chapter ${data.chapter} in ${data.duration || 0}s`\n    case 'translation_attempt':\n      return (data.attempt || 1) > 1\n        ? `▸ [ATTEMPT ${data.attempt}/${data.max_attempts || 3}] ${data.chapter || ''}`\n        : ''\n    case 'warning':\n      return `⚠ [WARN] ${data.warning || JSON.stringify(data)}`\n    case 'error':\n      return `✖ [ERROR] ${data.error || JSON.stringify(data)}`\n    case 'pipeline_complete':\n      return '★ [COMPLETED] Pipeline execution completed successfully!'\n    case 'pipeline_cancelled':\n      return `■ [CANCELLED] ${data.message || 'Pipeline cancelled by user'}`\n    case 'cancelling':\n      return `▸ [CANCEL] ${data.message || 'Cancellation requested'}`\n    default:\n      if (data.log) return String(data.log)\n      if (typeof data === 'string') return data\n      return ''\n  }\n}\n\nfunction applyServerLogs(res: PipelineStatusResponse) {\n  const lines: string[] = []\n  for (const item of res.logs || []) {\n    if (item.timestamp && item.timestamp > lastTs) lastTs = item.timestamp\n    const line = formatLine(item)\n    if (line) lines.push(line)\n  }\n  state.logs = lines\n  if (state.logs.length > MAX_LOG_LINES) state.logs = state.logs.slice(-MAX_LOG_LINES)\n}\n\nfunction setStatus(s: PipelineStatus, bookFolder?: string | null) {\n  state.status = s\n  if (bookFolder) state.bookFolder = bookFolder\n  persist()\n  emit()\n}\n\nfunction syncTerminalStatus(st: string) {\n  if (st === 'completed') setStatus('completed', state.bookFolder)\n  else if (st === 'failed') setStatus('failed')\n  else if (st === 'cancelled') setStatus('cancelled')\n  else if (st === 'running' || st === 'cancelling') setStatus(st)\n}\n\nfunction detach() {\n  if (eventSource) {\n    eventSource.close()\n    eventSource = null\n  }\n}\n\nasync function verifyFailure(taskId: string, streamClosed = false) {\n  try {\n    const res = await Api.getPipelineStatus(taskId)\n    const st = res.status\n    if (st === 'failed' || st === 'completed' || st === 'cancelled') {\n      if (res.book_folder) state.bookFolder = res.book_folder\n      syncTerminalStatus(st)\n      detach()\n    } else if (streamClosed) {\n      attach(taskId)\n    }\n  } catch {\n    if (streamClosed) {\n      setStatus('failed')\n      detach()\n    }\n  }\n}\n\nfunction resync(taskId: string) {\n  Api.getPipelineStatus(taskId)\n    .then((res) => {\n      if (res && Array.isArray(res.logs)) {\n        applyServerLogs(res)\n        if (res.book_folder) state.bookFolder = res.book_folder\n        syncTerminalStatus(res.status)\n        emit()\n      }\n    })\n    .catch(() => {})\n}\n\nfunction attach(taskId: string) {\n  detach()\n  state.taskId = taskId\n  persist()\n  emit()\n  resync(taskId)\n  eventSource = new EventSource(`/api/pipeline/events/${taskId}`)\n  eventSource.onopen = () => resync(taskId)\n  eventSource.onmessage = (e) => {\n    try {\n      const payload = JSON.parse(e.data)\n      const line = formatLine(payload)\n      if (line) appendMonitorLog(line, payload.timestamp)\n      const evt = payload.event\n      const data = payload.data || {}\n      if (evt === 'pipeline_complete' || data.status === 'completed') {\n        setStatus('completed', data.book_folder || state.bookFolder)\n        detach()\n      } else if (evt === 'pipeline_cancelled') {\n        setStatus('cancelled')\n        detach()\n      } else if (evt === 'error') {\n        verifyFailure(taskId)\n      }\n    } catch {\n      appendMonitorLog(e.data)\n    }\n  }\n  eventSource.onerror = () => {\n    verifyFailure(taskId, true)\n  }\n}\n\nexport function startPipelineMonitor(taskId: string) {\n  lastTs = 0\n  state = { taskId, status: 'running', logs: [], bookFolder: null }\n  persist()\n  appendMonitorLog('Pipeline initialized. Starting execution harness...')\n  attach(taskId)\n}\n\nexport async function cancelPipelineTask(taskId: string): Promise<void> {\n  try {\n    await Api.cancelPipeline(taskId)\n    setStatus('cancelling')\n    appendMonitorLog('▸ [CANCEL] Cancellation requested by user...')\n  } catch (err: any) {\n    appendMonitorLog(`✖ [ERROR] Cancel failed: ${err?.message || err}`)\n  }\n}\n\nif (typeof window !== 'undefined' && Api.getToken()) {\n  const saved = window.localStorage.getItem(STORAGE_KEY)\n  if (saved) attach(saved)\n}\n"


def patch_api_ts(src: str) -> tuple[str, int]:
    n = 0
    iface_anchor = "  has_docx: boolean\n  has_pdf: boolean\n}\n"
    iface = iface_anchor + (
        "\n"
        "export interface PipelineStatusResponse {\n"
        "  task_id: string\n"
        "  status: string\n"
        "  progress: number\n"
        "  current_stage: string\n"
        "  book_folder: string\n"
        "  file_path: string\n"
        "  error: string\n"
        "  logs: Array<{ event: string; data: any; timestamp: number }>\n"
        "}\n"
    )
    if iface_anchor in src and "PipelineStatusResponse" not in src:
        src = src.replace(iface_anchor, iface, 1)
        n += 1
    methods_anchor = "  static async runPipeline(params: {\n"
    methods = (
        "  static async getPipelineStatus(taskId: string): Promise<PipelineStatusResponse> {\n"
        "    return this.request<PipelineStatusResponse>(`/api/pipeline/status/${taskId}`)\n"
        "  }\n"
        "\n"
        "  static async cancelPipeline(taskId: string): Promise<void> {\n"
        "    await this.request(`/api/pipeline/cancel/${taskId}`, { method: 'POST' })\n"
        "  }\n"
        "\n"
    )
    if methods_anchor in src and "cancelPipeline" not in src:
        src = src.replace(methods_anchor, methods + methods_anchor, 1)
        n += 1
    return src, (1 if n == 2 else 0)


def patch_pipeline_view(src: str) -> tuple[str, int]:
    n = 0

    # 1) lucide imports: add Square
    old = "  ArrowRight,\n} from 'lucide-react'\n"
    new = "  ArrowRight,\n  Square,\n} from 'lucide-react'\n"
    if old in src:
        src = src.replace(old, new, 1)
        n += 1

    # 2) monitor import
    old = "import { Api, BookSummary } from '../api'\n"
    new = old + "import {\n  getMonitorState,\n  subscribePipeline,\n  startPipelineMonitor,\n  cancelPipelineTask,\n  appendMonitorLog,\n  MonitorState,\n} from '../lib/pipelineMonitor'\n"
    if old in src and "pipelineMonitor" not in src:
        src = src.replace(old, new, 1)
        n += 1

    # 3) state block -> monitor subscription
    old = (
        "  const [running, setRunning] = useState(false)\n"
        "  const [logs, setLogs] = useState<string[]>([])\n"
        "  const [status, setStatus] = useState<'idle' | 'running' | 'completed' | 'failed'>('idle')\n"
        "  const [completedBookFolder, setCompletedBookFolder] = useState<string | null>(null)\n"
    )
    new = (
        "  const [mon, setMon] = useState<MonitorState>(() => getMonitorState())\n"
        "  const running = mon.status === 'running' || mon.status === 'cancelling'\n"
        "  const logs = mon.logs\n"
        "  const completedBookFolder = mon.bookFolder\n"
        "  const status = mon.status\n"
        "\n"
        "  useEffect(() => subscribePipeline(setMon), [])\n"
        "\n"
        "  useEffect(() => {\n"
        "    const t = setTimeout(() => {\n"
        "      if (terminalRef.current) {\n"
        "        terminalRef.current.scrollTop = terminalRef.current.scrollHeight\n"
        "      }\n"
        "    }, 50)\n"
        "    return () => clearTimeout(t)\n"
        "  }, [mon.logs])\n"
    )
    if old in src:
        src = src.replace(old, new, 1)
        n += 1

    # 4) startPipeline head
    old = (
        "  const startPipeline = async () => {\n"
        "    if (!uploadedPath) return\n"
        "    setRunning(true)\n"
        "    setStatus('running')\n"
        "    setLogs(['Pipeline initialized. Starting execution harness...'])\n"
        "\n"
        "    try {\n"
    )
    new = "  const startPipeline = async () => {\n    if (!uploadedPath) return\n\n    try {\n"
    if old in src:
        src = src.replace(old, new, 1)
        n += 1

    # 5) whole EventSource block -> one monitor call
    pat = re.compile(
        r"      const taskId = res\.task_id\n"
        r"      const eventSource = new EventSource\(`/api/pipeline/events/\$\{taskId\}`\).*?"
        r"      eventSource\.onerror = \(\) => \{\n"
        r"        eventSource\.close\(\)\n"
        r"        setRunning\(false\)\n"
        r"        setStatus\(\(prev\) => \(prev === 'running' \? 'failed' : prev\)\)\n"
        r"      \}\n",
        re.S,
    )
    src, cnt = pat.subn("      startPipelineMonitor(res.task_id)\n", src, count=1)
    if cnt == 1:
        n += 1

    # 6) catch block
    old = (
        "    } catch (err: any) {\n"
        "      setRunning(false)\n"
        "      setStatus('failed')\n"
        "      setLogs((prev) => [...prev, `[ERR] Launch failed: ${err.message}`])\n"
        "    }\n"
    )
    new = "    } catch (err: any) {\n      appendMonitorLog(`[ERR] Launch failed: ${err.message}`)\n    }\n"
    if old in src:
        src = src.replace(old, new, 1)
        n += 1

    # 7) console header: status badge + cancel button
    old = (
        "              <div className=\"flex items-center gap-2.5\">\n"
        "                <Terminal className=\"h-4 w-4 text-primary\" />\n"
        "                <CardTitle className=\"text-base\">Live Execution Console</CardTitle>\n"
        "              </div>\n"
    )
    new = (
        "              <div className=\"flex items-center gap-2.5\">\n"
        "                <Terminal className=\"h-4 w-4 text-primary\" />\n"
        "                <CardTitle className=\"text-base\">Live Execution Console</CardTitle>\n"
        "                {mon.status !== 'idle' && (\n"
        "                  <span\n"
        "                    className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide ${\n"
        "                      mon.status === 'running'\n"
        "                        ? 'bg-primary/15 text-primary'\n"
        "                        : mon.status === 'completed'\n"
        "                          ? 'bg-success-light text-success'\n"
        "                          : 'bg-destructive/15 text-destructive'\n"
        "                    }`}\n"
        "                  >\n"
        "                    {mon.status}\n"
        "                  </span>\n"
        "                )}\n"
        "              </div>\n"
        "              {mon.status === 'running' && mon.taskId && (\n"
        "                <Button\n"
        "                  size=\"sm\"\n"
        "                  className=\"gap-1.5 bg-rose-500/15 text-rose-600 dark:text-rose-400 hover:bg-rose-500/25\"\n"
        "                  onClick={() => {\n"
        "                    if (window.confirm('Cancel this pipeline run? The current chapter will finish, then it stops.')) {\n"
        "                      cancelPipelineTask(mon.taskId as string)\n"
        "                    }\n"
        "                  }}\n"
        "                >\n"
        "                  <Square className=\"h-3.5 w-3.5\" />\n"
        "                  <span>Cancel</span>\n"
        "                </Button>\n"
        "              )\n"
    )
    if old in src:
        src = src.replace(old, new, 1)
        n += 1

    ok = n == 7
    if ok:
        leftovers = ["setLogs", "setRunning(", "setStatus(", "setCompletedBookFolder", "eventSource"]
        for token in leftovers:
            if token in src:
                print(f"  !! post-check failed, leftover token: {token}")
                return src, 0
    return src, (1 if ok else 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--webdir", default="web/src")
    args = ap.parse_args()

    webdir = Path(args.webdir)
    monitor_path = webdir / "lib" / "pipelineMonitor.ts"
    api_path = webdir / "api.ts"
    view_path = webdir / "views" / "PipelineView.tsx"

    for p in (api_path, view_path):
        if not p.is_file():
            sys.exit(f"required file missing: {p}")

    print(f"mode: {'APPLY' if args.apply else 'DRY-RUN'}   webdir: {webdir}")

    # 1) monitor module (write or verify identical)
    existing = monitor_path.read_text(encoding="utf-8") if monitor_path.is_file() else None
    if existing == MONITOR_TS:
        print("  [OK] pipelineMonitor.ts already up to date")
    elif monitor_path.is_file():
        print(f"  [DIFFERS] {monitor_path} exists with different content — refusing to overwrite. Delete it first if intentional.")
        sys.exit(2)
    else:
        if args.apply:
            monitor_path.parent.mkdir(parents=True, exist_ok=True)
            monitor_path.write_text(MONITOR_TS, encoding="utf-8")
            print(f"  [OK] wrote {monitor_path}")
        else:
            print(f"  [would write] {monitor_path}")

    # 2) api.ts
    src = api_path.read_text(encoding="utf-8")
    new, n = patch_api_ts(src)
    if n >= 1:
        status = "OK"
    elif "PipelineStatusResponse" in src:
        status = "already applied"
    else:
        status = "NOT FOUND"
    print(f"  [{status:>16}] api.ts: status/cancel client methods")
    if new != src:
        if args.apply and n >= 1:
            api_path.with_suffix(".ts.bak").write_text(src, encoding="utf-8")
            api_path.write_text(new, encoding="utf-8")
            print("         patched api.ts (backup: api.ts.bak)")
        elif not args.apply:
            print("         (dry-run)")

    # 3) PipelineView.tsx
    src = view_path.read_text(encoding="utf-8")
    new, n = patch_pipeline_view(src)
    if n >= 1:
        status = "OK"
    elif "startPipelineMonitor(res.task_id)" in src:
        status = "already applied"
    else:
        status = "NOT FOUND"
    print(f"  [{status:>16}] PipelineView.tsx: resilient console + cancel button")
    if new != src and n >= 1:
        if args.apply:
            view_path.with_suffix(".tsx.bak").write_text(src, encoding="utf-8")
            view_path.write_text(new, encoding="utf-8")
            print("         patched PipelineView.tsx (backup: PipelineView.tsx.bak)")
        else:
            print("         (dry-run)")

    if args.apply:
        print("\nDone. Rebuild the frontend:  cd web && npm run build")
    else:
        print("\nDry-run only. Re-run with --apply.")


if __name__ == "__main__":
    main()