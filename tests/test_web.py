import io
from pathlib import Path

from fastapi.testclient import TestClient

from tome.web.server import app

client = TestClient(app)


def test_security_headers():
    res = client.get("/robots.txt")
    assert res.status_code == 200
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_seo_endpoints():
    res = client.get("/robots.txt")
    assert res.status_code == 200
    assert "User-agent:" in res.text

    res = client.get("/sitemap.xml")
    assert res.status_code == 200
    assert "<urlset" in res.text

    res = client.get("/manifest.json")
    assert res.status_code == 200
    assert res.json()["name"] == "Tome"

    res = client.get("/favicon.svg")
    assert res.status_code == 200
    assert "<svg" in res.text


def test_auth_all_users_and_permissions():
    # 1. Test unauthenticated request
    res = client.get("/api/auth/me")
    assert res.status_code == 401

    # 2. Test invalid credentials
    res = client.post("/api/auth/login", json={"username": "aren", "password": "wrongpassword"})
    assert res.status_code == 401

    # 3. Test user 1: aren
    res = client.post("/api/auth/login", json={"username": "aren", "password": "0009"})
    assert res.status_code == 200
    aren_token = res.json()["token"]
    assert aren_token

    # 4. Test user 2: mobina
    res = client.post("/api/auth/login", json={"username": "mobina", "password": "1383"})
    assert res.status_code == 200
    mobina_token = res.json()["token"]
    assert mobina_token

    # 5. Test newly added user 3: khorshid / 1382
    res = client.post("/api/auth/login", json={"username": "khorshid", "password": "1382"})
    assert res.status_code == 200
    khorshid_token = res.json()["token"]
    assert khorshid_token

    # Verify session profile
    headers = {"Authorization": f"Bearer {khorshid_token}"}
    res = client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "khorshid"
    assert data["is_admin"] is True

    # 6. Logout and verify token is invalidated
    res = client.post("/api/auth/logout", cookies={"session_token": khorshid_token})
    assert res.status_code == 200
    res = client.get("/api/auth/me", headers=headers)
    assert res.status_code == 401


def test_standalone_tools_exhaustive():
    login_res = client.post("/api/auth/login", json={"username": "khorshid", "password": "1382"})
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Genre detection
    res = client.post(
        "/api/tools/detect-genre",
        json={"text": "The dragon soared over the dark kingdom of sorcery.", "filename": "story.txt"},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["genre"] == "fantasy"

    # Persian NLP Copyeditor (Shekar)
    res = client.post(
        "/api/tools/edit",
        json={"text": "اين كتاب مي باشد ."},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "این" in data["edited_text"]
    assert data["words_modified"] > 0

    # Chapter Segmenter
    sample_md = """# Chapter 1: The First Flight

The wind swept across the mountain peaks as the dawn sun pierced through heavy gray clouds.
Marcus stood silently upon the overlook, looking down upon the forgotten valleys below.
There was no return once the boundary had been crossed.

# Chapter 2: Shadows of the Citadel

Within the ancient stone walls, shadows danced softly against the weathered limestone pillars.
A faint melody drifted from the vaulted corridors ahead, guiding his steps into the dark.
He knew the answer lay somewhere deep beneath the subterranean crypts.
"""
    res = client.post(
        "/api/tools/chapterize",
        data={"markdown": sample_md, "book_title": "test_volume"},
        headers=headers,
    )
    assert res.status_code == 200
    ch_data = res.json()
    assert ch_data["chapter_count"] >= 1
    assert len(ch_data["chapters"]) >= 1


def test_config_and_prompts_crud():
    login_res = client.post("/api/auth/login", json={"username": "aren", "password": "0009"})
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # GET config
    res = client.get("/api/config", headers=headers)
    assert res.status_code == 200
    cfg = res.json()
    assert "general" in cfg or "translation" in cfg or "nlp" in cfg

    # POST config
    res = client.post(
        "/api/config",
        json={"translation": {"target_language": "Persian", "genre": "fantasy"}},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # GET prompts
    res = client.get("/api/prompts", headers=headers)
    assert res.status_code == 200
    prompts = res.json()
    assert "chapter_translation_with_glossary_system_prompt" in prompts

    # POST prompts (supports both canonical and alias keys)
    res = client.post(
        "/api/prompts",
        json={"prompts": {"user_style_rules": "Maintain high literary flow."}},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_books_and_chapters_error_handling():
    login_res = client.post("/api/auth/login", json={"username": "mobina", "password": "1383"})
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # List books
    res = client.get("/api/books", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # 404 for non-existent book
    res = client.get("/api/books/non_existent_book_folder_12345", headers=headers)
    assert res.status_code == 404

    # 404 for non-existent chapter
    res = client.get("/api/books/non_existent_book_folder_12345/chapters/unknown_ch", headers=headers)
    assert res.status_code == 404

    # 404 for download from non-existent book
    res = client.get("/api/books/non_existent_book_folder_12345/download/docx", headers=headers)
    assert res.status_code == 404


def test_pipeline_validation_and_events():
    login_res = client.post("/api/auth/login", json={"username": "khorshid", "password": "1382"})
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Pipeline launch with non-existent file
    res = client.post(
        "/api/pipeline/run",
        json={"file_path": "non_existent_manuscript.epub"},
        headers=headers,
    )
    assert res.status_code == 400
    assert "File not found" in res.json()["detail"]

    # Check non-existent task events
    res = client.get("/api/pipeline/events/task_invalid_999999", headers=headers)
    assert res.status_code == 404

    # Upload file validation
    test_content = b"# Sample Manuscript\nTesting pipeline validation."
    res = client.post(
        "/api/tools/upload",
        files={"file": ("test_manuscript.md", io.BytesIO(test_content), "text/markdown")},
        headers=headers,
    )
    assert res.status_code == 200
    uploaded_path = res.json()["path"]
    assert Path(uploaded_path).exists()

    # Now launch pipeline on the uploaded file
    res = client.post(
        "/api/pipeline/run",
        json={"file_path": uploaded_path, "skip_gliner": True, "translate": False},
        headers=headers,
    )
    assert res.status_code == 200
    task_id = res.json()["task_id"]
    assert task_id

    # Connect to event stream for task
    event_res = client.get(f"/api/pipeline/events/{task_id}", headers=headers)
    assert event_res.status_code == 200


def test_spa_routing():
    for path in ["/", "/bookshelf", "/pipeline", "/tools", "/prompts", "/settings"]:
        res = client.get(path)
        assert res.status_code == 200
        assert "Tome" in res.text
        assert "root" in res.text


def test_manuscript_resolver_and_library_tools():
    import socket

    from tome.cli.main import find_available_port
    from tome.config import TomeConfig
    from tome.web.server import _resolve_manuscript_path

    cfg = TomeConfig.load_config()

    # 1. Test port fallback logic
    p1 = find_available_port(8000)
    assert isinstance(p1, int) and p1 >= 8000

    # Simulate port 8000 in use
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", p1))
    s.listen(1)
    try:
        p2 = find_available_port(p1)
        assert p2 > p1
    finally:
        s.close()

    # 2. Test _resolve_manuscript_path
    book_test_dir = cfg.output_dir / "Book"
    book_test_dir.mkdir(parents=True, exist_ok=True)
    orig_dir = book_test_dir / "original"
    orig_dir.mkdir(parents=True, exist_ok=True)
    if not (orig_dir / "book.md").exists():
        (orig_dir / "book.md").write_text("# Book Title\nSample content for testing.", encoding="utf-8")
    if not (book_test_dir / "full_book.md").exists():
        (book_test_dir / "full_book.md").write_text("# Book Title\nSample content for testing.", encoding="utf-8")
    chap_dir = book_test_dir / "chapters"
    chap_dir.mkdir(parents=True, exist_ok=True)
    if not (chap_dir / "01_chapter_1.md").exists():
        (chap_dir / "01_chapter_1.md").write_text("# Chapter 1\nTest chapter content.", encoding="utf-8")

    resolved_book = _resolve_manuscript_path("Book", cfg)
    assert resolved_book is not None
    assert resolved_book.exists()

    resolved_once = _resolve_manuscript_path("Once Upon A Broken Heart", cfg)
    assert resolved_once is not None
    assert resolved_once.exists()

    # Path traversal protection
    bad = _resolve_manuscript_path("../../../../etc/passwd", cfg)
    assert bad is None

    # 3. Test standalone tools using library books with authenticated user
    login_res = client.post("/api/auth/login", json={"username": "khorshid", "password": "1382"})
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Genre detection on library book
    res = client.post("/api/tools/detect-genre", json={"filename": "Book"}, headers=headers)
    assert res.status_code == 200
    assert "genre" in res.json()

    # Metadata extraction on library book
    res = client.post("/api/tools/extract-metadata", data={"path": "Book"}, headers=headers)
    assert res.status_code == 200
    assert "title" in res.json()

    # Manuscript conversion on library book
    res = client.post("/api/tools/convert", data={"path": "Book"}, headers=headers)
    assert res.status_code == 200
    assert "markdown_path" in res.json() or "preview" in res.json()

    # Chapterization on library book path
    res = client.post("/api/tools/chapterize", data={"path": "Book", "book_title": "Book"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["total_chapters"] >= 1


def test_generate_launchd_plist(tmp_path):
    from tome.web.service import generate_launchd_plist

    plist = generate_launchd_plist(
        exec_args=["/opt/homebrew/bin/tome"],
        work_dir=str(tmp_path),
        host="127.0.0.1",
        port=9000,
    )

    assert "com.tome.web" in plist
    assert "<string>/opt/homebrew/bin/tome</string>" in plist
    assert "<string>web</string>" in plist
    assert "<string>--host</string>" in plist
    assert "<string>127.0.0.1</string>" in plist
    assert "<string>--port</string>" in plist
    assert "<string>9000</string>" in plist
    assert f"<string>{tmp_path}/logs/web/service.log</string>" in plist
    assert "<key>RunAtLoad</key>" in plist
    assert "<key>KeepAlive</key>" in plist
