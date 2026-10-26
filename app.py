import fitz
from PIL import Image, ImageFilter, ImageOps
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from PyPDF2.errors import PdfReadError
from pdfminer.pdfparser import PDFSyntaxError

from flask import Flask, request, render_template, send_file, jsonify, redirect
import subprocess
import os
import threading
import time
import platform
import uuid
import io
import zipfile
import datetime
from urllib.parse import quote

from werkzeug.utils import secure_filename
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import json
import re
import math
import xml.etree.ElementTree as ET
import requests




app = Flask(__name__)

# limit upload size
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024


# -----------------------------
# CANONICAL HOST REDIRECT
# -----------------------------

CANONICAL_ORIGIN = "https://hellobrivio.com"

# Optional: set HEALTH_CHECK_PATH in the Render dashboard if a health-check
# path is configured there (render.yaml has none), so it is never redirected.
HEALTH_CHECK_PATH = os.environ.get("HEALTH_CHECK_PATH") or None


def _host_needs_redirect(host):
    """True for Render's default hostnames and the www host; False for the
    canonical host, localhost, IP addresses and anything unknown."""
    host = host.strip().lower().rstrip(".")
    if host.startswith("["):  # bracketed IPv6 literal, possibly with a port
        return False
    host = host.split(":")[0]
    return host == "onrender.com" or host.endswith(".onrender.com") or host == "www.hellobrivio.com"


@app.before_request
def redirect_to_canonical_host():
    """Send every request for onrender.com or www.hellobrivio.com to
    https://hellobrivio.com, keeping the path and query string.

    Render sits behind a proxy, so the original host may arrive in
    X-Forwarded-Host; both it and Host are checked, so a client can't dodge
    the redirect by sending a different forwarded header. The target is a
    fixed constant, never built from the request, so this can't become an
    open redirect.
    """
    if HEALTH_CHECK_PATH and request.path == HEALTH_CHECK_PATH:
        return None

    hosts = [request.host]
    forwarded = request.headers.get("X-Forwarded-Host")
    if forwarded:
        hosts += forwarded.split(",")

    if not any(_host_needs_redirect(h) for h in hosts):
        return None

    target = CANONICAL_ORIGIN + quote(request.path, safe="/")
    if request.query_string:
        target += "?" + request.query_string.decode("latin-1")

    # 301 for page views. A form POST must keep its method and body, which a
    # 301 would turn into a GET, so those get a 308 (also permanent).
    return redirect(target, code=301 if request.method in ("GET", "HEAD") else 308)

UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# -----------------------------
# MEMORY LIMITS (QT-009)
# -----------------------------
# The 20 MB upload cap bounds file SIZE, not memory: a 1 MB JPEG can be 80
# megapixels, and a 0.5 MB PDF can have 300 pages or a poster-sized page.
# Decoding costs roughly 9-13 bytes per pixel at peak (measured with
# scripts/measure_memory.py), so these are pixel budgets. The defaults keep a
# single request under about 400 MB on a 512 MB instance; raise them with the
# environment variables if the Render plan has more RAM.

def _megapixels_from_env(name, default):
    try:
        value = float(os.environ.get(name, default))
    except (TypeError, ValueError):
        value = float(default)
    return max(1.0, value)


MAX_IMAGE_MEGAPIXELS = _megapixels_from_env("MAX_IMAGE_MEGAPIXELS", 30)        # photos we fully decode
MAX_PDF_RENDER_MEGAPIXELS = _megapixels_from_env("MAX_PDF_RENDER_MEGAPIXELS", 30)  # one rendered PDF page
MAX_WORD_IMAGE_MEGAPIXELS = _megapixels_from_env("MAX_WORD_IMAGE_MEGAPIXELS", 20)  # all page images in a PDF -> Word


@app.context_processor
def limits_context():
    """The enforced limits, for the templates that state them."""
    return {"max_image_megapixels": int(MAX_IMAGE_MEGAPIXELS),
            "max_word_image_megapixels": int(MAX_WORD_IMAGE_MEGAPIXELS)}


def image_too_large_message(name, width, height):
    """None if a width x height image is within MAX_IMAGE_MEGAPIXELS, else a user-facing error."""
    megapixels = width * height / 1_000_000
    if megapixels <= MAX_IMAGE_MEGAPIXELS:
        return None
    return (f"\"{name}\" is about {megapixels:.0f} megapixels ({width} \u00d7 {height} px), more than the "
            f"{MAX_IMAGE_MEGAPIXELS:.0f}-megapixel limit for this tool. Please make the picture smaller first, "
            f"for example by resizing it in your phone's or computer's photo editor, and try again.")


def render_matrix(width, height, zoom=2):
    """A fitz.Matrix scaling by `zoom`, reduced only when the rendered page would exceed
    MAX_PDF_RENDER_MEGAPIXELS. Ordinary pages (A4 at 2x is about 2 MP) are never affected."""
    pixels = width * height * zoom * zoom
    limit = MAX_PDF_RENDER_MEGAPIXELS * 1_000_000
    if pixels > limit:
        zoom *= (limit / pixels) ** 0.5
    return fitz.Matrix(zoom, zoom)


def pdf_image_megapixels(path):
    """Total pixels of all images placed on the pages of a PDF (read from its metadata, no decoding)."""
    with fitz.open(path) as doc:
        total = 0
        for page_index in range(len(doc)):
            for image in doc.get_page_images(page_index):
                total += image[2] * image[3]
    return total / 1_000_000


def release_pdfplumber_page(page):
    """Free what pdfplumber caches per page. Without this a 300-page PDF holds ~2.3 MB per page
    (about 750 MB) until the request ends; with it the same request stays under 70 MB."""
    close = getattr(page, "close", None) or getattr(page, "flush_cache", None)
    if close:
        close()


def delete_file_later(file_path, delay=300):
    def delete():
        time.sleep(delay)
        if os.path.exists(file_path):
            os.remove(file_path)

    threading.Thread(target=delete, daemon=True).start()


def save_upload(file_storage, delay=300):
    """Save an upload under a UUID-prefixed safe name. Returns (path, name)."""
    safe = secure_filename(file_storage.filename) or "file"
    name = f"{uuid.uuid4()}_{safe}"
    path = os.path.join(UPLOAD_FOLDER, name)
    file_storage.save(path)
    delete_file_later(path, delay=delay)
    return path, name


# Accepted extensions, compared against filename.lower().
WORD_EXTENSIONS = (".doc", ".docx", ".odt")
EXCEL_EXTENSIONS = (".xlsx", ".xlsm", ".xls")


def upload_stem(file_storage):
    """User-facing base name (no extension) of an upload, for download names."""
    safe = secure_filename(file_storage.filename) or "file"
    return os.path.splitext(safe)[0] or "file"


def resolve_upload(name):
    """Map a client-supplied upload name to a path inside UPLOAD_FOLDER, or None."""
    if not name:
        return None
    safe = secure_filename(name)
    if not safe or safe != name:
        return None
    path = os.path.realpath(os.path.join(UPLOAD_FOLDER, safe))
    root = os.path.realpath(UPLOAD_FOLDER)
    if not path.startswith(root + os.sep) or not os.path.isfile(path):
        return None
    return path


def flatten_on_white(img):
    """RGB copy of img with any transparency composited onto white.

    Image.convert("RGB") alone drops alpha without compositing, so
    transparent pixels keep whatever colour is stored under them (usually
    black).
    """
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.getchannel("A"))
        return flat
    return img.convert("RGB")


def images_to_pdf(files, output_path):
    """Build a PDF with one page per uploaded image, sized to the image's pixels.

    JPEGs are embedded byte-for-byte, so they are not re-compressed. Every
    other format is flattened onto white and embedded losslessly (PNG/Flate).
    Returns an error message, or None on success.
    """
    doc = fitz.open()
    try:
        for file in files:
            if not file.filename:
                continue
            path, _ = save_upload(file)
            try:
                with Image.open(path) as img:
                    width, height = img.size
                    if img.format == "JPEG" and img.mode in ("RGB", "L"):
                        # Embedded byte-for-byte, so it doesn't need a full decode. Decoding at 1/8
                        # scale still reads the whole stream (so a truncated file is caught) for
                        # about 1/64 of the memory.
                        img.draft(img.mode, (max(1, width // 8), max(1, height // 8)))
                        img.load()
                        with open(path, "rb") as f:
                            data = f.read()
                    else:
                        too_big = image_too_large_message(secure_filename(file.filename), width, height)
                        if too_big:
                            return too_big
                        img.load()
                        buf = io.BytesIO()
                        flatten_on_white(img).save(buf, "PNG")
                        data = buf.getvalue()
            except (OSError, ValueError):
                return f"\"{secure_filename(file.filename)}\" isn't an image we can read. Please upload JPG or PNG files."
            page = doc.new_page(width=width, height=height)
            page.insert_image(page.rect, stream=data)

        if len(doc) == 0:
            return "No images selected. Please choose at least one image."
        doc.save(output_path, deflate=True)
    finally:
        doc.close()
    return None


@app.template_filter("longdate")
def longdate(iso_date):
    """'2026-04-28' -> 'April 28, 2026' for visible bylines."""
    d = datetime.date.fromisoformat(iso_date)
    return f"{d:%B} {d.day}, {d.year}"


IMAGE_TOOL_PATHS = {"/resize-image", "/compress-jpg", "/remove-background"}


@app.context_processor
def breadcrumb_context():
    """Expose breadcrumb_trail(label) to templates: Home > section > page.

    A page opts in with {% set breadcrumb_label = "..." %}; base.html renders
    the visible trail and the matching BreadcrumbList JSON-LD.
    """
    def breadcrumb_trail(label):
        path = request.path
        trail = [{"label": "Home", "url": "/"}]
        if path.startswith(("/how-to-", "/blog/")):
            trail.append({"label": "Guides", "url": "/blog"})
        elif path in IMAGE_TOOL_PATHS:
            trail.append({"label": "Image Tools", "url": "/image-tools"})
        elif path not in ("/pdf-tools", "/image-tools", "/blog"):
            trail.append({"label": "PDF Tools", "url": "/pdf-tools"})
        trail.append({"label": label, "url": path})
        return trail

    return {"breadcrumb_trail": breadcrumb_trail}


def error_page(message, status=400):
    """Styled error response, instead of a bare string on a blank page."""
    return render_template("error.html", message=message, status=status), status


# -----------------------------
# REDACT PDF HELPERS
# -----------------------------

def _render_pdf_page_preview(doc, page_index):
    """Render one PDF page to a JPEG in static/ for the redact-pdf editor preview."""
    page = doc[page_index]
    pix = page.get_pixmap(matrix=render_matrix(page.rect.width, page.rect.height))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    preview_name = f"{uuid.uuid4()}.jpg"
    preview_path = os.path.join("static", preview_name)
    img.save(preview_path, "JPEG")

    delete_file_later(preview_path, delay=600)
    return preview_name


def _apply_pdf_redactions(doc, areas):
    """Permanently black out / whiteout / blur / pixelate the given areas.

    `areas` is a list of dicts (page, x, y, width, height, style, imgWidth,
    imgHeight) in browser-preview pixel space; coordinates are scaled to
    each page's PDF space before being applied.
    """
    by_page = {}
    for area in areas:
        try:
            page_num = int(area.get("page", 1))
            x = float(area["x"])
            y = float(area["y"])
            w = float(area["width"])
            h = float(area["height"])
            img_w = float(area.get("imgWidth") or 1)
            img_h = float(area.get("imgHeight") or 1)
            style = area.get("style", "black")
        except (KeyError, TypeError, ValueError):
            continue

        if style not in ("black", "white", "blur", "pixelate"):
            style = "black"
        if w <= 0 or h <= 0 or img_w <= 0 or img_h <= 0:
            continue

        by_page.setdefault(page_num, []).append((x, y, w, h, img_w, img_h, style))

    for page_num, rects in by_page.items():
        if page_num < 1 or page_num > len(doc):
            continue
        page = doc[page_num - 1]
        pdf_w, pdf_h = page.rect.width, page.rect.height

        pdf_rects = []
        for (x, y, w, h, img_w, img_h, style) in rects:
            scale_x = pdf_w / img_w
            scale_y = pdf_h / img_h
            rect = fitz.Rect(x * scale_x, y * scale_y, (x + w) * scale_x, (y + h) * scale_y)
            rect = rect & page.rect
            if rect.is_empty or rect.width <= 0 or rect.height <= 0:
                continue
            pdf_rects.append((rect, style))

        # Render blur/pixelate regions BEFORE redacting — apply_redactions()
        # strips the underlying content, so the source pixels must be
        # captured first.
        pending_images = []
        for rect, style in pdf_rects:
            if style not in ("blur", "pixelate"):
                continue
            pix = page.get_pixmap(matrix=render_matrix(rect.width, rect.height, zoom=3), clip=rect)
            region = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            if style == "blur":
                region = region.filter(ImageFilter.GaussianBlur(radius=10))
            else:
                factor = 14
                small = region.resize(
                    (max(1, region.width // factor), max(1, region.height // factor)),
                    Image.NEAREST,
                )
                region = small.resize(region.size, Image.NEAREST)
            buf = io.BytesIO()
            region.save(buf, format="PNG")
            pending_images.append((rect, buf.getvalue()))

        for rect, style in pdf_rects:
            fill = (0, 0, 0) if style == "black" else (1, 1, 1)
            page.add_redact_annot(rect, fill=fill)

        if pdf_rects:
            page.apply_redactions()

        for rect, image_bytes in pending_images:
            page.insert_image(rect, stream=image_bytes)


# -----------------------------
# PDF COMPRESSION ENGINE
# -----------------------------

# Ghostscript flag sets per level, ordered from lightest to most aggressive.
# Reused both for single-pass compression and for the target-size best-effort loop.
COMPRESSION_PRESETS = {
    "low": [
        # Minimal — preserve quality, just re-optimise structure
        "-dPDFSETTINGS=/prepress",
    ],
    "medium": [
        # Balanced — 120 DPI, downsample everything above target
        "-dPDFSETTINGS=/ebook",
        "-dDownsampleColorImages=true",
        "-dColorImageDownsampleType=/Bicubic",
        "-dColorImageResolution=120",
        "-dColorImageDownsampleThreshold=1.0",
        "-dDownsampleGrayImages=true",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dGrayImageResolution=120",
        "-dGrayImageDownsampleThreshold=1.0",
    ],
    "high": [
        # 72 DPI, downsample everything, force JPEG
        "-dPDFSETTINGS=/screen",
        "-dDownsampleColorImages=true",
        "-dColorImageDownsampleType=/Bicubic",
        "-dColorImageResolution=72",
        "-dColorImageDownsampleThreshold=1.0",
        "-dDownsampleGrayImages=true",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dGrayImageResolution=72",
        "-dGrayImageDownsampleThreshold=1.0",
        "-dDownsampleMonoImages=true",
        "-dMonoImageResolution=150",
        "-dMonoImageDownsampleThreshold=1.0",
        "-dAutoFilterColorImages=false",
        "-dColorImageFilter=/DCTEncode",
        "-dAutoFilterGrayImages=false",
        "-dGrayImageFilter=/DCTEncode",
    ],
    "extreme": [
        # Maximum — 50 DPI + convert to grayscale (huge reduction for colour PDFs)
        "-dPDFSETTINGS=/screen",
        "-dDownsampleColorImages=true",
        "-dColorImageDownsampleType=/Bicubic",
        "-dColorImageResolution=50",
        "-dColorImageDownsampleThreshold=1.0",
        "-dDownsampleGrayImages=true",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dGrayImageResolution=50",
        "-dGrayImageDownsampleThreshold=1.0",
        "-dDownsampleMonoImages=true",
        "-dMonoImageResolution=100",
        "-dMonoImageDownsampleThreshold=1.0",
        "-sColorConversionStrategy=Gray",
        "-dProcessColorModel=/DeviceGray",
    ],
}

EMAIL_OPT_FLAGS = [
    "-dPDFSETTINGS=/screen",
    "-dDownsampleColorImages=true",
    "-dColorImageDownsampleType=/Bicubic",
    "-dColorImageResolution=72",
    "-dColorImageDownsampleThreshold=1.0",
    "-dDownsampleGrayImages=true",
    "-dGrayImageDownsampleType=/Bicubic",
    "-dGrayImageResolution=72",
    "-dGrayImageDownsampleThreshold=1.0",
]

# Order to escalate through when chasing a target file size (lightest to strongest).
TARGET_SIZE_LEVEL_ORDER = ["low", "medium", "high", "extreme"]

# JPEG re-encode quality per level -- mirrors the Low/Medium/High/Extreme
# naming used by the PDF compressor, for one consistent mental model.
JPG_COMPRESSION_QUALITY = {
    "low": 90,
    "medium": 75,
    "high": 60,
    "extreme": 40,
}


def _run_ghostscript(extra_flags, input_path, temp_output):
    gs_command = "gswin64c" if platform.system() == "Windows" else "gs"

    base_flags = [
        gs_command,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dSubsetFonts=true",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
    ]

    command = base_flags + extra_flags + [f"-sOutputFile={temp_output}", input_path]
    subprocess.run(command, check=True)


def compress_pdf(input_path, output_path, level="medium", target_size=None, email_opt=False):

    temp_output = output_path + ".tmp"
    meta_path = output_path + ".meta.json"

    target_bytes = None
    if target_size:
        try:
            target_bytes = float(target_size) * 1024 * 1024
        except (TypeError, ValueError):
            target_bytes = None

    try:
        if target_bytes:
            # Best-effort loop: escalate through presets until we're under the
            # target, or we run out of presets — an exact target can't always
            # be guaranteed (e.g. a dense scanned page has a size floor).
            attempts = []
            target_met = False
            final_level = None

            for candidate_level in TARGET_SIZE_LEVEL_ORDER:
                _run_ghostscript(COMPRESSION_PRESETS[candidate_level], input_path, temp_output)
                size = os.path.getsize(temp_output)
                attempts.append({"level": candidate_level, "size_bytes": size})
                final_level = candidate_level

                if size <= target_bytes:
                    target_met = True
                    break

            os.replace(temp_output, output_path)

            meta = {
                "target_requested_bytes": target_bytes,
                "target_met": target_met,
                "final_level": final_level,
                "final_size_bytes": os.path.getsize(output_path),
                "attempts": attempts,
            }
            with open(meta_path, "w") as f:
                json.dump(meta, f)

        else:
            extra = EMAIL_OPT_FLAGS if email_opt else COMPRESSION_PRESETS.get(level, COMPRESSION_PRESETS["medium"])
            _run_ghostscript(extra, input_path, temp_output)
            os.replace(temp_output, output_path)

    except Exception as e:
        print("Compression ERROR:", e)

        # Leave a marker /status can report, so processing.html stops polling.
        if isinstance(e, FileNotFoundError):  # Ghostscript not installed
            message = "Compression is temporarily unavailable. Please try again later."
        else:
            message = "We couldn't compress this PDF. It may be damaged or password-protected."

        if os.path.exists(temp_output):
            os.remove(temp_output)

        error_path = output_path + ".error"
        with open(error_path, "w") as f:
            f.write(message)
        delete_file_later(error_path, delay=600)


# -----------------------------
# HOMEPAGE
# -----------------------------

@app.route("/")
def index():
    return render_template("index.html")


# -----------------------------
# COMPRESS PDF PAGE
# -----------------------------

@app.route("/compress-pdf", methods=["GET", "POST"])
def compress_pdf_page():

    if request.method == "POST":

        if "pdf" not in request.files:
            return error_page("No file uploaded")

        file = request.files["pdf"]

        if file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        # 🔐 SAFE NAME
        filename = secure_filename(file.filename)

        unique_id = str(uuid.uuid4())

        input_filename = f"{unique_id}_{filename}"
        output_filename = f"{unique_id}_compressed_{filename}"

        input_path = os.path.join(UPLOAD_FOLDER, input_filename)
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        file.save(input_path)

        # ✅ GET OPTIONS FROM UI
        level = request.form.get("level", "medium")
        target_size = request.form.get("target_size")  # optional
        email_opt = request.form.get("email_opt") == "1"

        # 🧠 DEBUG (optional but useful)
        print("Compression settings:", level, target_size, email_opt)

        # 🚀 RUN IN BACKGROUND
        threading.Thread(
            target=compress_pdf,
            args=(input_path, output_path, level, target_size, email_opt),
            daemon=True
        ).start()

        # ⏱ CLEANUP (AFTER some time)
        delete_file_later(input_path, delay=300)
        delete_file_later(output_path, delay=600)

        # 🔄 REDIRECT TO PROCESSING PAGE
        return render_template(
            "processing.html",
            file_name=output_filename
        )

    return render_template("compress_pdf.html")


# -----------------------------
# DOWNLOAD RESULT PAGE
# -----------------------------

@app.route("/download/<filename>")
def download(filename):

    filename = secure_filename(filename)
    compressed_path = os.path.join(UPLOAD_FOLDER, filename)

    if not os.path.exists(compressed_path):
        return error_page("File not ready", 404)

    original_name = filename.replace("_compressed_", "_")
    original_path = os.path.join(UPLOAD_FOLDER, original_name)

    if os.path.exists(original_path):

        original_size = os.path.getsize(original_path)
        compressed_size = os.path.getsize(compressed_path)

        original_mb = round(original_size / (1024 * 1024), 2)
        compressed_mb = round(compressed_size / (1024 * 1024), 2)

        reduction = round((1 - compressed_size / original_size) * 100, 1)

    else:
        original_mb = "-"
        compressed_mb = "-"
        reduction = "-"

    # If compression was run with a target size, surface whether it was hit.
    target_info = None
    meta_path = compressed_path + ".meta.json"

    if os.path.exists(meta_path):
        try:
            with open(meta_path) as f:
                meta = json.load(f)

            target_info = {
                "met": meta.get("target_met"),
                "target_mb": round(meta.get("target_requested_bytes", 0) / (1024 * 1024), 2),
            }
        except (ValueError, OSError):
            target_info = None

        delete_file_later(meta_path, delay=600)

    return render_template(
        "result.html",
        file_name=filename,
        original_size=original_mb,
        compressed_size=compressed_mb,
        reduction=reduction,
        target_info=target_info,
    )


@app.route("/download-file/<filename>")
def download_file(filename):

    safe_filename = secure_filename(filename)
    path = os.path.join(UPLOAD_FOLDER, safe_filename)

    if not os.path.exists(path):
        return error_page("File not found", 404)

    response = send_file(path, as_attachment=True)
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@app.route("/status/<filename>")
def status(filename):

    filename = secure_filename(filename)
    path = os.path.join(UPLOAD_FOLDER, filename)

    if os.path.exists(path):
        return {"ready": True}

    error_path = path + ".error"
    if os.path.exists(error_path):
        with open(error_path) as f:
            return {"ready": False, "error": f.read()}

    return {"ready": False}


@app.route("/merge-pdf", methods=["GET", "POST"])
def merge_pdf():

    if request.method == "POST":

        files = request.files.getlist("pdfs")

        merger = PdfMerger()

        unique_id = str(uuid.uuid4())
        output_filename = f"{unique_id}_merged.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        appended = 0

        for file in files:

            if file.filename != "":
                filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
                path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(path)
                delete_file_later(path)


                merger.append(path)
                appended += 1

        if not appended:
            merger.close()
            return error_page("No PDFs selected. Please choose the files you want to merge.")

        merger.write(output_path)
        merger.close()
        delete_file_later(output_path)

        return send_file(output_path, as_attachment=True)

    return render_template("merge.html")


@app.errorhandler(413)
def too_large(e):
    return render_template("413.html"), 413

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500

@app.errorhandler(400)
def bad_request(e):
    return error_page("Something was missing from that request. Please choose your file and try again.")

# Corrupt / non-PDF uploads raise from the PDF libraries deep inside a route.
@app.errorhandler(fitz.FileDataError)
@app.errorhandler(fitz.EmptyFileError)
@app.errorhandler(PdfReadError)
@app.errorhandler(PDFSyntaxError)
def invalid_pdf(e):
    return error_page("That file doesn't look like a valid PDF. It may be damaged — please try a different file.")


@app.route("/split-pdf", methods=["GET", "POST"])
def split_pdf():

    if request.method == "POST":

        file = request.files["pdf"]

        if not file or file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)

        reader = PdfReader(input_path)

        output_files = []

        for i, page in enumerate(reader.pages):

            writer = PdfWriter()
            writer.add_page(page)

            output_filename = f"{uuid.uuid4()}_page_{i+1}.pdf"
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)

            with open(output_path, "wb") as output_file:
                writer.write(output_file)

            output_files.append(output_filename)
            delete_file_later(output_path)

        return render_template("split_result.html", files=output_files)

    return render_template("split.html")


@app.route("/jpg-to-pdf", methods=["GET", "POST"])
def jpg_to_pdf():
    from PIL import Image

    if request.method == "POST":

        unique_id = str(uuid.uuid4())
        output_filename = f"{unique_id}_images.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        error = images_to_pdf(request.files.getlist("images"), output_path)

        if error:
            return error_page(error)

        delete_file_later(output_path)

        return send_file(output_path, as_attachment=True, download_name="images.pdf")

    return render_template("jpg_to_pdf.html")

@app.route("/pdf-to-png", methods=["GET", "POST"])
def pdf_to_png():

    import fitz  # PyMuPDF
    from PIL import Image

    if request.method == "POST":

        file = request.files.get("pdf")

        if not file or file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        input_path, _ = save_upload(file)

        doc = fitz.open(input_path)

        image_files = []
        MAX_PAGES = 20

        for page_index in range(len(doc)):

            if page_index >= MAX_PAGES:
                break

            page = doc[page_index]

            pix = page.get_pixmap(matrix=render_matrix(page.rect.width, page.rect.height))

            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            output_filename = f"{uuid.uuid4()}_page_{page_index+1}.png"
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)

            img.save(output_path, "PNG")

            image_files.append(output_filename)

            delete_file_later(output_path)

        doc.close()

        # CREATE ZIP
        zip_filename = f"{uuid.uuid4()}_png_images.zip"
        zip_path = os.path.join(UPLOAD_FOLDER, zip_filename)

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for image in image_files:
                image_path = os.path.join(UPLOAD_FOLDER, image)
                zipf.write(image_path, arcname=image.split("_", 1)[1])

        delete_file_later(zip_path)

        return render_template(
            "pdf_to_png_result.html",
            images=image_files,
            zip_file=zip_filename,
            total=len(image_files)
        )
    
    return render_template("pdf_to_png.html")



@app.route("/rotate-pdf", methods=["GET", "POST"])
def rotate_pdf():

    if request.method == "POST":

        file = request.files["pdf"]

        if not file or file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        try:
            rotation = int(request.form.get("rotation", 0)) % 360
        except (ValueError, TypeError):
            return error_page("Please choose a rotation of 90, 180 or 270 degrees.")

        if rotation % 90:
            return error_page("Please choose a rotation of 90, 180 or 270 degrees.")

        filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)


        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            page.rotate(rotation)
            writer.add_page(page)

        output_filename = f"{uuid.uuid4()}_rotated.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        with open(output_path, "wb") as output_file:
            writer.write(output_file)

        return send_file(output_path, as_attachment=True)

    return render_template("rotate_pdf.html")

@app.route("/delete-pdf-pages", methods=["GET", "POST"])
def delete_pdf_pages():

    if request.method == "POST":

        file = request.files["pdf"]
        pages_to_delete = request.form.get("pages", "").strip()

        if file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        if not pages_to_delete:
            return error_page("Please enter page numbers to delete (e.g. 2,5,7)")

        filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)

        reader = PdfReader(input_path)
        writer = PdfWriter()

        try:
            delete_pages = [int(p.strip()) - 1 for p in pages_to_delete.split(",") if p.strip()]
        except ValueError:
            return error_page("Invalid page numbers. Use format: 2,5,7")

        for i, page in enumerate(reader.pages):

            if i not in delete_pages:
                writer.add_page(page)

        output_filename = f"{uuid.uuid4()}_edited.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        with open(output_path, "wb") as output_file:
            writer.write(output_file)

        return send_file(output_path, as_attachment=True)

    return render_template("delete_pages.html")

@app.route("/pdf-to-word", methods=["GET", "POST"])
def pdf_to_word():
    from pdf2docx import Converter

    if request.method == "POST":

        file = request.files["pdf"]

        if file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        if not file.filename.lower().endswith(".pdf"):
            return error_page("Please upload a PDF file.")

        input_path, _ = save_upload(file)
        stem = upload_stem(file)

        megapixels = pdf_image_megapixels(input_path)
        if megapixels > MAX_WORD_IMAGE_MEGAPIXELS:
            return error_page(
                f"This PDF is mostly large page images (about {megapixels:.0f} megapixels in total), more than the "
                f"{MAX_WORD_IMAGE_MEGAPIXELS:.0f} megapixels we can convert in one go. Scanned pages come out as pictures "
                f"in the Word file, not editable text, so try splitting the PDF into smaller parts first, or use "
                f"Compress PDF to shrink the images.")

        output_filename = f"{uuid.uuid4()}_{stem}.docx"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        cv = Converter(input_path)
        cv.convert(output_path, start=0, end=None)
        cv.close()

        return send_file(output_path, as_attachment=True, download_name=f"{stem}.docx")

    return render_template("pdf_to_word.html")


@app.route("/word-to-pdf", methods=["GET", "POST"])
def word_to_pdf():

    if request.method == "POST":

        file = request.files["docx"]

        if file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        if not file.filename.lower().endswith(WORD_EXTENSIONS):
            return error_page("Please upload a Word document (.doc, .docx or .odt).")

        input_path, input_name = save_upload(file)
        stem = upload_stem(file)

        # LibreOffice names its output after the input, with the extension swapped.
        output_filename = os.path.splitext(input_name)[0] + ".pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        office_command = "soffice" if platform.system() == "Windows" else "libreoffice"

        try:
            result = subprocess.run([
                office_command,
                "--headless",
                "--convert-to",
                "pdf",
                input_path,
                "--outdir",
                UPLOAD_FOLDER
            ])
        except OSError:
            return error_page("Word conversion is temporarily unavailable. Please try again later.", 503)

        if result.returncode != 0 or not os.path.exists(output_path):
            return error_page("Conversion failed. Make sure your file is a valid Word document.")

        return send_file(output_path, as_attachment=True, download_name=f"{stem}.pdf")

    return render_template("word_to_pdf.html")

@app.route("/protect-pdf", methods=["GET", "POST"])
def protect_pdf():

    if request.method == "POST":

        file = request.files["pdf"]
        password = request.form.get("password")

        if file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        if not password:
            return error_page("Please enter a password.")

        input_path, _ = save_upload(file)
        stem = upload_stem(file)

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt(password)

        output_filename = f"{uuid.uuid4()}_protected.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True, download_name=f"protected_{stem}.pdf")

    return render_template("protect_pdf.html")

@app.route("/unlock-pdf", methods=["GET", "POST"])
def unlock_pdf():

    if request.method == "POST":

        file = request.files["pdf"]
        password = request.form.get("password")

        if file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        input_path, _ = save_upload(file)
        stem = upload_stem(file)

        reader = PdfReader(input_path)

        if reader.is_encrypted:
            try:
                decrypted = reader.decrypt(password or "")
            except Exception:
                decrypted = 0
            if not decrypted:
                return error_page("Incorrect password.")

        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        output_filename = f"{uuid.uuid4()}_unlocked.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True, download_name=f"unlocked_{stem}.pdf")

    return render_template("unlock_pdf.html")

@app.route("/add-page-numbers", methods=["GET", "POST"])
def add_page_numbers():
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    if request.method == "POST":

        file = request.files["pdf"]

        if file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        input_path, _ = save_upload(file)
        stem = upload_stem(file)

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for i, page in enumerate(reader.pages):

            packet = io.BytesIO()

            c = canvas.Canvas(packet, pagesize=letter)

            page_number = f"{i+1}"

            c.drawString(500, 20, page_number)

            c.save()

            packet.seek(0)

            overlay = PdfReader(packet)
            page.merge_page(overlay.pages[0])

            writer.add_page(page)

        output_filename = f"{uuid.uuid4()}_numbered.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True, download_name=f"numbered_{stem}.pdf")

    return render_template("add_page_numbers.html")

@app.route("/pdf-tools")
def pdf_tools():
    return render_template("pdf_tools.html")

@app.route("/image-tools")
def image_tools():
    return render_template("image_tools.html")

@app.route("/sitemap.xml")
def sitemap():
    return send_file("sitemap.xml", mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    return send_file("robots.txt")


@app.route("/convert-pdf")
def convert_pdf():
    return render_template("convert_pdf.html")

@app.route("/edit-pdf")
def edit_pdf():
    return render_template("edit_pdf.html")

@app.route("/organize-pdf")
def organize_pdf():
    return render_template("organize_pdf.html")

@app.route("/blog")
def blog():
    return render_template("blog.html")


@app.route("/blog/pdf-file-size-explained")
def blog_pdf_file_size_explained():
    return render_template("blog/pdf_file_size_explained.html")


@app.route("/blog/pdf-security-basics")
def blog_pdf_security_basics():
    return render_template("blog/pdf_security_basics.html")


@app.route("/blog/prepare-pdf-for-job-application")
def blog_prepare_pdf_for_job_application():
    return render_template("blog/prepare_pdf_for_job_application.html")


@app.route("/blog/send-large-pdf-when-email-fails")
def blog_send_large_pdf_when_email_fails():
    return render_template("blog/send_large_pdf_when_email_fails.html")


@app.route("/blog/how-to-resize-images-for-social-media")
def blog_how_to_resize_images_for_social_media():
    return render_template("blog/how_to_resize_images_for_social_media.html")


@app.route("/blog/instagram-image-sizes-guide")
def blog_instagram_image_sizes_guide():
    return render_template("blog/instagram_image_sizes_guide.html")


@app.route("/blog/png-vs-jpg-guide")
def blog_png_vs_jpg_guide():
    return render_template("blog/png_vs_jpg_guide.html")


@app.route("/blog/optimize-images-for-web")
def blog_optimize_images_for_web():
    return render_template("blog/optimize_images_for_web.html")


@app.route("/blog/how-to-remove-image-background")
def blog_how_to_remove_image_background():
    return render_template("blog/how_to_remove_image_background.html")


@app.route("/blog/scanned-documents-to-pdf")
def blog_scanned_documents_to_pdf():
    return render_template("blog/scanned_documents_to_pdf.html")


@app.route("/blog/why-pdf-to-word-conversion-looks-wrong")
def blog_why_pdf_to_word_conversion_looks_wrong():
    return render_template("blog/why_pdf_to_word_conversion_looks_wrong.html")


@app.route("/blog/why-compress-pdf-barely-shrinks-some-files")
def blog_why_compress_pdf_barely_shrinks_some_files():
    return render_template("blog/why_compress_pdf_barely_shrinks_some_files.html")


@app.route("/blog/why-remove-background-leaves-rough-edges")
def blog_why_remove_background_leaves_rough_edges():
    return render_template("blog/why_remove_background_leaves_rough_edges.html")


@app.route("/blog/resizing-vs-compressing-an-image")
def blog_resizing_vs_compressing_an_image():
    return render_template("blog/resizing_vs_compressing_an_image.html")


@app.route("/blog/why-jpg-to-pdf-has-a-huge-page-size")
def blog_why_jpg_to_pdf_has_a_huge_page_size():
    return render_template("blog/why_jpg_to_pdf_has_a_huge_page_size.html")


@app.route("/blog/what-encryption-does-protect-pdf-use")
def blog_what_encryption_does_protect_pdf_use():
    return render_template("blog/what_encryption_does_protect_pdf_use.html")


@app.route("/blog/electronic-signature-vs-digital-signature")
def blog_electronic_signature_vs_digital_signature():
    return render_template("blog/electronic_signature_vs_digital_signature.html")


@app.route("/blog/fill-pdf-with-no-form-fields")
def blog_fill_pdf_with_no_form_fields():
    return render_template("blog/fill_pdf_with_no_form_fields.html")


@app.route("/blog/svg-to-pdf-arrows-markers-disappear")
def blog_svg_to_pdf_arrows_markers_disappear():
    return render_template("blog/svg_to_pdf_arrows_markers_disappear.html")


@app.route("/how-to-compress-pdf")
def compress_pdf_guide():
    return render_template("compress_pdf_guide.html")


@app.route("/how-to-merge-pdf")
def merge_pdf_guide():
    return render_template("merge_pdf_guide.html")


@app.route("/how-to-split-pdf")
def split_pdf_guide():
    return render_template("split_pdf_guide.html")

@app.route("/how-to-jpg-to-pdf")
def jpg_to_pdf_guide():
    return render_template("jpg_to_pdf_guide.html")


@app.route("/how-to-pdf-to-jpg")
def pdf_to_jpg_guide():
    return render_template("pdf_to_jpg_guide.html")


@app.route("/compress-jpg", methods=["GET", "POST"])
def compress_jpg():

    if request.method == "POST":

        files = request.files.getlist("images")
        level = request.form.get("level", "medium")
        quality = JPG_COMPRESSION_QUALITY.get(level, 75)

        results = []
        compressed_paths = []
        total_original = 0
        total_compressed = 0

        for file in files:

            if not file.filename:
                continue
            if not file.filename.lower().endswith((".jpg", ".jpeg")):
                continue

            display_name = secure_filename(file.filename)
            input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{display_name}")
            file.save(input_path)
            delete_file_later(input_path, delay=60)

            original_size = os.path.getsize(input_path)

            output_name = f"{uuid.uuid4()}_{display_name}"
            output_path = os.path.join(UPLOAD_FOLDER, output_name)

            try:
                img = Image.open(input_path)
                too_big = image_too_large_message(display_name, img.width, img.height)
                if too_big:
                    return error_page(too_big)
                img = ImageOps.exif_transpose(img)  # bake in orientation before EXIF is stripped
                img = img.convert("RGB")
                img.save(output_path, "JPEG", quality=quality, optimize=True)
            except Exception:
                continue

            compressed_size = os.path.getsize(output_path)
            delete_file_later(output_path)

            total_original += original_size
            total_compressed += compressed_size

            reduction = round((1 - compressed_size / original_size) * 100, 1) if original_size else 0

            results.append({
                "filename": output_name,
                "display_name": display_name,
                "original_kb": round(original_size / 1024, 1),
                "compressed_kb": round(compressed_size / 1024, 1),
                "reduction": reduction,
            })
            compressed_paths.append(output_path)

        if not results:
            return error_page("No valid JPG files were uploaded.")

        zip_filename = f"{uuid.uuid4()}_compressed_jpgs.zip"
        zip_path = os.path.join(UPLOAD_FOLDER, zip_filename)

        with zipfile.ZipFile(zip_path, "w") as zipf:
            for r, p in zip(results, compressed_paths):
                zipf.write(p, arcname=r["display_name"])

        delete_file_later(zip_path)

        total_reduction = round((1 - total_compressed / total_original) * 100, 1) if total_original else 0

        return render_template(
            "compress_jpg_result.html",
            results=results,
            zip_file=zip_filename,
            total_original_kb=round(total_original / 1024, 1),
            total_compressed_kb=round(total_compressed / 1024, 1),
            total_reduction=total_reduction,
        )

    return render_template("compress_jpg.html")


@app.route("/how-to-compress-jpg")
def compress_jpg_guide():
    return render_template("compress_jpg_guide.html")


def _letterbox_resize(img, target_w, target_h):
    """Scale img to fit entirely within (target_w, target_h), preserving
    aspect ratio, and center it on a white canvas of that exact size --
    pads with white bars, never crops or stretches.
    """
    img = ImageOps.exif_transpose(img)

    img_ratio = img.width / img.height
    target_ratio = target_w / target_h

    if img_ratio > target_ratio:
        new_w = target_w
        new_h = max(1, round(target_w / img_ratio))
    else:
        new_h = target_h
        new_w = max(1, round(target_h * img_ratio))

    resized = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (target_w, target_h), (255, 255, 255))
    offset = ((target_w - new_w) // 2, (target_h - new_h) // 2)

    if resized.mode in ("RGBA", "LA") or (resized.mode == "P" and "transparency" in resized.info):
        resized = resized.convert("RGBA")
        canvas.paste(resized, offset, resized)
    else:
        canvas.paste(resized.convert("RGB"), offset)

    return canvas


@app.route("/resize-image", methods=["GET", "POST"])
def resize_image():

    if request.method == "POST":

        file = request.files.get("image")

        if not file or not file.filename:
            return error_page("No file selected. Please choose a file and try again.")

        try:
            width = max(1, min(int(request.form.get("width", 1080)), 4000))
            height = max(1, min(int(request.form.get("height", 1080)), 4000))
        except ValueError:
            width, height = 1080, 1080

        fmt = "jpg" if request.form.get("format") == "jpg" else "png"

        try:
            quality = max(50, min(int(request.form.get("quality", 90)), 100))
        except ValueError:
            quality = 90

        input_name = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{input_name}")
        file.save(input_path)
        delete_file_later(input_path, delay=60)

        try:
            img = Image.open(input_path)
        except Exception:
            return error_page("Could not read that image file.")

        too_big = image_too_large_message(input_name, img.width, img.height)
        if too_big:
            return error_page(too_big)

        try:
            img.load()
        except Exception:
            return error_page("Could not read that image file.")

        result = _letterbox_resize(img, width, height)

        output_name = f"{uuid.uuid4()}_resized.{fmt}"
        output_path = os.path.join(UPLOAD_FOLDER, output_name)

        if fmt == "jpg":
            result.save(output_path, "JPEG", quality=quality, optimize=True)
        else:
            result.save(output_path, "PNG", optimize=True)

        delete_file_later(output_path)

        return send_file(output_path, as_attachment=True)

    return render_template("resize_image.html")


@app.route("/how-to-resize-image")
def resize_image_guide():
    return render_template("resize_image_guide.html")


@app.route("/remove-background", methods=["GET", "POST"])
def remove_background():

    if request.method == "POST":

        file = request.files.get("image")

        if not file or not file.filename:
            return error_page("No file selected. Please choose a file and try again.")

        api_key = os.environ.get("REMOVE_BG_API_KEY")
        if not api_key:
            return error_page(
                "Background removal isn't configured on this server yet "
                "(missing REMOVE_BG_API_KEY).",
                503,
            )

        input_name = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{input_name}")
        file.save(input_path)
        delete_file_later(input_path, delay=60)

        try:
            with open(input_path, "rb") as f:
                response = requests.post(
                    "https://api.remove.bg/v1.0/removebg",
                    files={"image_file": f},
                    data={"size": "auto"},
                    headers={"X-Api-Key": api_key},
                    timeout=60,
                )
        except requests.RequestException:
            return error_page("Could not reach the background removal service. Please try again.", 502)

        if response.status_code != 200:
            return error_page("Could not remove the background from that image. Please try a different file.")

        output_name = f"{uuid.uuid4()}_no_bg.png"
        output_path = os.path.join(UPLOAD_FOLDER, output_name)

        with open(output_path, "wb") as f:
            f.write(response.content)

        delete_file_later(output_path)

        return send_file(output_path, as_attachment=True)

    return render_template("remove_background.html")


@app.route("/how-to-remove-background")
def remove_background_guide():
    return render_template("remove_background_guide.html")


@app.route("/how-to-rotate-pdf")
def rotate_pdf_guide():
    return render_template("rotate_pdf_guide.html")


@app.route("/how-to-delete-pdf-pages")
def delete_pages_guide():
    return render_template("delete_pages_guide.html")


@app.route("/how-to-protect-pdf")
def protect_pdf_guide():
    return render_template("protect_pdf_guide.html")


@app.route("/how-to-unlock-pdf")
def unlock_pdf_guide():
    return render_template("unlock_pdf_guide.html")


@app.route("/how-to-add-page-numbers")
def add_page_numbers_guide():
    return render_template("add_page_numbers_guide.html")

@app.route("/how-to-sign-pdf")
def sign_pdf_guide():
    return render_template("sign_pdf_guide.html")

@app.route("/how-to-word-to-pdf")
def word_to_pdf_guide():
    return render_template("word_to_pdf_guide.html")

@app.route("/how-to-pdf-to-word")
def pdf_to_word_guide():
    return render_template("pdf_to_word_guide.html")

@app.route("/compress-pdf-to-1mb")
def compress_pdf_1mb():
    return render_template("compress_pdf_to_1mb.html")



@app.route("/add-watermark", methods=["GET", "POST"])
def add_watermark():

    if request.method == "POST":

        file = request.files["pdf"]
        watermark_text = request.form.get("text")

        if file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        input_path, _ = save_upload(file)
        stem = upload_stem(file)

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:

            packet = io.BytesIO()

            c = canvas.Canvas(packet, pagesize=letter)

            c.setFont("Helvetica", 40)
            c.setFillGray(0.5, 0.3)

            c.drawString(150, 400, watermark_text)

            c.save()

            packet.seek(0)

            overlay = PdfReader(packet)

            page.merge_page(overlay.pages[0])

            writer.add_page(page)

        output_filename = f"{uuid.uuid4()}_watermarked.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True, download_name=f"watermarked_{stem}.pdf")

    return render_template("add_watermark.html")

# Visual signature of the watermark add_watermark() draws: Helvetica,
# 40pt, 50% gray at 30% opacity, with its text origin at PDF user-space
# (150, 400) -- all hardcoded there. Matching every one of these together
# (not any single attribute alone) is what keeps this from also matching
# ordinary document text; checked against a battery of near-miss cases
# (same position/size but opaque, same signature but a different position,
# etc.) before relying on this as the removal signature.
#
# The overlay is drawn on a Letter canvas but merged into pages of any
# size without scaling, so on a taller or shorter page it sits at a
# different distance from the top. The expected position is therefore
# mapped through each page's own transformation matrix, so it follows the
# page's height, crop box and rotation instead of assuming Letter.
WATERMARK_ORIGIN = (150.0, 400.0)


def _is_own_watermark_span(span, page):
    chars = span.get("chars")
    if not chars:
        return False
    expected = fitz.Point(*WATERMARK_ORIGIN) * page.transformation_matrix
    origin = chars[0][2]
    if abs(origin[0] - expected.x) > 1.5 or abs(origin[1] - expected.y) > 1.5:
        return False
    if span.get("font") != "Helvetica":
        return False
    if abs(span.get("size", 0) - 40.0) > 0.5:
        return False
    if abs(span.get("opacity", 1.0) - 0.3) > 0.05:
        return False
    color = span.get("color") or (0, 0, 0)
    if max(color) - min(color) > 0.02:  # must be neutral gray, not colored
        return False
    if abs(color[0] - 0.572) > 0.03:
        return False
    return True


@app.route("/remove-watermark", methods=["GET", "POST"])
def remove_watermark():

    if request.method == "POST":

        file = request.files["pdf"]

        if file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)

        output_filename = f"{uuid.uuid4()}_cleaned.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        doc = fitz.open(input_path)
        for page in doc:
            for span in page.get_texttrace():
                if _is_own_watermark_span(span, page):
                    page.add_redact_annot(fitz.Rect(span["bbox"]))
            page.apply_redactions()
            page.clean_contents()
        doc.save(output_path)
        doc.close()

        return send_file(output_path, as_attachment=True)

    return render_template("remove_watermark.html")

@app.route("/how-to-add-watermark-pdf")
def add_watermark_guide():
    return render_template("add_watermark_guide.html")


@app.route("/how-to-remove-watermark-pdf")
def remove_watermark_guide():
    return render_template("remove_watermark_guide.html")

@app.route("/extract-images", methods=["GET", "POST"])
def extract_images():

    import fitz  # PyMuPDF

    if request.method == "POST":

        file = request.files["pdf"]

        if file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        input_path, _ = save_upload(file)

        doc = fitz.open(input_path)

        images = []
        MAX_IMAGES = 50

        for page_index in range(len(doc)):

            page = doc[page_index]
            image_list = page.get_images(full=True)

            for img_index, img in enumerate(image_list):

                xref = img[0]
                base_image = doc.extract_image(xref)

                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                image_filename = f"{uuid.uuid4()}_page{page_index+1}_{img_index}.{image_ext}"
                image_path = os.path.join(UPLOAD_FOLDER, image_filename)

                with open(image_path, "wb") as img_file:
                    img_file.write(image_bytes)

                delete_file_later(image_path)
                images.append(image_filename)

                # ✅ LIMIT
                if len(images) >= MAX_IMAGES:
                    break

            if len(images) >= MAX_IMAGES:
                break

        doc.close()

        # ✅ SMART UX FLAG
        limit_reached = len(images) >= MAX_IMAGES

        return render_template(
            "extract_images_result.html",
            images=images,
            limit=limit_reached
        )

    return render_template("extract_images.html")

@app.route("/how-to-extract-images-from-pdf")
def extract_images_guide():
    return render_template("extract_images_guide.html")

@app.route("/pdf-to-jpg", methods=["GET", "POST"])
def pdf_to_jpg():

    import fitz  # PyMuPDF
    from PIL import Image

    if request.method == "POST":

        file = request.files.get("pdf")

        if not file or file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        input_path, _ = save_upload(file)

        doc = fitz.open(input_path)

        image_files = []
        MAX_PAGES = 20

        for page_index in range(len(doc)):

            if page_index >= MAX_PAGES:
                break

            page = doc[page_index]

            pix = page.get_pixmap(matrix=render_matrix(page.rect.width, page.rect.height))

            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            output_filename = f"{uuid.uuid4()}_page_{page_index+1}.jpg"
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)

            img.save(output_path, "JPEG", quality=90)

            image_files.append(output_filename)

            delete_file_later(output_path)

        doc.close()

        # CREATE ZIP
        zip_filename = f"{uuid.uuid4()}_jpg_images.zip"
        zip_path = os.path.join(UPLOAD_FOLDER, zip_filename)

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for image in image_files:
                image_path = os.path.join(UPLOAD_FOLDER, image)
                zipf.write(image_path, arcname=image.split("_", 1)[1])

        delete_file_later(zip_path)

        return render_template(
            "pdf_to_jpg_result.html",
            images=image_files,
            zip_file=zip_filename,
            total=len(image_files)
        )

    return render_template("pdf_to_jpg.html")


@app.route("/png-to-pdf", methods=["GET", "POST"])
def png_to_pdf():

    if request.method == "POST":

        output_filename = f"{uuid.uuid4()}_converted.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        error = images_to_pdf(request.files.getlist("images"), output_path)

        if error:
            return error_page(error)

        delete_file_later(output_path)

        return send_file(output_path, as_attachment=True)

    return render_template("png_to_pdf.html")


@app.route("/how-to-pdf-to-png")
def pdf_to_png_guide():
    return render_template("pdf_to_png_guide.html")

@app.route("/how-to-png-to-pdf")
def png_to_pdf_guide():
    return render_template("png_to_pdf_guide.html")


def _svg_element_points(el):
    """Extract an ordered point list from a <path>/<line>/<polyline> element."""
    tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag

    if tag == "line":
        try:
            return [
                (float(el.get("x1", 0)), float(el.get("y1", 0))),
                (float(el.get("x2", 0)), float(el.get("y2", 0))),
            ]
        except (TypeError, ValueError):
            return []

    if tag == "polyline":
        return _svg_parse_point_list(el.get("points", ""))

    d = el.get("d")
    return _svg_parse_path_d(d) if d else []


def _svg_parse_path_d(d):
    """Minimal M/L(/Z) SVG path-data parser -> list of (x, y) points."""
    tokens = re.findall(r"[MLmlZz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?", d)
    pts = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in ("M", "L", "m", "l", "Z", "z"):
            i += 1
            continue
        try:
            x, y = float(t), float(tokens[i + 1])
        except (IndexError, ValueError):
            break
        pts.append((x, y))
        i += 2
    return pts


def _svg_parse_point_list(points_attr):
    nums = re.findall(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?", points_attr or "")
    return [(float(nums[i]), float(nums[i + 1])) for i in range(0, len(nums) - 1, 2)]


def _svg_mat_mul(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1,
    )


def _svg_apply_mat(m, pt):
    a, b, c, d, e, f = m
    x, y = pt
    return (a * x + c * y + e, b * x + d * y + f)


def _inline_svg_markers(svg_bytes):
    """Bake <marker> arrowheads (marker-start/marker-end) into plain absolute
    -coordinate <path> elements before handing the SVG to MuPDF.

    MuPDF's SVG parser both silently drops most marker references and
    mis-handles chained transform= attributes, so real-world flowchart/
    diagram SVGs (which almost always use markers for arrowheads) lose most
    of their arrows on conversion. All the placement math (translate along
    the path's end tangent, rotate per orient="auto", scale per the default
    markerUnits="strokeWidth") is done here in plain Python, so the emitted
    geometry needs no transform support at all -- just M/L/Z path data.

    Anything this can't confidently parse (curves, unknown units) is left
    untouched rather than guessed at.
    """
    try:
        root = ET.fromstring(svg_bytes)
    except ET.ParseError:
        return svg_bytes

    SVG_NS = "http://www.w3.org/2000/svg"

    def tag(el):
        return el.tag.split("}")[-1] if "}" in el.tag else el.tag

    markers = {tag_el.get("id"): tag_el for tag_el in root.iter() if tag(tag_el) == "marker" and tag_el.get("id")}
    if not markers:
        return svg_bytes

    def resolve(value):
        if not value:
            return None
        m = re.match(r"url\(#([^)]+)\)", value.strip())
        return markers.get(m.group(1)) if m else None

    new_nodes = []

    for el in list(root.iter()):
        if tag(el) not in ("path", "line", "polyline"):
            continue

        pts = _svg_element_points(el)
        if len(pts) < 2:
            continue

        try:
            stroke_width = float(el.get("stroke-width", "1") or "1")
        except ValueError:
            stroke_width = 1.0

        for attr, is_start in (("marker-start", True), ("marker-end", False)):
            marker_el = resolve(el.get(attr))
            if marker_el is None:
                continue

            if is_start:
                anchor = pts[0]
                tx, ty = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
            else:
                anchor = pts[-1]
                tx, ty = pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]

            angle = math.degrees(math.atan2(ty, tx))
            orient = marker_el.get("orient", "0")
            if orient not in ("auto", "auto-start-reverse"):
                try:
                    angle = float(orient)
                except ValueError:
                    pass
            elif orient == "auto-start-reverse" and is_start:
                angle += 180

            marker_units = marker_el.get("markerUnits", "strokeWidth")
            scale = stroke_width if marker_units == "strokeWidth" else 1.0

            try:
                ref_x = float(marker_el.get("refX", "0") or "0")
                ref_y = float(marker_el.get("refY", "0") or "0")
            except ValueError:
                ref_x = ref_y = 0.0

            m = (1, 0, 0, 1, anchor[0], anchor[1])
            r = math.radians(angle)
            m = _svg_mat_mul(m, (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0, 0))
            m = _svg_mat_mul(m, (scale, 0, 0, scale, 0, 0))
            m = _svg_mat_mul(m, (1, 0, 0, 1, -ref_x, -ref_y))

            for child in list(marker_el):
                child_tag = tag(child)
                if child_tag == "path" and child.get("d"):
                    child_pts = _svg_parse_path_d(child.get("d"))
                elif child_tag == "polygon" and child.get("points"):
                    child_pts = _svg_parse_point_list(child.get("points"))
                else:
                    continue
                if not child_pts:
                    continue

                transformed = [_svg_apply_mat(m, p) for p in child_pts]
                d_str = "M " + " L ".join(f"{x:.3f},{y:.3f}" for x, y in transformed) + " Z"

                new_path = ET.Element(f"{{{SVG_NS}}}path", {"d": d_str})
                fill = child.get("fill")
                if fill:
                    new_path.set("fill", fill)
                new_nodes.append(new_path)

            del el.attrib[attr]

    for node in new_nodes:
        root.append(node)

    return ET.tostring(root, encoding="utf-8")


@app.route("/svg-to-pdf", methods=["GET", "POST"])
def svg_to_pdf():

    if request.method == "POST":

        files = request.files.getlist("images")

        saved_paths = []
        output_doc = fitz.open()

        for file in files:

            if not file.filename:
                continue
            if not file.filename.lower().endswith(".svg"):
                continue

            filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)
            saved_paths.append(path)

            try:
                with open(path, "rb") as f:
                    svg_bytes = f.read()
                svg_bytes = _inline_svg_markers(svg_bytes)

                svg_doc = fitz.open(stream=svg_bytes, filetype="svg")
                pdf_bytes = svg_doc.convert_to_pdf()
                svg_doc.close()

                page_pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
                output_doc.insert_pdf(page_pdf)
                page_pdf.close()
            except Exception:
                continue

        for path in saved_paths:
            delete_file_later(path)

        if len(output_doc) == 0:
            output_doc.close()
            return error_page("No valid SVG files were uploaded.")

        output_filename = f"{uuid.uuid4()}_converted.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        output_doc.save(output_path)
        output_doc.close()

        delete_file_later(output_path)

        return send_file(output_path, as_attachment=True)

    return render_template("svg_to_pdf.html")


@app.route("/how-to-svg-to-pdf")
def svg_to_pdf_guide():
    return render_template("svg_to_pdf_guide.html")


@app.route("/compress-pdf-for-email")
def compress_pdf_for_email():
    return render_template("compress_pdf_for_email.html")

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/privacy-policy")
def privacy_policy():
    return render_template("privacy_policy.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/pdf-to-excel", methods=["GET","POST"])
def pdf_to_excel():

    import pdfplumber
    import pandas as pd

    if request.method == "POST":

        file = request.files["pdf"]

        if file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        if not file.filename.lower().endswith(".pdf"):
            return error_page("Please upload a PDF file.")

        input_path, _ = save_upload(file)
        stem = upload_stem(file)

        output_filename = f"{uuid.uuid4()}_{stem}.xlsx"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        tables = []

        with pdfplumber.open(input_path) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    df = pd.DataFrame(table[1:], columns=table[0])
                    tables.append(df)
                release_pdfplumber_page(page)

        if tables:
            final_df = pd.concat(tables)
            final_df.to_excel(output_path, index=False)
        else:
            return error_page("We couldn't find a table in this PDF. PDF to Excel needs tables with selectable text — scanned pages won't work.")

        delete_file_later(output_path)

        return send_file(output_path, as_attachment=True, download_name=f"{stem}.xlsx")

    return render_template("pdf_to_excel.html")

@app.route("/excel-to-pdf", methods=["GET","POST"])
def excel_to_pdf():

    import pandas as pd
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    if request.method == "POST":

        file = request.files["excel"]

        if file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        if not file.filename.lower().endswith(EXCEL_EXTENSIONS):
            return error_page("Please upload an Excel file (.xlsx).")

        input_path, _ = save_upload(file)
        stem = upload_stem(file)

        try:
            df = pd.read_excel(input_path)
        except Exception:
            return error_page("Could not read that spreadsheet. Please save it as .xlsx and try again.")

        output_filename = f"{uuid.uuid4()}_{stem}.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        c = canvas.Canvas(output_path, pagesize=letter)

        y = 750

        for index, row in df.iterrows():

            row_text = " | ".join(str(x) for x in row)

            c.drawString(40, y, row_text)

            y -= 20

            if y < 40:
                c.showPage()
                y = 750

        c.save()

        delete_file_later(output_path)

        return send_file(output_path, as_attachment=True, download_name=f"{stem}.pdf")

    return render_template("excel_to_pdf.html")

@app.route("/how-to-pdf-to-excel")
def pdf_to_excel_guide():
    return render_template("pdf_to_excel_guide.html")


@app.route("/how-to-excel-to-pdf")
def excel_to_pdf_guide():
    return render_template("excel_to_pdf_guide.html")

@app.route("/pdf-to-text", methods=["GET", "POST"])
def pdf_to_text():

    import pdfplumber

    if request.method == "POST":

        file = request.files["pdf"]

        if file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        if not file.filename.lower().endswith(".pdf"):
            return error_page("Please upload a PDF file.")

        input_path, _ = save_upload(file)
        stem = upload_stem(file)

        output_filename = f"{uuid.uuid4()}_{stem}.txt"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        text_content = ""

        with pdfplumber.open(input_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_content += text + "\n\n"
                release_pdfplumber_page(page)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text_content)

        delete_file_later(output_path)

        return send_file(output_path, as_attachment=True, download_name=f"{stem}.txt")

    return render_template("pdf_to_text.html")

@app.route("/how-to-extract-text-from-pdf")
def pdf_to_text_guide():
    return render_template("pdf_to_text_guide.html")

@app.route("/pdf-to-webp", methods=["GET", "POST"])
def pdf_to_webp():

    import fitz  # PyMuPDF
    from PIL import Image

    if request.method == "POST":

        file = request.files.get("pdf")

        if not file or file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        input_path, _ = save_upload(file)

        doc = fitz.open(input_path)

        image_files = []
        MAX_PAGES = 20  # safety limit

        for page_index in range(len(doc)):

            if page_index >= MAX_PAGES:
                break

            page = doc[page_index]

            # render page (better quality)
            pix = page.get_pixmap(matrix=render_matrix(page.rect.width, page.rect.height))

            # convert to PIL image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            output_filename = f"{uuid.uuid4()}_page_{page_index+1}.webp"
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)

            # save as WEBP (with compression)
            img.save(output_path, "WEBP", quality=80)

            image_files.append(output_filename)

            # optional cleanup
            delete_file_later(output_path)

        doc.close()

        return render_template(
            "pdf_to_webp_result.html",
            images=image_files,
            total=len(image_files)
        )

    return render_template("pdf_to_webp.html")

@app.route("/how-to-pdf-to-webp")
def pdf_to_webp_guide():
    return render_template("pdf_to_webp_guide.html")

@app.route("/ads.txt")
def ads():
    return send_file("templates/ads.txt", mimetype="text/plain")


@app.route("/crop-pdf", methods=["GET", "POST"])
def crop_pdf():

    if request.method == "POST":

        file = request.files["pdf"]

        if file.filename == "":
            return error_page("No file selected. Please choose a file and try again.")

        filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)

        try:
            margins = [float(request.form.get(side, 0)) for side in ("left", "right", "top", "bottom")]
        except (ValueError, TypeError):
            return error_page("Crop margins must be numbers (in points).")

        if not all(map(math.isfinite, margins)):
            return error_page("Crop margins must be numbers (in points).")

        left, right, top, bottom = (max(0, m) for m in margins)

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:

            x0 = float(page.mediabox.left) + left
            y0 = float(page.mediabox.bottom) + bottom
            x1 = float(page.mediabox.right) - right
            y1 = float(page.mediabox.top) - top

            if x1 <= x0 or y1 <= y0:
                return error_page("Those crop margins are larger than the page. Please use smaller values.")

            page.mediabox.lower_left = (x0, y0)
            page.mediabox.upper_right = (x1, y1)

            writer.add_page(page)

        output_filename = f"{uuid.uuid4()}_cropped.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        with open(output_path, "wb") as f:
            writer.write(f)

        delete_file_later(output_path)

        return send_file(output_path, as_attachment=True)

    return render_template("crop_pdf.html")


@app.route("/how-to-crop-pdf")
def crop_pdf_guide():
    return render_template("crop_pdf_guide.html")

@app.route("/sign-pdf", methods=["GET", "POST"])
def sign_pdf():

    import fitz  # PyMuPDF
    from PIL import Image
    import uuid
    import os

    if request.method == "POST":

        pdf_file = request.files.get("pdf")
        signature_file = request.files.get("signature")
        existing_file = request.form.get("existing_file")

        # =========================
        # ✅ STEP 1 — UPLOAD + PREVIEW
        # =========================
        if (
            pdf_file
            and signature_file
            and pdf_file.filename
            and signature_file.filename
        ):

            # Scheduled now, not in step 2 -- an abandoned session never gets there.
            pdf_path, pdf_name = save_upload(pdf_file, delay=600)
            sig_path, sig_name = save_upload(signature_file, delay=600)

            try:
                with Image.open(sig_path) as sig_img:
                    sig_img.verify()
            except Exception:
                return error_page("Your signature must be an image file (PNG or JPG).")

            try:
                page_num = int(request.form.get("page", 1)) - 1
            except (ValueError, TypeError):
                page_num = 0

            # 🔥 GENERATE PREVIEW (FIRST PAGE ONLY)
            doc = fitz.open(pdf_path)
            if page_num < 0 or page_num >= len(doc):
                page_num = 0
            page = doc[page_num]

            pix = page.get_pixmap(matrix=render_matrix(page.rect.width, page.rect.height))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()

            preview_name = f"{uuid.uuid4()}.jpg"
            preview_path = os.path.join("static", preview_name)

            img.save(preview_path, "JPEG")

            # optional cleanup
            delete_file_later(preview_path, delay=600)

            return render_template(
                "sign_pdf.html",
                preview=preview_name,
                filename=pdf_name,
                signature=sig_name,
                page=page_num + 1
            )

        # =========================
        # ✅ STEP 2 — APPLY SIGNATURE
        # =========================
        elif existing_file:

            pdf_path = resolve_upload(existing_file)
            sig_path = resolve_upload(request.form.get("signature_file"))

            # 🔒 SECURITY CHECK
            if not pdf_path or not sig_path:
                return error_page("File missing or expired. Please upload again.")

            # 📍 POSITION FROM FRONTEND
            try:
                x = float(request.form.get("x", 0))
                y = float(request.form.get("y", 0))
                img_width = float(request.form.get("img_width", 1))
                img_height = float(request.form.get("img_height", 1))

                box_width = float(request.form.get("box_width", 100))
                box_height = float(request.form.get("box_height", 50))

                page_num = int(request.form.get("page", 1)) - 1
            except (ValueError, TypeError):
                return error_page("The signature position was invalid. Please place your signature again.")

            values = (x, y, img_width, img_height, box_width, box_height)
            if not all(map(math.isfinite, values)) or min(img_width, img_height, box_width, box_height) <= 0:
                return error_page("The signature position was invalid. Please place your signature again.")

            doc = fitz.open(pdf_path)
            if page_num < 0 or page_num >= len(doc):
                page_num = 0
            page = doc[page_num]

            pdf_width = page.rect.width
            pdf_height = page.rect.height

            # =========================
            # ✅ CORRECT SCALING
            # =========================

            pdf_x = (x / img_width) * pdf_width

            pdf_w = (box_width / img_width) * pdf_width
            pdf_h = (box_height / img_height) * pdf_height

            # 🔥 FINAL FIX (NO MORE JUMPING)
            pdf_y = (y / img_height) * pdf_height

            rect = fitz.Rect(pdf_x, pdf_y, pdf_x + pdf_w, pdf_y + pdf_h)

            # 🖊 INSERT SIGNATURE
            page.insert_image(rect, filename=sig_path)

            output_name = f"signed_{uuid.uuid4()}.pdf"
            output_path = os.path.join(UPLOAD_FOLDER, output_name)

            doc.save(output_path)
            doc.close()

            # 🧹 CLEANUP
            delete_file_later(output_path)
            delete_file_later(pdf_path, delay=60)
            delete_file_later(sig_path, delay=60)

            return send_file(output_path, as_attachment=True)

    # =========================
    # ✅ DEFAULT PAGE
    # =========================
    return render_template("sign_pdf.html")

@app.route("/add-text-to-pdf", methods=["GET", "POST"])
def add_text_to_pdf():

    if request.method == "POST":

        pdf_file = request.files.get("pdf")
        existing_file = request.form.get("existing_file")

        # Step 1: Upload + generate preview
        if pdf_file and pdf_file.filename:

            pdf_name = f"{uuid.uuid4()}_{secure_filename(pdf_file.filename)}"
            pdf_path = os.path.join(UPLOAD_FOLDER, pdf_name)
            pdf_file.save(pdf_path)

            doc = fitz.open(pdf_path)
            page = doc[0]
            pix = page.get_pixmap(matrix=render_matrix(page.rect.width, page.rect.height))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()

            preview_name = f"{uuid.uuid4()}.jpg"
            preview_path = os.path.join("static", preview_name)
            img.save(preview_path, "JPEG")

            delete_file_later(pdf_path, delay=600)
            delete_file_later(preview_path, delay=600)

            return render_template(
                "add_text_to_pdf.html",
                preview=preview_name,
                filename=pdf_name,
            )

        # Step 2: Apply text to PDF
        elif existing_file:

            pdf_path = resolve_upload(existing_file)

            if not pdf_path:
                return error_page("File missing or expired. Please upload again.")

            try:
                x = float(request.form.get("x", 0))
                y = float(request.form.get("y", 0))
                font_size = float(request.form.get("font_size", 12))
                img_width = float(request.form.get("img_width", 1) or 1)
                img_height = float(request.form.get("img_height", 1) or 1)
            except (ValueError, TypeError):
                return error_page("The text position or size was invalid. Please place your text again.")

            if (not all(map(math.isfinite, (x, y, font_size, img_width, img_height)))
                    or img_width <= 0 or img_height <= 0 or not 1 <= font_size <= 200):
                return error_page("The text position or size was invalid. Please place your text again.")

            text = request.form.get("text", "")
            color = request.form.get("color", "#000000")
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", color or ""):
                color = "#000000"
            color_hex = color.lstrip("#")

            r = int(color_hex[0:2], 16) / 255
            g = int(color_hex[2:4], 16) / 255
            b = int(color_hex[4:6], 16) / 255

            doc = fitz.open(pdf_path)
            page = doc[0]

            pdf_x = (x / img_width) * page.rect.width
            pdf_y = (y / img_height) * page.rect.height

            page.insert_text(
                (pdf_x, pdf_y + font_size),
                text,
                fontsize=font_size,
                color=(r, g, b)
            )

            output_name = f"{uuid.uuid4()}_text_added.pdf"
            output_path = os.path.join(UPLOAD_FOLDER, output_name)
            doc.save(output_path)
            doc.close()

            delete_file_later(pdf_path, delay=60)
            delete_file_later(output_path)

            return send_file(output_path, as_attachment=True)

    return render_template("add_text_to_pdf.html")


@app.route("/how-to-add-text-to-pdf")
def add_text_guide():
    return render_template("add_text_to_pdf_guide.html")


@app.route("/redact-pdf", methods=["GET", "POST"])
def redact_pdf():

    if request.method == "POST":

        pdf_file = request.files.get("pdf")
        existing_file = request.form.get("existing_file")

        # =========================
        # STEP 1 — UPLOAD + PREVIEW FIRST PAGE
        # =========================
        if pdf_file and pdf_file.filename:

            pdf_name = f"{uuid.uuid4()}_{secure_filename(pdf_file.filename)}"
            pdf_path = os.path.join(UPLOAD_FOLDER, pdf_name)
            pdf_file.save(pdf_path)

            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            preview_name = _render_pdf_page_preview(doc, 0)
            doc.close()

            delete_file_later(pdf_path, delay=600)

            return render_template(
                "redact_pdf.html",
                preview=preview_name,
                filename=pdf_name,
                page=1,
                total_pages=total_pages,
                areas_json="[]",
            )

        # =========================
        # STEP 2 — NAVIGATE PAGES OR APPLY REDACTIONS
        # =========================
        elif existing_file:

            pdf_path = resolve_upload(existing_file)

            if not pdf_path:
                return error_page("File missing or expired. Please upload again.")

            action = request.form.get("action", "apply")
            areas_json = request.form.get("areas", "[]")

            doc = fitz.open(pdf_path)
            total_pages = len(doc)

            if action == "apply":
                try:
                    areas = json.loads(areas_json)
                    if not isinstance(areas, list):
                        areas = []
                except (ValueError, TypeError):
                    areas = []

                _apply_pdf_redactions(doc, areas)

                output_name = f"{uuid.uuid4()}_redacted.pdf"
                output_path = os.path.join(UPLOAD_FOLDER, output_name)
                doc.save(output_path)
                doc.close()

                delete_file_later(pdf_path, delay=60)
                delete_file_later(output_path)

                return send_file(output_path, as_attachment=True)

            try:
                current_page = int(request.form.get("current_page", 1) or 1)
            except (ValueError, TypeError):
                current_page = 1
            if action == "prev":
                target_page = current_page - 1
            elif action == "next":
                target_page = current_page + 1
            else:
                target_page = current_page

            target_page = max(1, min(total_pages, target_page))
            preview_name = _render_pdf_page_preview(doc, target_page - 1)
            doc.close()

            return render_template(
                "redact_pdf.html",
                preview=preview_name,
                filename=existing_file,
                page=target_page,
                total_pages=total_pages,
                areas_json=areas_json,
            )

    return render_template("redact_pdf.html")


@app.route("/how-to-redact-pdf")
def redact_pdf_guide():
    return render_template("redact_pdf_guide.html")


from flask import send_from_directory, abort

# Only the sign-pdf signature preview loads files through this route, so it
# serves images only -- never the PDFs/documents that share uploads/.
PREVIEWABLE_UPLOAD_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    if not filename.lower().endswith(PREVIEWABLE_UPLOAD_EXTENSIONS):
        abort(404)
    response = send_from_directory(UPLOAD_FOLDER, filename)
    response.headers["X-Robots-Tag"] = "noindex"
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
