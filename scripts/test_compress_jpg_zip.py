"""Compress JPG must put every uploaded photo's output in the ZIP, even when names repeat.

Run from the repo root:

    .venv\Scripts\python.exe scripts\test_compress_jpg_zip.py

Uploads photos with the same file name (as happens when files come from different folders, or
differ only in capitals) through the real /compress-jpg route and checks that the ZIP holds one
entry per photo, with unique names and the right content for each. Exits 1 on any failure.
"""

import io
import os
import re
import sys
import zipfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from PIL import Image  # noqa: E402

import app as qt_app  # noqa: E402

client = qt_app.app.test_client()
failures = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)


def jpg(color, size=(120, 90)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG", quality=95)
    buf.seek(0)
    return buf


def run(files):
    r = client.post("/compress-jpg", data={"images": files, "level": "medium"},
                    content_type="multipart/form-data")
    assert r.status_code == 200, r.status_code
    page = r.get_data(as_text=True)
    zip_name = re.search(r"[0-9a-f-]{36}_compressed_jpgs\.zip", page).group(0)
    with zipfile.ZipFile(os.path.join(qt_app.UPLOAD_FOLDER, zip_name)) as z:
        return page, {n: z.read(n) for n in z.namelist()}, z.namelist()


def dominant(files, name):
    with Image.open(io.BytesIO(files[name])) as im:
        return im.convert("RGB").getpixel((60, 45))


RED, GREEN, BLUE = (220, 20, 20), (20, 200, 20), (20, 20, 220)

page, z, names = run([(jpg(RED), "photo.jpg"), (jpg(GREEN), "photo.jpg"), (jpg(BLUE), "photo.jpg")])
check("three same-named uploads give three ZIP entries", len(names) == 3)
check("ZIP entry names are unique", len(set(n.lower() for n in names)) == 3)
check("first keeps its name, the others get a counter",
      names == ["photo.jpg", "photo (2).jpg", "photo (3).jpg"])
check("each entry holds its own photo",
      [max(range(3), key=lambda i: dominant(z, n)[i]) for n in names] == [0, 1, 2])
check("result page lists the same unique names", all(n in page for n in names))

page, z, names = run([(jpg(RED), "IMG.JPG"), (jpg(GREEN), "img.jpg")])
check("names differing only in capitals are kept apart",
      len(names) == 2 and len({n.lower() for n in names}) == 2)

page, z, names = run([(jpg(RED), "a.jpg"), (jpg(GREEN), "b.jpg")])
check("distinct names are left untouched", names == ["a.jpg", "b.jpg"])

page, z, names = run([(jpg(RED), "x.jpg"), (io.BytesIO(b"not an image"), "x.jpg"), (jpg(GREEN), "x.jpg")])
check("an unreadable duplicate does not use up a number", names == ["x.jpg", "x (2).jpg"])

print(f"\n{'FAILED: ' + str(len(failures)) if failures else 'All checks passed.'}")
sys.exit(1 if failures else 0)
