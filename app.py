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

def compress_pdf(input_path, output_path):

    try:

        if platform.system() == "Windows":
            gs_command = "gswin64c"
        else:
            gs_command = "gs"

        temp_output = output_path + ".tmp"

        command = [
            gs_command,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/screen",
            "-dDetectDuplicateImages=true",
            "-dCompressFonts=true",
            "-dSubsetFonts=true",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={temp_output}",
            input_path
        ]

        subprocess.run(command, check=True)

        os.rename(temp_output, output_path)

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

        filename = secure_filename(file.filename)

        unique_id = str(uuid.uuid4())

        input_filename = f"{unique_id}_{filename}"
        output_filename = f"{unique_id}_compressed_{filename}"

        input_path = os.path.join(UPLOAD_FOLDER, input_filename)
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        file.save(input_path)
        delete_file_later(input_path)
        delete_file_later(output_path)


        threading.Thread(
            target=compress_pdf,
            args=(input_path, output_path),
            daemon=True
        ).start()

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

    return render_template(
        "result.html",
        file_name=filename,
        original_size=original_mb,
        compressed_size=compressed_mb,
        reduction=reduction
    )


@app.route("/download-file/<filename>")
def download_file(filename):

    path = os.path.join(UPLOAD_FOLDER, filename)

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
                filename = secure_filename(file.filename)
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
    return "File too large. Maximum allowed size is 10MB.", 413


@app.route("/split-pdf", methods=["GET", "POST"])
def split_pdf():

    if request.method == "POST":

        file = request.files["pdf"]

        if file.filename == "":
            return "No file selected"

        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)
        delete_file_later(output_path)



        reader = PdfReader(input_path)

        output_files = []

        for i, page in enumerate(reader.pages):

            writer = PdfWriter()
            writer.add_page(page)

            output_filename = f"{uuid.uuid4()}_page_{i+1}.jpg"
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)


            with open(output_path, "wb") as output_file:
                writer.write(output_file)

            output_files.append(output_filename)

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
        rotation = int(request.form.get("rotation"))

        if file.filename == "":
            return "No file selected"

        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)
    

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            page.rotate(rotation)
            writer.add_page(page)

        output_filename = f"rotated_{filename}"
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
        pages_to_delete = request.form.get("pages")

        if file.filename == "":
            return "No file selected"

        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)

        reader = PdfReader(input_path)
        writer = PdfWriter()

        delete_pages = [int(p.strip()) - 1 for p in pages_to_delete.split(",")]

        for i, page in enumerate(reader.pages):

            if i not in delete_pages:
                writer.add_page(page)

        output_filename = f"edited_{filename}"
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

        subprocess.run([
            "libreoffice",
            "--headless",
            "--convert-to",
            "pdf",
            input_path,
            "--outdir",
            UPLOAD_FOLDER
        ])

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

@app.route("/how-to-word-to-pdf")
def word_to_pdf_guide():
    return render_template("word_to_pdf_guide.html")

@app.route("/how-to-pdf-to-word")
def pdf_to_word_guide():
    return render_template("pdf_to_word_guide.html")

@app.route("/compress-pdf-to-1mb")
def compress_pdf_1mb():
    return render_template("compress_pdf_to_1mb.html")


@app.route("/sign-pdf", methods=["GET", "POST"])
def sign_pdf():

    if request.method == "POST":

        pdf_file = request.files["pdf"]
        signature = request.files["signature"]

        if pdf_file.filename == "" or signature.filename == "":
            return "Missing file"

        pdf_name = secure_filename(pdf_file.filename)
        sig_name = secure_filename(signature.filename)

        pdf_path = os.path.join(UPLOAD_FOLDER, pdf_name)
        sig_path = os.path.join(UPLOAD_FOLDER, sig_name)

        pdf_file.save(pdf_path)
        delete_file_later(pdf_path)

        signature.save(sig_path)

        reader = PdfReader(pdf_path)
        writer = PdfWriter()

        sig_img = Image.open(sig_path)

        for i, page in enumerate(reader.pages):

            packet = io.BytesIO()

            c = canvas.Canvas(packet, pagesize=letter)

            if i == 0:
                c.drawImage(sig_path, 400, 50, width=150, height=50)

            c.save()

            packet.seek(0)

            overlay = PdfReader(packet)

            page.merge_page(overlay.pages[0])

            writer.add_page(page)

        output_name = f"signed_{pdf_name}"
        output_path = os.path.join(UPLOAD_FOLDER, output_name)

        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True)

    return render_template("sign_pdf.html")


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

        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)
        delete_file_later(input_path)
        

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:

            page.clear()

            writer.add_page(page)

        output_filename = f"cleaned_{filename}"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        delete_file_later(output_path)

        with open(output_path, "wb") as f:
            writer.write(f)

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

@app.route("/add-text-to-pdf", methods=["GET", "POST"])
def add_text_to_pdf():

    import fitz
    from PIL import Image
    import uuid

    preview_filename = None
    filename = None

    if request.method == "POST":

        file = request.files.get("pdf")
        existing_file = request.form.get("existing_file")

        # ✅ STEP 1 — GENERATE PREVIEW
        if file and file.filename != "":

            filename = secure_filename(file.filename)
            input_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(input_path)

            doc = fitz.open(input_path)
            page = doc[0]

            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            preview_filename = f"{uuid.uuid4()}.jpg"
            preview_path = os.path.join("static", preview_filename)

            img.save(preview_path, "JPEG")

            # ✅ optional cleanup
            delete_file_later(preview_path, delay=600)

            return render_template(
                "add_text_to_pdf.html",
                preview=preview_filename,
                filename=filename
            )

        # ✅ STEP 2 — APPLY TEXT
        elif existing_file:

            input_path = os.path.join(UPLOAD_FOLDER, existing_file)

            text = request.form.get("text")
            if not text:
                return "No text provided", 400

            x = float(request.form.get("x", 50))
            y = float(request.form.get("y", 50))

            img_width = float(request.form.get("img_width"))
            img_height = float(request.form.get("img_height"))

            font_size = int(request.form.get("font_size", 12))
            color_hex = request.form.get("color", "#000000")

            color = tuple(int(color_hex[i:i+2], 16)/255 for i in (1, 3, 5))

            doc = fitz.open(input_path)
            page = doc[0]

            pdf_width = page.rect.width
            pdf_height = page.rect.height
            # position
            pdf_x = (x / img_width) * pdf_width
            pdf_y = (y / img_height) * pdf_height

            box_width = float(request.form.get("box_width"))
            box_height = float(request.form.get("box_height"))

            pdf_box_width = (box_width / img_width) * pdf_width
            pdf_box_height = (box_height / img_height) * pdf_height

            rect = fitz.Rect(
                pdf_x,
                pdf_y,
                pdf_x + pdf_box_width,
                pdf_y + pdf_box_height
            )

            page.insert_textbox(
                rect,
                text,
                fontsize=font_size,
                color=color,
                align=0
            )

            output_filename = f"text_{uuid.uuid4()}.pdf"
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)

            doc.save(output_path)

            # ✅ cleanup AFTER use
            delete_file_later(input_path)
            delete_file_later(output_path)

            return send_file(output_path, as_attachment=True)

    return render_template("add_text_to_pdf.html")

@app.route("/how-to-add-text-to-pdf")
def add_text_guide():
    return render_template("add_text_to_pdf_guide.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
