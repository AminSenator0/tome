#!/usr/bin/env python3
"""
Tome Phase 1 — pipeline control backend:
  P0: fix extract-entities broken GLiNER pre-loading (sync VPS hotfix into repo)
  P1: cancel-event plumbing (threading.Event per task + cancelling observer wrapper)
  P2: GET  /api/pipeline/status/{task_id}
  P3: POST /api/pipeline/cancel/{task_id}
  P4: wire cancellation into _runner (clean "cancelled" state, no fake failure)
  P5: SSE stream ends cleanly on "cancelled" too
  P6: cleanup also drops cancel events

Usage:  python tome_phase1.py            (dry-run)
        python tome_phase1.py --apply
"""

import argparse
import re
import sys
from pathlib import Path


def patch_p0_extract_entities(src: str) -> tuple[str, int]:
    old = (
        "    model_path = ensure_gliner_model(req.model, endpoint=config.hf_mirror_endpoint)\n"
        "    tax = config.get_taxonomy(req.genre)\n"
        "    raw = extract_entities(text, model_path, tax, batch_size=req.batch_size)\n"
    )
    new = (
        "    tax = config.get_taxonomy(req.genre)\n"
        "    raw = extract_entities(text, req.model, tax, batch_size=req.batch_size)\n"
    )
    return src.replace(old, new), src.count(old)


def patch_p1_plumbing(src: str) -> tuple[str, int]:
    n = 0
    imp_old = "from collections.abc import AsyncGenerator\n"
    imp_new = "from collections.abc import AsyncGenerator, Callable\n"
    if imp_old in src and "Callable" not in src.split("class SecurityHeadersMiddleware")[0]:
        src = src.replace(imp_old, imp_new, 1)
        n += 1
    imp2_old = "import tempfile\nimport time\n"
    imp2_new = "import tempfile\nimport threading\nimport time\n"
    if imp2_old in src and "import threading" not in src:
        src = src.replace(imp2_old, imp2_new, 1)
        n += 1
    anchor = "active_tasks: dict[str, dict[str, Any]] = {}\ntask_event_queues: dict[str, list[asyncio.Queue]] = {}\n"
    addition = anchor + (
        "pipeline_cancel_events: dict[str, Any] = {}\n"
        "\n"
        "\n"
        "class PipelineCancelled(Exception):\n"
        '    """Raised internally when the user cancels a running pipeline task."""\n'
        "\n"
        "\n"
        "def _make_cancelling_observer(task_id: str, observer: Callable[[str, Any], None]) -> Callable[[str, Any], None]:\n"
        "    def wrapped(event: str, data: Any) -> None:\n"
        "        ev = pipeline_cancel_events.get(task_id)\n"
        "        if ev is not None and ev.is_set():\n"
        '            raise PipelineCancelled(f"Task {task_id} cancelled by user")\n'
        "        observer(event, data)\n"
        "\n"
        "    return wrapped\n"
    )
    if anchor in src and "PipelineCancelled" not in src:
        src = src.replace(anchor, addition, 1)
        n += 1
    return src, (1 if n == 3 else 0)


def patch_p2_p3_endpoints(src: str) -> tuple[str, int]:
    anchor = '@app.get("/api/pipeline/events/{task_id}")'
    endpoints = (
        '@app.get("/api/pipeline/status/{task_id}")\n'
        "async def api_pipeline_status(task_id: str, user: User = Depends(get_current_user)) -> dict[str, Any]:\n"
        "    info = active_tasks.get(task_id)\n"
        "    if not info:\n"
        '        raise HTTPException(status_code=404, detail="Task not found")\n'
        "    return {\n"
        '        "task_id": task_id,\n'
        '        "status": info.get("status", "unknown"),\n'
        '        "progress": info.get("progress", 0),\n'
        '        "current_stage": info.get("current_stage", ""),\n'
        '        "book_folder": info.get("book_folder", ""),\n'
        '        "file_path": info.get("file_path", ""),\n'
        '        "error": info.get("error", ""),\n'
        '        "logs": info.get("logs", []),\n'
        "    }\n"
        "\n"
        "\n"
        '@app.post("/api/pipeline/cancel/{task_id}")\n'
        "async def api_pipeline_cancel(task_id: str, user: User = Depends(get_current_user)) -> dict[str, str]:\n"
        "    info = active_tasks.get(task_id)\n"
        "    if not info:\n"
        '        raise HTTPException(status_code=404, detail="Task not found")\n'
        '    if info.get("status") != "running":\n'
        '        return {"status": "ignored", "detail": f"Task already {info.get(\'status\')}"}\n'
        "    ev = pipeline_cancel_events.setdefault(task_id, threading.Event())\n"
        "    ev.set()\n"
        '    info["status"] = "cancelling"\n'
        "    for q in task_event_queues.get(task_id, []):\n"
        "        q.put_nowait({\n"
        '            "event": "cancelling",\n'
        '            "data": {"message": "Cancellation requested by user"},\n'
        '            "timestamp": time.time(),\n'
        "        })\n"
        '    return {"status": "ok"}\n'
        "\n"
        "\n"
    )
    if anchor in src and "api_pipeline_status" not in src:
        return src.replace(anchor, endpoints + anchor, 1), 1
    return src, 0


def patch_p4_runner(src: str) -> tuple[str, int]:
    n = 0
    old_start = "    def _runner() -> None:\n        try:\n"
    new_start = (
        "    def _runner() -> None:\n"
        "        pipeline_cancel_events[task_id] = threading.Event()\n"
        "        _runner_observer = _make_cancelling_observer(task_id, _observer)\n"
        "        try:\n"
    )
    if old_start in src:
        src = src.replace(old_start, new_start, 1)
        n += 1
    cnt = src.count("observer=_observer")
    if cnt >= 3:
        src = src.replace("observer=_observer", "observer=_runner_observer")
        n += 1
    old_except = (
        "        except Exception as err:\n"
        "            if task_id in active_tasks:\n"
        '                active_tasks[task_id]["status"] = "failed"\n'
        '                active_tasks[task_id]["error"] = str(err)\n'
        '            _observer("error", {"error": str(err)})\n'
    )
    new_except = (
        "        except PipelineCancelled:\n"
        "            pipeline_cancel_events.pop(task_id, None)\n"
        "            if task_id in active_tasks:\n"
        '                active_tasks[task_id]["status"] = "cancelled"\n'
        '            _observer("pipeline_cancelled", {"message": "Pipeline cancelled by user"})\n'
        "        except Exception as err:\n"
        "            pipeline_cancel_events.pop(task_id, None)\n"
        "            if task_id in active_tasks:\n"
        '                active_tasks[task_id]["status"] = "failed"\n'
        '                active_tasks[task_id]["error"] = str(err)\n'
        '            _observer("error", {"error": str(err)})\n'
    )
    if old_except in src:
        src = src.replace(old_except, new_except, 1)
        n += 1
    old_done = '            _observer("pipeline_complete", {"book_folder": book_dir.name, "status": "completed"})\n'
    new_done = (
        '            _observer("pipeline_complete", {"book_folder": book_dir.name, "status": "completed"})\n'
        "            pipeline_cancel_events.pop(task_id, None)\n"
    )
    if old_done in src and new_done not in src:
        src = src.replace(old_done, new_done, 1)
        n += 1
    return src, (1 if n == 4 else 0)


def patch_p5_sse(src: str) -> tuple[str, int]:
    old = 'if active_tasks[task_id]["status"] in ("completed", "failed") and queue.empty():'
    new = 'if active_tasks[task_id]["status"] in ("completed", "failed", "cancelled") and queue.empty():'
    return src.replace(old, new), src.count(old)


def patch_p6_cleanup(src: str) -> tuple[str, int]:
    old = (
        "    for _tid in [t for t, i in active_tasks.items() if i.get(\"status\") in (\"completed\", \"failed\") and i.get(\"created_at\", 0) < cutoff]:\n"
        "        active_tasks.pop(_tid, None)\n"
        "        task_event_queues.pop(_tid, None)\n"
    )
    new = (
        "    for _tid in [t for t, i in active_tasks.items() if i.get(\"status\") in (\"completed\", \"failed\", \"cancelled\") and i.get(\"created_at\", 0) < cutoff]:\n"
        "        active_tasks.pop(_tid, None)\n"
        "        task_event_queues.pop(_tid, None)\n"
        "        pipeline_cancel_events.pop(_tid, None)\n"
    )
    return src.replace(old, new), src.count(old)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--server", default="src/tome/web/server.py")
    args = ap.parse_args()

    server = Path(args.server)
    if not server.is_file():
        sys.exit(f"server.py not found at {server} — run from project root")
    src = server.read_text(encoding="utf-8")

    steps = [
        ("P0: extract-entities GLiNER fix", patch_p0_extract_entities, True),
        ("P1: cancel plumbing (imports, state, observer wrapper)", patch_p1_plumbing, True),
        ("P2+P3: status & cancel endpoints", patch_p2_p3_endpoints, True),
        ("P4: cancellation wired into _runner", patch_p4_runner, True),
        ("P5: SSE ends on cancelled", patch_p5_sse, True),
        ("P6: cleanup drops cancel events", patch_p6_cleanup, True),
    ]

    new = src
    results = []
    for name, fn, required in steps:
        new, n = fn(new)
        results.append((name, n, required))

    print(f"file: {server}   mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    ok = True
    for name, n, required in results:
        status = "OK" if n >= 1 else ("NOT FOUND (required)" if required else "not found (optional)")
        if required and n < 1:
            ok = False
        print(f"  [{status:>24}] {name}")
    if new == src:
        print("nothing to change.")
        sys.exit(0)
    if args.apply and ok:
        backup = server.with_suffix(server.suffix + ".bak")
        backup.write_text(src, encoding="utf-8")
        server.write_text(new, encoding="utf-8")
        print(f"patched. backup: {backup}")
        print("NOTE: re-run 'python tome_phase1.py' — a second run should print 'nothing to change'.")
    elif args.apply:
        print("ABORTED — required pattern missing; file untouched.")
        sys.exit(2)
    else:
        print("(dry-run — re-run with --apply)")


if __name__ == "__main__":
    main()