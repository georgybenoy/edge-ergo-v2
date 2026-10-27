from PIL import Image
import io
import base64
from pathlib import Path

img = Image.open("dashboard/public/logo.png").convert("RGBA")
img = img.resize((128, 128), Image.Resampling.LANCZOS)
buf = io.BytesIO()
img.save(buf, format="PNG", optimize=True)
b64 = base64.b64encode(buf.getvalue()).decode("ascii")

target = Path("central_server/reports/logo_base64.py")
target.write_text(f'"""Embedded EdgeErgo logo base64."""\n\nLOGO_PNG_BASE64 = "{b64}"\n', encoding="utf-8")
print(f"Generated {target} with base64 length {len(b64)}")
