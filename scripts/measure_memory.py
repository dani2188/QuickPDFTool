"""Measure how much memory the app's process uses, per tool (QT-009).

No dependencies beyond the app's own. Run from the repo root:

    .venv\\Scripts\\python.exe scripts\\measure_memory.py            # all scenarios
    .venv\\Scripts\\python.exe scripts\\measure_memory.py --json out.json

How it works
------------
Every scenario runs in a FRESH child process that imports the real Flask
app and drives its real routes through the test client with realistic
sample files, so "first request" costs are not hidden by earlier requests.
After each step the child reports:

  rss     resident memory now        (Windows: WorkingSetSize, Linux: VmRSS)
  peak    highest resident memory the process has ever reached
          (Windows: PeakWorkingSetSize, Linux: VmHWM)
  threads live Python threads

It also counts how many delete_file_later() timers the step would have
started (each one is a sleeping thread in the real app). Timers are
replaced by a counter here so files go to a temp folder and nothing sleeps.

What it does NOT cover: Ghostscript and LibreOffice run as separate
operating-system processes, so their memory is NOT in the Python numbers
(compress-pdf shows only the Python side). Windows and Linux report memory
differently, so absolute numbers from this machine are an estimate for
Render; run the script on a Linux box for numbers closer to production.
"""

import io
import json
import os
import subprocess
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(BASE, "static", "examples")
MB = 1024 * 1024


# ----------------------------------------------------------- OS memory counters
def memory_now():
    """(rss_bytes, peak_rss_bytes) of this process, standard library only."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                        ("PrivateUsage", ctypes.c_size_t)]

        kernel32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), wintypes.DWORD]
        c = Counters()
        c.cb = ctypes.sizeof(c)
        psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return c.WorkingSetSize, c.PeakWorkingSetSize

    values = {}
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith(("VmRSS:", "VmHWM:")):
                values[line.split(":")[0]] = int(line.split()[1]) * 1024
    return values["VmRSS"], values["VmHWM"]


def pid_memory(pid):
    """Current resident memory of another process, in bytes (0 if it is gone)."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                        ("PrivateUsage", ctypes.c_size_t)]

        kernel32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), wintypes.DWORD]
        handle = kernel32.OpenProcess(0x0410, False, pid)  # QUERY_INFORMATION | VM_READ
        if not handle:
            return 0
        c = Counters()
        c.cb = ctypes.sizeof(c)
        ok = psapi.GetProcessMemoryInfo(handle, ctypes.byref(c), c.cb)
        kernel32.CloseHandle(handle)
        return c.WorkingSetSize if ok else 0
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    return 0


def p_(folder, name):
    return os.path.join(folder, name)


# ------------------------------------------------------------------- sample files
def make_samples(folder):
    """Create the inputs: realistic ones plus a worst case near the 20 MB cap."""
    import fitz
    import numpy as np
    from PIL import Image
    from docx import Document
    from openpyxl import Workbook

    p = lambda name: os.path.join(folder, name)  # noqa: E731

    # 20 pages of text (the page limit of the image-export tools)
    src = fitz.open(os.path.join(EXAMPLES, "text-report.pdf"))
    doc = fitz.open()
    for _ in range(4):
        doc.insert_pdf(src)
    doc.insert_pdf(src, from_page=0, to_page=1)
    doc.save(p("text-20pages.pdf"))

    # A ruled table, for pdf-to-excel
    doc = fitz.open()
    page = doc.new_page()
    for r in range(25):
        page.draw_line((50, 80 + r * 22), (500, 80 + r * 22))
    for x in (50, 200, 350, 500):
        page.draw_line((x, 80), (x, 80 + 24 * 22))
    for r in range(24):
        for c, x in enumerate((50, 200, 350)):
            page.insert_text((x + 6, 96 + r * 22), f"r{r}c{c}", fontsize=10)
    doc.save(p("table.pdf"))

    # Worst case: 9 full-page photographic scans of random noise, which
    # JPEG can't shrink, giving a PDF just under the 20 MB upload cap.
    rng = np.random.default_rng(3)
    doc = fitz.open()
    for _ in range(9):
        noise = rng.integers(0, 256, (2400, 1700, 3), dtype=np.uint8)
        buf = io.BytesIO()
        Image.fromarray(noise).save(buf, "JPEG", quality=70)
        page = doc.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=buf.getvalue())
    doc.save(p("worst-case-scan.pdf"))

    # Tiny files that are enormous once decoded: a flat 9000x9000 JPEG (81 megapixels,
    # just under Pillow's 89 MP warning) and a PDF whose one page is 5000x5000 points.
    Image.new("RGB", (9000, 9000), (120, 160, 200)).save(p("huge-image-81MP.jpg"), "JPEG", quality=80)
    doc = fitz.open()
    page = doc.new_page(width=5000, height=5000)
    page.insert_text((200, 400), "Large-format page", fontsize=120)
    page.draw_rect(fitz.Rect(300, 600, 4700, 4700), fill=(0.8, 0.9, 1))
    doc.save(p("huge-page-5000pt.pdf"))
    # A0 poster (2384 x 3370 pt), a size real users do have
    doc = fitz.open()
    page = doc.new_page(width=2384, height=3370)
    page.insert_text((100, 300), "A0 poster", fontsize=200)
    doc.save(p("a0-poster.pdf"))

    # A long text PDF (300 pages, a few hundred KB): page COUNT is not bounded by the upload cap either.
    doc = fitz.open()
    for _ in range(50):
        doc.insert_pdf(src)
    doc.save(p("text-300pages.pdf"))
    doc = fitz.open()
    for _ in range(17):
        doc.insert_pdf(src)
    doc.save(p("text-100pages.pdf"))

    wb = Workbook()
    ws = wb.active
    for r in range(2000):
        ws.append([f"row {r}", r, r * 1.5, "text " * 5])
    wb.save(p("sheet-2000-rows.xlsx"))

    d = Document()
    for i in range(40):
        d.add_paragraph("Paragraph %d. " % i + "Some body text. " * 30)
    d.save(p("doc-40-paragraphs.docx"))
    return p


# ------------------------------------------------------------------ the scenarios
def scenarios(p):
    """name -> list of (label, route, {field: [files]}, form-data)."""
    ex = lambda n: os.path.join(EXAMPLES, n)  # noqa: E731
    small, twenty, worst = ex("text-report.pdf"), p("text-20pages.pdf"), p("worst-case-scan.pdf")
    return {
        "pdf-to-word": [
            ("6-page text PDF", "/pdf-to-word", {"pdf": [small]}, {}),
            ("same again", "/pdf-to-word", {"pdf": [small]}, {}),
            ("20-page text PDF", "/pdf-to-word", {"pdf": [twenty]}, {}),
            ("worst-case scan", "/pdf-to-word", {"pdf": [worst]}, {}),
        ],
        "pdf-to-word-100-pages": [("100-page text PDF", "/pdf-to-word", {"pdf": [p("text-100pages.pdf")]}, {})],
        "pdf-to-excel": [
            ("ruled table", "/pdf-to-excel", {"pdf": [p("table.pdf")]}, {}),
            ("20-page text (no table)", "/pdf-to-excel", {"pdf": [twenty]}, {}),
        ],
        "excel-to-pdf": [("2000-row sheet", "/excel-to-pdf", {"excel": [p("sheet-2000-rows.xlsx")]}, {})],
        "pdf-to-text": [("20-page text PDF", "/pdf-to-text", {"pdf": [twenty]}, {}),
                        ("worst-case scan", "/pdf-to-text", {"pdf": [worst]}, {})],
        "pdf-to-jpg": [("20-page text PDF", "/pdf-to-jpg", {"pdf": [twenty]}, {}),
                       ("worst-case scan (9 pages)", "/pdf-to-jpg", {"pdf": [worst]}, {})],
        "pdf-to-png": [("worst-case scan (9 pages)", "/pdf-to-png", {"pdf": [worst]}, {})],
        "extract-images": [("worst-case scan", "/extract-images", {"pdf": [worst]}, {})],
        "many-pages": [("pdf-to-text, 300 pages", "/pdf-to-text", {"pdf": [p("text-300pages.pdf")]}, {}),
                       ("pdf-to-excel, 300 pages", "/pdf-to-excel", {"pdf": [p("text-300pages.pdf")]}, {}),
                       ("split-pdf, 300 pages", "/split-pdf", {"pdf": [p("text-300pages.pdf")]}, {}),
                       ("rotate-pdf, 300 pages", "/rotate-pdf", {"pdf": [p("text-300pages.pdf")]}, {"rotation": "90"})],
        "split-pdf": [("20-page text PDF", "/split-pdf", {"pdf": [twenty]}, {})],
        "merge-pdf": [("worst-case + 20-page", "/merge-pdf", {"pdfs": [worst, twenty]}, {})],
        "pdf-to-jpg-large-pages": [("A0 poster (2384x3370 pt)", "/pdf-to-jpg", {"pdf": [p("a0-poster.pdf")]}, {}),
                                   ("5000x5000 pt page", "/pdf-to-jpg", {"pdf": [p("huge-page-5000pt.pdf")]}, {})],
        "huge-image": [("resize-image 81 MP", "/resize-image", {"image": [p("huge-image-81MP.jpg")]}, {"width": "1080", "height": "1080"}),
                       ("compress-jpg 81 MP", "/compress-jpg", {"images": [p("huge-image-81MP.jpg")]}, {"level": "medium"}),
                       ("jpg-to-pdf 81 MP", "/jpg-to-pdf", {"images": [p("huge-image-81MP.jpg")]}, {})],
        "compress-jpg": [("3000x2000 photo", "/compress-jpg", {"images": [ex("landscape-photo.jpg")]}, {"level": "medium"})],
        "jpg-to-pdf": [("two 3000x2000 photos", "/jpg-to-pdf",
                        {"images": [ex("landscape-photo.jpg"), ex("landscape-photo.jpg")]}, {})],
        "resize-image": [("3000x2000 photo", "/resize-image", {"image": [ex("landscape-photo.jpg")]},
                          {"width": "1080", "height": "1080"})],
        "remove-watermark": [("20-page text PDF", "/remove-watermark", {"pdf": [twenty]}, {})],
    }


# ----------------------------------------------------------------------- child side
def child_main(name, folder):
    sys.path.insert(0, BASE)
    os.chdir(BASE)
    result = {"scenario": name, "steps": []}

    def record(label, extra=None):
        rss, peak = memory_now()
        import threading
        row = {"label": label, "rss": rss / MB, "peak": peak / MB, "threads": threading.active_count()}
        row.update(extra or {})
        result["steps"].append(row)

    record("python started")
    if name == "boot-lazy-pdf2docx":
        # What boot would cost if app.py did not import pdf2docx (and so OpenCV/numpy) at module level.
        import types
        stub = types.ModuleType("pdf2docx")
        stub.Converter = None
        sys.modules["pdf2docx"] = stub
    import time
    started = time.time()
    import app as qt_app
    record("import app", {"seconds": time.time() - started})

    timers = {"n": 0}
    real_delete_file_later = qt_app.delete_file_later
    qt_app.delete_file_later = lambda *a, **k: timers.__setitem__("n", timers["n"] + 1)
    qt_app.UPLOAD_FOLDER = os.path.join(folder, "uploads")
    os.makedirs(qt_app.UPLOAD_FOLDER, exist_ok=True)
    client = qt_app.app.test_client()

    def hit(route, files, data):
        payload = dict(data)
        handles = []
        for field, paths in files.items():
            items = []
            for path in paths:
                h = open(path, "rb")
                handles.append(h)
                items.append((h, os.path.basename(path)))
            payload[field] = items
        before = timers["n"]
        r = client.post(route, data=payload, content_type="multipart/form-data")
        for h in handles:
            h.close()
        r.get_data()
        return r.status_code, timers["n"] - before

    plan = scenarios(lambda n: os.path.join(folder, n))
    if name == "delete-timers":
        # The real delete_file_later() starts one sleeping thread per file. What do N of them cost?
        import threading
        for n in (0, 100, 500, 1000):
            while threading.active_count() - 1 < n:
                real_delete_file_later(os.path.join(folder, "nothing"), delay=120)
            time.sleep(0.3)
            record(f"{n} sleeping timer threads")
    elif name == "compress-pdf":
        # Ghostscript is a separate OS process: poll its memory while it runs.
        import subprocess as real_subprocess
        peak = {"mb": 0.0}

        def watch(pid):
            while proc_alive[0]:
                peak["mb"] = max(peak["mb"], pid_memory(pid) / MB)
                time.sleep(0.01)

        class Shim:
            CalledProcessError = real_subprocess.CalledProcessError

            @staticmethod
            def run(cmd, check=False, **kw):
                import threading
                proc = real_subprocess.Popen(cmd)
                proc_alive[0] = True
                t = threading.Thread(target=watch, args=(proc.pid,))
                t.start()
                code = proc.wait()
                proc_alive[0] = False
                t.join()
                if check and code:
                    raise real_subprocess.CalledProcessError(code, cmd)
                return None

        proc_alive = [False]
        qt_app.subprocess = Shim
        for label, path, level in (("worst-case scan, low", p_(folder, "worst-case-scan.pdf"), "low"),
                                   ("worst-case scan, extreme", p_(folder, "worst-case-scan.pdf"), "extreme"),
                                   ("20-page text, medium", p_(folder, "text-20pages.pdf"), "medium")):
            peak["mb"] = 0.0
            out = os.path.join(folder, "out_" + level + ".pdf")
            qt_app.compress_pdf(path, out, level=level)
            record(label, {"gs_peak_mb": peak["mb"], "ok": os.path.exists(out)})
    elif name in ("boot", "boot-lazy-pdf2docx"):
        client.get("/")
        client.get("/pdf-tools")
        record("GET / and /pdf-tools")
    elif name == "worker-lifetime":
        # What a real worker does all day: every tool in turn, then the same
        # cycle again, to tell a one-off import cost from a steady leak.
        cycle_steps = [s for k, v in plan.items() for s in v]
        for cycle in range(1, 6):
            codes, t = [], 0
            for label, route, files, data in cycle_steps:
                code, n = hit(route, files, data)
                codes.append(code)
                t += n
            record(f"after full cycle {cycle} ({len(cycle_steps)} requests)",
                   {"timers": t, "bad": sum(1 for c in codes if c not in (200, 302))})
    else:
        for label, route, files, data in plan[name]:
            code, n = hit(route, files, data)
            record(label, {"status": code, "timers": n})
    print("RESULT" + json.dumps(result))


# ---------------------------------------------------------------------- parent side
def run_parent(out_json):
    folder = tempfile.mkdtemp(prefix="memtest_")
    print("Creating sample files …")
    sys.path.insert(0, BASE)
    os.chdir(BASE)
    make_samples(folder)
    sizes = {f: os.path.getsize(os.path.join(folder, f)) / MB for f in sorted(os.listdir(folder))}
    print("  " + ", ".join(f"{k} {v:.1f} MB" for k, v in sizes.items()) + "\n")

    order = ["boot", "boot-lazy-pdf2docx", "delete-timers", "compress-pdf", "pdf-to-jpg-large-pages", "huge-image", "many-pages", "pdf-to-word-100-pages", "pdf-to-word", "pdf-to-excel", "excel-to-pdf", "pdf-to-text", "pdf-to-jpg", "pdf-to-png",
             "extract-images", "split-pdf", "merge-pdf", "jpg-to-pdf", "compress-jpg", "resize-image", "remove-watermark",
             "worker-lifetime"]
    if "--only" in sys.argv:
        wanted = sys.argv[sys.argv.index("--only") + 1].split(",")
        order = [n for n in order if n in wanted]
    results = []
    for name in order:
        proc = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--child", name, folder],
                              capture_output=True, text=True, cwd=BASE)
        line = next((l for l in proc.stdout.splitlines() if l.startswith("RESULT")), None)
        if not line:
            print(f"!! {name} failed:\n{proc.stderr[-1500:]}")
            continue
        res = json.loads(line[len("RESULT"):])
        results.append(res)
        print(f"=== {name}")
        print(f"  {'step':<34}{'RSS MB':>9}{'peak MB':>9}{'threads':>9}{'timers':>8}")
        for s in res["steps"]:
            extra = f"{s['timers']:>8}" if "timers" in s else ""
            if "seconds" in s:
                extra += f"   import took {s['seconds']:.1f}s"
            if "gs_peak_mb" in s:
                extra += f"   Ghostscript peak {s['gs_peak_mb']:.0f} MB (separate process), output {'ok' if s['ok'] else 'MISSING'}"
            flag = "" if s.get("status", 200) in (200, 302) else f"  HTTP {s['status']} (rejected)"
            print(f"  {s['label']:<34}{s['rss']:>9.0f}{s['peak']:>9.0f}{s['threads']:>9}{extra}{flag}")
        print()
    if out_json:
        with open(out_json, "w") as f:
            json.dump({"platform": sys.platform, "python": sys.version.split()[0], "samples_mb": sizes, "results": results}, f, indent=1)
        print("wrote", out_json)


if __name__ == "__main__":
    if "--child" in sys.argv:
        i = sys.argv.index("--child")
        child_main(sys.argv[i + 1], sys.argv[i + 2])
    else:
        out = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
        run_parent(out)
