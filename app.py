from flask import Flask, request, render_template, send_file, jsonify
import subprocess
import os
import threading
import time
import platform
import uuid
import io

from werkzeug.utils import secure_filename
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from PIL import Image
from pdf2image import convert_from_path
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

    return send_file(path, as_attachment=True, mimetype="application/pdf")


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

        reader = PdfReader(input_path)

        output_files = []

        for i, page in enumerate(reader.pages):

            writer = PdfWriter()
            writer.add_page(page)

            output_filename = f"page_{i+1}.pdf"
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)

            with open(output_path, "wb") as output_file:
                writer.write(output_file)

            output_files.append(output_filename)

        return render_template("split_result.html", files=output_files)

    return render_template("split.html")


@app.route("/jpg-to-pdf", methods=["GET", "POST"])
def jpg_to_pdf():

    if request.method == "POST":

        files = request.files.getlist("images")

        images = []

        for file in files:

            if file.filename != "":

                filename = secure_filename(file.filename)
                path = os.path.join(UPLOAD_FOLDER, filename)

                file.save(path)

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

@app.route("/pdf-to-jpg", methods=["GET", "POST"])
def pdf_to_jpg():

    if request.method == "POST":

        file = request.files["pdf"]

        if file.filename == "":
            return "No file selected"

        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)

        if platform.system() == "Windows":
            images = convert_from_path(
            input_path,dpi=150,
            thread_count=4,
            fmt="jpeg",
            poppler_path=r"C:\Program Files\Release-25.12.0-0\poppler-25.12.0\Library\bin"
            )
        else:
            images = convert_from_path(input_path, 
            dpi=150,
            thread_count=4,
            fmt="jpeg")

        output_files = []

        for i, image in enumerate(images):

            output_filename = f"page_{i+1}.jpg"
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)

            image.save(output_path, "JPEG")

            output_files.append(output_filename)

        return render_template("pdf_to_jpg_result.html", files=output_files)

    return render_template("pdf_to_jpg.html")

    from PyPDF2 import PdfReader, PdfWriter


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

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            page.rotate(rotation)
            writer.add_page(page)

        output_filename = f"rotated_{filename}"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

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

        reader = PdfReader(input_path)
        writer = PdfWriter()

        delete_pages = [int(p.strip()) - 1 for p in pages_to_delete.split(",")]

        for i, page in enumerate(reader.pages):

            if i not in delete_pages:
                writer.add_page(page)

        output_filename = f"edited_{filename}"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        with open(output_path, "wb") as output_file:
            writer.write(output_file)

        return send_file(output_path, as_attachment=True)

    return render_template("delete_pages.html")

@app.route("/pdf-to-word", methods=["GET", "POST"])
def pdf_to_word():

    if request.method == "POST":

        file = request.files["pdf"]

        if file.filename == "":
            return "No file selected"

        filename = secure_filename(file.filename)

        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)

        output_filename = filename.replace(".pdf", ".docx")
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

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

        output_filename = filename.replace(".docx", ".pdf")
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

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

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt(password)

        output_filename = f"protected_{filename}"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

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

        reader = PdfReader(input_path)

        if reader.is_encrypted:
            reader.decrypt(password)

        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        output_filename = f"unlocked_{filename}"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True)

    return render_template("unlock_pdf.html")

@app.route("/add-page-numbers", methods=["GET", "POST"])
def add_page_numbers():

    if request.method == "POST":

        file = request.files["pdf"]

        if file.filename == "":
            return "No file selected"

        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)

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

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:

            page.clear()

            writer.add_page(page)

        output_filename = f"cleaned_{filename}"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

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

    if request.method == "POST":

        file = request.files["pdf"]

        if file.filename == "":
            return "No file selected"

        filename = secure_filename(file.filename)

        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)

        reader = PdfReader(input_path)

        images = []

        for page_number, page in enumerate(reader.pages):

            if "/XObject" in page["/Resources"]:

                xObject = page["/Resources"]["/XObject"].get_object()

                for obj in xObject:

                    if xObject[obj]["/Subtype"] == "/Image":

                        size = (xObject[obj]["/Width"], xObject[obj]["/Height"])

                        data = xObject[obj]._data

                        image_filename = f"image_{page_number+1}_{obj[1:]}.jpg"

                        image_path = os.path.join(UPLOAD_FOLDER, image_filename)

                        with open(image_path, "wb") as img_file:
                            img_file.write(data)

                        images.append(image_filename)

        return render_template("extract_images_result.html", images=images)

    return render_template("extract_images.html")

@app.route("/how-to-extract-images-from-pdf")
def extract_images_guide():
    return render_template("extract_images_guide.html")

@app.route("/pdf-to-png", methods=["GET", "POST"])
def pdf_to_png():

    if request.method == "POST":

        file = request.files["pdf"]

        if file.filename == "":
            return "No file selected"

        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(input_path)

        if platform.system() == "Windows":
            images = convert_from_path(
                input_path,
                dpi=200,
                poppler_path=r"C:\Program Files\Release-25.12.0-0\poppler-25.12.0\Library\bin"
            )
        else:
            images = convert_from_path(input_path, dpi=200)

        output_files = []

        for i, image in enumerate(images):

            output_filename = f"page_{i+1}.png"
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)

            image.save(output_path, "PNG")

            output_files.append(output_filename)

        return render_template("pdf_to_png_result.html", files=output_files)

    return render_template("pdf_to_png.html")

@app.route("/png-to-pdf", methods=["GET", "POST"])
def png_to_pdf():

    if request.method == "POST":

        files = request.files.getlist("images")

        images = []

        for file in files:

            if file.filename != "":

                filename = secure_filename(file.filename)
                path = os.path.join(UPLOAD_FOLDER, filename)

                file.save(path)

                image = Image.open(path).convert("RGB")
                images.append(image)

        output_filename = "converted_images.pdf"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        if images:

            images[0].save(
                output_path,
                save_all=True,
                append_images=images[1:]
            )

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




if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
