from fastapi.testclient import TestClient

from app.eval.cases import GOLDEN_CASES
from app.eval.runner import run_golden_eval


async def test_golden_eval_passes_offline() -> None:
    report = await run_golden_eval()
    failed = [case.id for case in report.cases if not case.passed]
    assert report.total == len(GOLDEN_CASES)
    assert report.failed == 0, f"failed: {failed} details={[c.failures for c in report.cases]}"
    by_id = {case.id: case for case in report.cases}
    assert by_id["retrieve_leave"].cited_sources >= 1
    assert by_id["retrieve_leave"].groundedness is not None
    assert by_id["refuse_unrelated"].refused is True
    assert by_id["calculator"].tools == ["calculator"]
    assert "save_note" in by_id["save_note_approve"].tools
    # Report must not echo the question, answer, or note body.
    dumped = report.model_dump_json().lower()
    assert "buy milk" not in dumped
    assert "mars colony" not in dumped
    assert "twenty five" not in dumped


def test_eval_run_and_latest_endpoints(client: TestClient) -> None:
    missing = client.get("/eval/latest")
    assert missing.status_code == 204

    response = client.post("/eval/run")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["failed"] == 0
    assert body["passed"] == body["total"]
    assert body["total"] == len(GOLDEN_CASES)

    latest = client.get("/eval/latest")
    assert latest.status_code == 200
    assert latest.json()["ran_at"] == body["ran_at"]
    assert "buy milk" not in latest.text.lower()
