def test_health_reports_extractive_mode_without_a_key(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["answer_mode"] == "extractive"
    assert body["documents"] == 4


def test_auto_mode_without_key_falls_back_to_extractive(make_client):
    client = make_client(answer_mode="auto")
    assert client.get("/api/health").json()["answer_mode"] == "extractive"
    assert client.post("/api/chat", json={"question": "Do you deliver?"}).json()["mode"] == "extractive"


def test_llm_mode_without_key_gives_a_clear_error(make_client):
    client = make_client(answer_mode="llm")
    response = client.post("/api/chat", json={"question": "Do you deliver?"})
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_pages_are_served(client):
    assert "Docs chatbot" in client.get("/").text
    assert client.get("/widget.js").headers["content-type"].startswith("application/javascript")
    assert "/widget.js" in client.get("/widget-demo").text


def test_chat_answers_with_sources(client):
    body = client.post("/api/chat", json={"question": "What time do you open on Sunday?"}).json()
    assert body["found"] is True
    assert body["offer_human"] is False
    assert body["sources"][0] == {**body["sources"][0], "source": "opening-hours.pdf", "page": 1}
    assert "8:00 am" in body["answer"]


def test_chat_says_i_dont_know(client):
    body = client.post("/api/chat", json={"question": "What is the capital of France?"}).json()
    assert body["found"] is False
    assert body["answer"].startswith("I don't know")
    assert body["sources"] == []
    assert body["offer_human"] is True


def test_chat_rejects_empty_question(client):
    assert client.post("/api/chat", json={"question": "   "}).status_code == 422
    assert client.post("/api/chat", json={"question": "x" * 1001}).status_code == 422


def test_upload_then_ask(client):
    files = {"files": ("wifi.txt", b"The guest wifi password is crumbs2026.", "text/plain")}
    response = client.post("/api/documents", files=files)
    assert response.status_code == 200
    assert response.json()["indexed"] == [{"name": "wifi.txt", "chunks": 1}]
    names = [d["name"] for d in client.get("/api/documents").json()["documents"]]
    assert "wifi.txt" in names
    body = client.post("/api/chat", json={"question": "What is the wifi password?"}).json()
    assert body["sources"][0]["source"] == "wifi.txt"
    assert client.delete("/api/documents/wifi.txt").status_code == 200
    assert client.delete("/api/documents/wifi.txt").status_code == 404


def test_upload_rejects_unsupported_and_oversized_files(make_client):
    client = make_client(max_upload_mb=1)
    bad = client.post("/api/documents", files={"files": ("x.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code == 400
    assert "Unsupported" in bad.json()["errors"][0]["error"]
    big = client.post("/api/documents", files={"files": ("big.txt", b"a" * (1024 * 1024 + 1), "text/plain")})
    assert big.status_code == 400
    assert "Larger than" in big.json()["errors"][0]["error"]


def test_uploads_can_require_the_admin_token(make_client):
    client = make_client(public_uploads=False, admin_token="secret")
    files = {"files": ("a.txt", b"hello there", "text/plain")}
    assert client.post("/api/documents", files=files).status_code == 401
    ok = client.post("/api/documents", files=files, headers={"X-Admin-Token": "secret"})
    assert ok.status_code == 200


def test_rate_limit_per_ip(make_client):
    client = make_client(rate_limit_per_minute=3)
    codes = [client.post("/api/chat", json={"question": "Do you deliver?"}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    limited = client.post("/api/chat", json={"question": "Do you deliver?"})
    assert "Retry-After" in limited.headers


def test_leads_are_saved_and_exported_with_token(make_client):
    client = make_client(admin_token="s3cret")
    lead = {"name": "Asha", "email": "asha@example.com", "question": "Can you bake 200 cupcakes?"}
    assert client.post("/api/leads", json=lead).status_code == 201

    assert client.get("/api/leads/export").status_code == 401
    assert client.get("/api/leads/export", headers={"X-Admin-Token": "wrong"}).status_code == 401

    rows = client.get("/api/leads/export", headers={"Authorization": "Bearer s3cret"}).json()["leads"]
    assert len(rows) == 1 and rows[0]["email"] == "asha@example.com"

    csv = client.get("/api/leads/export?format=csv", headers={"X-Admin-Token": "s3cret"})
    assert csv.headers["content-type"].startswith("text/csv")
    assert "asha@example.com" in csv.text


def test_lead_validation(client):
    bad_email = {"name": "Asha", "email": "not-an-email", "question": "hi"}
    assert client.post("/api/leads", json=bad_email).status_code == 422
    assert client.post("/api/leads", json={"name": " ", "email": "a@b.co", "question": "hi"}).status_code == 422


def test_export_is_off_without_admin_token(client):
    response = client.get("/api/leads/export", headers={"X-Admin-Token": ""})
    assert response.status_code == 503
    assert "ADMIN_TOKEN" in response.json()["detail"]


def test_bad_config_fails_with_a_clear_message(tmp_path, embedder):
    import pytest

    from app.main import create_app
    from tests.conftest import make_settings

    with pytest.raises(SystemExit, match="OPENAI_API_KEY"):
        create_app(make_settings(tmp_path, embedding_backend="openai"), embedder=embedder)
