"""End-to-end API tests: upload -> list -> chat with sources -> delete. No external services."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.embeddings import FakeEmbeddingProvider
from app.llm import FakeLLMProvider
from app.retrieval import QdrantVectorStore
from tests.helpers import make_pdf

HANDBOOK = (
    "Employees receive twenty five days of annual leave each year. "
    "Leave requests must be submitted two weeks in advance. "
    "The office closes at six in the evening on weekdays."
)


def _upload(client: TestClient, name: str, data: bytes, content_type: str):
    return client.post("/documents/upload", files={"file": (name, data, content_type)})


def test_upload_text_document_indexes_and_lists(
    client: TestClient, vector_store: QdrantVectorStore, settings: Settings
) -> None:
    response = _upload(client, "handbook.txt", HANDBOOK.encode(), "text/plain")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "ready"
    assert body["name"] == "handbook.txt"
    assert body["content_type"] == "text/plain"
    assert body["chunk_count"] >= 1
    assert body["page_count"] is None
    assert body["error"] is None

    # The file was saved under a server-generated ID, not the client's name alone.
    saved = list((settings.upload_dir / body["id"]).iterdir())
    assert [p.name for p in saved] == ["handbook.txt"]

    listing = client.get("/documents").json()
    assert listing["total"] == 1
    assert listing["documents"][0]["id"] == body["id"]
    assert client.get(f"/documents/{body['id']}").status_code == 200


def test_upload_pdf_records_page_count(client: TestClient) -> None:
    pdf = make_pdf(["Page one discusses revenue.", "Page two discusses costs."])
    response = _upload(client, "report.pdf", pdf, "application/pdf")
    assert response.status_code == 201, response.text
    assert response.json()["page_count"] == 2
    assert response.json()["chunk_count"] >= 2


def test_upload_sanitises_filename(client: TestClient) -> None:
    response = _upload(client, "../../etc/pass wd.md", b"# hi\n\ntext", "text/markdown")
    assert response.status_code == 201
    assert response.json()["name"] == "pass_wd.md"


def test_upload_rejects_bad_type_and_disguised_pdf(client: TestClient) -> None:
    assert _upload(client, "evil.exe", b"MZ....", "application/octet-stream").status_code == 400
    r = _upload(client, "fake.pdf", b"not a pdf at all", "application/pdf")
    assert r.status_code == 400
    assert "not a PDF" in r.json()["detail"]
    assert client.get("/documents").json()["total"] == 0


def test_upload_rejects_oversized_file_before_indexing(
    client: TestClient, fake_embeddings: FakeEmbeddingProvider, settings: Settings
) -> None:
    too_big = b"a" * (settings.max_upload_bytes + 1)
    response = _upload(client, "big.txt", too_big, "text/plain")
    assert response.status_code == 413
    assert fake_embeddings.document_calls == []
    assert not any(settings.upload_dir.iterdir()) if settings.upload_dir.exists() else True


def test_upload_with_no_extractable_text_is_422_and_recorded_failed(client: TestClient) -> None:
    response = _upload(client, "blank.pdf", make_pdf([""]), "application/pdf")
    assert response.status_code == 422
    docs = client.get("/documents").json()["documents"]
    assert docs[0]["status"] == "failed"
    assert "No extractable text" in docs[0]["error"]


def test_chat_uses_documents_and_returns_sources(
    client: TestClient, fake_llm: FakeLLMProvider
) -> None:
    _upload(client, "handbook.txt", HANDBOOK.encode(), "text/plain")
    fake_llm.reply = "Twenty five days [Source 1]."

    response = client.post("/chat", json={"message": "how many days of annual leave?"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "rag"
    assert body["prompt_version"] == "rag-system-v1"
    assert body["retrieval"]["retrieved_chunks"] >= 1
    assert body["retrieval"]["cited_sources"] == 1
    assert body["sources"][0]["document_name"] == "handbook.txt"
    assert body["sources"][0]["cited"] is True
    assert "annual leave" in body["sources"][0]["snippet"]
    # Grounded context reached the model.
    assert "annual leave" in fake_llm.calls[0][0].content


def test_chat_can_bypass_documents(client: TestClient, fake_llm: FakeLLMProvider) -> None:
    response = client.post("/chat", json={"message": "hi", "use_documents": False})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "chat"
    assert body["prompt_version"] == "chat-system-v1"
    assert body["sources"] == [] and body["retrieval"] is None


def test_delete_document_removes_chunks_and_file(
    client: TestClient, vector_store: QdrantVectorStore, settings: Settings
) -> None:
    doc_id = _upload(client, "handbook.txt", HANDBOOK.encode(), "text/plain").json()["id"]
    assert client.get("/health").json()["qdrant"]["chunks"] >= 1

    assert client.delete(f"/documents/{doc_id}").status_code == 204
    assert client.get("/documents").json()["total"] == 0
    assert client.get("/health").json()["qdrant"]["chunks"] == 0
    assert not (settings.upload_dir / doc_id).exists()
    assert client.delete(f"/documents/{doc_id}").status_code == 404


def test_health_reports_all_dependencies(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["embeddings"] == {"reachable": True, "model": "fake-embed"}
    assert body["qdrant"]["reachable"] is True
    assert body["qdrant"]["collection"] == "test_documents"
    assert body["documents_ready"] == 0


def test_health_degraded_when_embeddings_down(
    client: TestClient, fake_embeddings: FakeEmbeddingProvider
) -> None:
    fake_embeddings.healthy = False
    body = client.get("/health").json()
    assert body["status"] == "degraded"
    assert body["embeddings"]["reachable"] is False


def test_upload_dir_is_isolated_per_test(settings: Settings, tmp_path: Path) -> None:
    assert settings.upload_dir.is_relative_to(tmp_path)
