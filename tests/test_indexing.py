from pathlib import Path

from app.indexing.parser import parse_openapi_spec


def test_parse_openapi_spec():
    spec_path = Path("docs/docs.json")
    documents = parse_openapi_spec(spec_path)

    assert len(documents) > 0

    for doc in documents:
        assert doc.metadata["doc_type"] == "endpoint"
        assert doc.metadata["path"]
        assert doc.metadata["method"] in ("GET", "POST", "PUT", "PATCH", "DELETE")
        assert doc.metadata["source"] == str(spec_path)


def test_parse_openapi_spec_has_auth_endpoint():
    spec_path = Path("docs/docs.json")
    documents = parse_openapi_spec(spec_path)

    paths = [doc.metadata["path"] for doc in documents]
    assert "/auth" in paths
