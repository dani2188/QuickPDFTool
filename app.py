import fitz
from PIL import Image
from PyPDF2 import PdfMerger, PdfReader, PdfWriter

from flask import Flask, request, render_template, send_file, jsonify
import subprocess
import os
import threading
import time
import platform
import uuid
import io
import zipfile

from werkzeug.utils import secure_filename
from pdf2docx import Converter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import json




app = Flask(__name__)

# limit upload size
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def delete_file_later(file_path, delay=300):
    def delete():
        time.sleep(delay)
        if os.path.exists(file_path):
            os.remove(file_path)

    threading.Thread(target=delete, daemon=True).start()


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
            return "No file uploaded", 400

        file = request.files["pdf"]

        if file.filename == "":
            return "No file selected", 400

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

    compressed_path = os.path.join(UPLOAD_FOLDER, filename)

    if not os.path.exists(compressed_path):
        return "File not ready", 404

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
        return "File not found", 404

    return send_file(path, as_attachment=True)


@app.route("/status/<filename>")
def status(filename):

    path = os.path.join(UPLOAD_FOLDER, filename)

    if os.path.exists(path):
        return {"ready": True}

    return {"ready": False}


@app.route("/merge-pdf", methods=["GET", "POST"])
def merge_pdf():

    if request.method == "POST":

        files = request.files.getlist("pdfs")

        merger = PdfMerger()

        unique_id = str(uuid.uuid4())
        output_filename = f"{unique_id}_merged.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        for file in files:

            if file.filename != "":
                filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
                path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(path)
                delete_file_later(path)


                merger.append(path)

        merger.write(output_path)
        merger.close()

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


@app.route("/split-pdf", methods=["GET", "POST"])
def split_pdf():

    if request.method == "POST":

        file = request.files["pdf"]

        if not file or file.filename == "":
            return "No file selected", 400

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

        files = request.files.getlist("images")

        images = []

        for file in files:

            if file.filename != "":

                filename = secure_filename(file.filename)
                path = os.path.join(UPLOAD_FOLDER, filename)

                file.save(path)
                delete_file_later(path)


                image = Image.open(path).convert("RGB")
                images.append(image)

        unique_id = str(uuid.uuid4())
        output_filename = f"{unique_id}_images.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        if images:

            images[0].save(
                output_path,
                save_all=True,
                append_images=images[1:]
            )

        return send_file(output_path, as_attachment=True)

    return render_template("jpg_to_pdf.html")

@app.route("/pdf-to-png", methods=["GET", "POST"])
def pdf_to_png():

    import fitz  # PyMuPDF
    from PIL import Image

    if request.method == "POST":

        file = request.files.get("pdf")

        if not file or file.filename == "":
            return "No file selected"

        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(input_path)

        doc = fitz.open(input_path)

        image_files = []
        MAX_PAGES = 20

        for page_index in range(len(doc)):

            if page_index >= MAX_PAGES:
                break

            page = doc[page_index]

            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))

            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            output_filename = f"{uuid.uuid4()}_page_{page_index+1}.png"
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)

            img.save(output_path, "PNG")

            image_files.append(output_filename)

            delete_file_later(output_path)

        delete_file_later(input_path)
        
        # CREATE ZIP
        zip_filename = f"{uuid.uuid4()}_png_images.zip"
        zip_path = os.path.join(UPLOAD_FOLDER, zip_filename)

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for image in image_files:
                image_path = os.path.join(UPLOAD_FOLDER, image)
                zipf.write(image_path, arcname=image)

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
        rotation = int(request.form.get("rotation", 0)) % 360

        if not file or file.filename == "":
            return "No file selected"

        filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)


        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            if hasattr(page, "rotate_clockwise"):
                page = page.rotate_clockwise(rotation)
            elif hasattr(page, "rotate"):
                page.rotate(rotation)
            else:
                page._data["/Rotate"] = rotation
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
            return "No file selected"

        if not pages_to_delete:
            return "Please enter page numbers to delete (e.g. 2,5,7)", 400

        filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)

        reader = PdfReader(input_path)
        writer = PdfWriter()

        try:
            delete_pages = [int(p.strip()) - 1 for p in pages_to_delete.split(",") if p.strip()]
        except ValueError:
            return "Invalid page numbers. Use format: 2,5,7", 400

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
            return "No file selected"

        filename = secure_filename(file.filename)

        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)
        

        output_filename = filename.replace(".pdf", ".docx")
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        cv = Converter(input_path)
        cv.convert(output_path, start=0, end=None)
        cv.close()

        return send_file(output_path, as_attachment=True)

    return render_template("pdf_to_word.html")


@app.route("/word-to-pdf", methods=["GET", "POST"])
def word_to_pdf():

    if request.method == "POST":

        file = request.files["docx"]

        if file.filename == "":
            return "No file selected"

        filename = secure_filename(file.filename)

        input_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(input_path)
        delete_file_later(input_path)
        

        output_filename = filename.replace(".docx", ".pdf")
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        result = subprocess.run([
            "libreoffice",
            "--headless",
            "--convert-to",
            "pdf",
            input_path,
            "--outdir",
            UPLOAD_FOLDER
        ])

        if result.returncode != 0 or not os.path.exists(output_path):
            return "Conversion failed. Make sure your file is a valid .docx document.", 500

        return send_file(output_path, as_attachment=True)

    return render_template("word_to_pdf.html")

@app.route("/protect-pdf", methods=["GET", "POST"])
def protect_pdf():

    if request.method == "POST":

        file = request.files["pdf"]
        password = request.form.get("password")

        if file.filename == "":
            return "No file selected"

        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)
        
        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt(password)

        output_filename = f"protected_{filename}"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True)

    return render_template("protect_pdf.html")

@app.route("/unlock-pdf", methods=["GET", "POST"])
def unlock_pdf():

    if request.method == "POST":

        file = request.files["pdf"]
        password = request.form.get("password")

        if file.filename == "":
            return "No file selected"

        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)

        reader = PdfReader(input_path)

        if reader.is_encrypted:
            reader.decrypt(password)

        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        output_filename = f"unlocked_{filename}"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True)

    return render_template("unlock_pdf.html")

@app.route("/add-page-numbers", methods=["GET", "POST"])
def add_page_numbers():
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    if request.method == "POST":

        file = request.files["pdf"]

        if file.filename == "":
            return "No file selected"

        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)
        
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

        output_filename = f"numbered_{filename}"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True)

    return render_template("add_page_numbers.html")

@app.route("/pdf-tools")
def pdf_tools():
    return render_template("pdf_tools.html")

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
            return "No file selected"

        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)
        


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

        output_filename = f"watermarked_{filename}"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True)

    return render_template("add_watermark.html")

@app.route("/remove-watermark", methods=["GET", "POST"])
def remove_watermark():

    if request.method == "POST":

        file = request.files["pdf"]

        if file.filename == "":
            return "No file selected"

        filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)

        output_filename = f"{uuid.uuid4()}_cleaned.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        doc = fitz.open(input_path)
        for page in doc:
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
            return "No file selected"

        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(input_path)

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

                images.append(image_filename)

                # ✅ LIMIT
                if len(images) >= MAX_IMAGES:
                    break

            if len(images) >= MAX_IMAGES:
                break

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
            return "No file selected"

        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(input_path)

        doc = fitz.open(input_path)

        image_files = []
        MAX_PAGES = 20

        for page_index in range(len(doc)):

            if page_index >= MAX_PAGES:
                break

            page = doc[page_index]

            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))

            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            output_filename = f"{uuid.uuid4()}_page_{page_index+1}.jpg"
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)

            img.save(output_path, "JPEG", quality=90)

            image_files.append(output_filename)

            delete_file_later(output_path)

        delete_file_later(input_path)

        # CREATE ZIP
        zip_filename = f"{uuid.uuid4()}_jpg_images.zip"
        zip_path = os.path.join(UPLOAD_FOLDER, zip_filename)

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for image in image_files:
                image_path = os.path.join(UPLOAD_FOLDER, image)
                zipf.write(image_path, arcname=image)

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

        files = request.files.getlist("images")

        images = []

        for file in files:

            if file.filename != "":

                filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
                path = os.path.join(UPLOAD_FOLDER, filename)

                file.save(path)
                delete_file_later(path)

                image = Image.open(path).convert("RGB")
                images.append(image)

        if images:

            output_filename = f"{uuid.uuid4()}_converted.pdf"
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)

            images[0].save(
                output_path,
                save_all=True,
                append_images=images[1:]
            )

            delete_file_later(output_path)

            return send_file(output_path, as_attachment=True)

    return render_template("png_to_pdf.html")


@app.route("/how-to-pdf-to-png")
def pdf_to_png_guide():
    return render_template("pdf_to_png_guide.html")

@app.route("/how-to-png-to-pdf")
def png_to_pdf_guide():
    return render_template("png_to_pdf_guide.html")

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
            return "No file selected"

        filename = secure_filename(file.filename)

        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)

        output_filename = filename.replace(".pdf",".xlsx")
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        tables = []

        with pdfplumber.open(input_path) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    df = pd.DataFrame(table[1:], columns=table[0])
                    tables.append(df)

        if tables:
            final_df = pd.concat(tables)
            final_df.to_excel(output_path, index=False)
        else:
            return "No table found in PDF"

        delete_file_later(output_path)

        return send_file(output_path, as_attachment=True)

    return render_template("pdf_to_excel.html")

@app.route("/excel-to-pdf", methods=["GET","POST"])
def excel_to_pdf():

    import pandas as pd
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    if request.method == "POST":

        file = request.files["excel"]

        if file.filename == "":
            return "No file selected"

        filename = secure_filename(file.filename)

        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)

        df = pd.read_excel(input_path)

        output_filename = filename.replace(".xlsx",".pdf")
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

        return send_file(output_path, as_attachment=True)

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
            return "No file selected"

        filename = secure_filename(file.filename)

        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)

        output_filename = filename.replace(".pdf", ".txt")
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        text_content = ""

        with pdfplumber.open(input_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_content += text + "\n\n"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text_content)

        delete_file_later(output_path)

        return send_file(output_path, as_attachment=True)

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
            return "No file selected"

        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(input_path)

        doc = fitz.open(input_path)

        image_files = []
        MAX_PAGES = 20  # safety limit

        for page_index in range(len(doc)):

            if page_index >= MAX_PAGES:
                break

            page = doc[page_index]

            # render page (better quality)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))

            # convert to PIL image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            output_filename = f"{uuid.uuid4()}_page_{page_index+1}.webp"
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)

            # save as WEBP (with compression)
            img.save(output_path, "WEBP", quality=80)

            image_files.append(output_filename)

            # optional cleanup
            delete_file_later(output_path)

        # optional cleanup input
        delete_file_later(input_path)

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
    return send_file("ads.txt")


@app.route("/crop-pdf", methods=["GET", "POST"])
def crop_pdf():

    if request.method == "POST":

        file = request.files["pdf"]

        if file.filename == "":
            return "No file selected"

        filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)

        left = max(0, float(request.form.get("left", 0)))
        right = max(0, float(request.form.get("right", 0)))
        top = max(0, float(request.form.get("top", 0)))
        bottom = max(0, float(request.form.get("bottom", 0)))

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:

            x0 = page.mediabox.left + left
            y0 = page.mediabox.bottom + bottom
            x1 = page.mediabox.right - right
            y1 = page.mediabox.top - top

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

            pdf_name = f"{uuid.uuid4()}_{secure_filename(pdf_file.filename)}"
            sig_name = f"{uuid.uuid4()}_{secure_filename(signature_file.filename)}"

            pdf_path = os.path.join(UPLOAD_FOLDER, pdf_name)
            sig_path = os.path.join(UPLOAD_FOLDER, sig_name)

            pdf_file.save(pdf_path)
            signature_file.save(sig_path)

            # 🔥 GENERATE PREVIEW (FIRST PAGE ONLY)
            doc = fitz.open(pdf_path)
            page_num = int(request.form.get("page", 1)) - 1
            if page_num < 0 or page_num >= len(doc):
                page_num = 0
            page = doc[page_num]

            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

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

            pdf_path = os.path.join(UPLOAD_FOLDER, existing_file)

            sig_filename = request.form.get("signature_file")
            sig_path = os.path.join(UPLOAD_FOLDER, sig_filename)

            # 🔒 SECURITY CHECK
            if not os.path.exists(pdf_path) or not os.path.exists(sig_path):
                return "File missing", 400

            # 📍 POSITION FROM FRONTEND
            x = float(request.form.get("x", 0))
            y = float(request.form.get("y", 0))
            img_width = float(request.form.get("img_width", 1))
            img_height = float(request.form.get("img_height", 1))

            box_width = float(request.form.get("box_width", 100))
            box_height = float(request.form.get("box_height", 50))

            page_num = int(request.form.get("page", 1)) - 1

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
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
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

            pdf_path = os.path.join(UPLOAD_FOLDER, existing_file)

            if not os.path.exists(pdf_path):
                return "File missing or expired. Please upload again.", 400

            x = float(request.form.get("x", 0))
            y = float(request.form.get("y", 0))
            text = request.form.get("text", "")
            font_size = float(request.form.get("font_size", 12))
            color_hex = request.form.get("color", "#000000").lstrip("#")
            img_width = float(request.form.get("img_width", 1) or 1)
            img_height = float(request.form.get("img_height", 1) or 1)

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

from flask import send_from_directory

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
