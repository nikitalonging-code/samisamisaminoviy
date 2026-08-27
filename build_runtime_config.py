import os
from pathlib import Path

root=Path(__file__).resolve().parent
url=os.getenv("BACKEND_PUBLIC_URL", "").strip().rstrip("/")
if not url:
    raise SystemExit("BACKEND_PUBLIC_URL is required for the frontend build")
(root/"runtime-config.js").write_text(
    "window.__APP_CONFIG__ = {apiBase: " + repr(url) + "};\n",
    encoding="utf-8"
)
print("Generated runtime-config.js for", url)
