import json
from pathlib import Path

from llama_index.core.schema import Document


def parse_openapi_spec(spec_path: Path) -> list[Document]:
    with open(spec_path) as f:
        spec = json.load(f)

    documents: list[Document] = []

    for path, methods in spec.get("paths", {}).items():
        for method, details in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue

            tags = details.get("tags", [])
            summary = details.get("summary", "")

            content = json.dumps(
                {
                    "path": path,
                    "method": method.upper(),
                    "summary": summary,
                    "description": details.get("description", ""),
                    "tags": tags,
                    "parameters": details.get("parameters", []),
                    "requestBody": details.get("requestBody"),
                    "responses": details.get("responses", {}),
                },
                ensure_ascii=False,
                indent=2,
            )

            documents.append(
                Document(
                    text=content,
                    metadata={
                        "doc_type": "endpoint",
                        "path": path,
                        "method": method.upper(),
                        "tags": ", ".join(tags),
                        "summary": summary,
                        "source": str(spec_path),
                    },
                )
            )

    return documents
