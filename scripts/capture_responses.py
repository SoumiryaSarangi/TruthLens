"""Capture real POST /verify responses for the demo chips (input to ui_render_check.js).

    python scripts/capture_responses.py reports/ui_responses.json
    node scripts/ui_render_check.js app/static/app.js reports/ui_responses.json \
        app/static/i18n/en.json

CI has no browser and no Node, so the page's rendering is checked here, locally,
before a demo: app.js's own render() over what the API really returns. Its first
run found the template explanation labelled with the input language.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    out_path = Path(args[0] if args else "reports/ui_responses.json")
    samples = json.loads((ROOT / "app/static/samples.json").read_text(encoding="utf-8"))
    client = TestClient(app)
    out = {"version": client.get("/version").json(), "responses": []}
    for chip in samples["chips"]:
        r = client.post("/verify", json={"text": chip["text"]})
        out["responses"].append({"shows": chip["shows"], "status": r.status_code,
                                 "body": r.json()})
    out["r422"] = client.post("/verify", json={"text": "   "}).status_code
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print("captured", len(out["responses"]), "responses; empty text ->", out["r422"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
