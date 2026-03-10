from flask import Flask, request, render_template, send_file, jsonify
import subprocess
import os
import threading
import time
import platform
import uuid
from werkzeug.utils import secure_filename
from PyPDF2 import PdfMerger
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
from pdf2image import convert_from_path
import platform

app = Flask(__name__)

# limit upload size
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

UPLOAD_FOLDER = "uploads"


# create uploads folder safely
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def delete_file_later(file_path, delay=300):
    def delete():
        time.sleep(delay)
        if os.path.exists(file_path):
            os.remove(file_path)

    threading.Thread(target=delete, daemon=True).start()


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

        # rename only when finished
        os.rename(temp_output, output_path)

    except Exception as e:
        print("Compression ERROR:", e)


@app.route("/", methods=["GET", "POST"])
def index():

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

        # start compression in background
        threading.Thread(
            target=compress_pdf,
            args=(input_path, output_path),
            daemon=True
        ).start()

        return render_template(
            "processing.html",
            file_name=output_filename
        )

    return render_template("index.html")


@app.route("/download/<filename>")
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
                input_path,
                poppler_path=r"C:\Program Files\Release-25.12.0-0\poppler-25.12.0\Library\bin"
            )
        else:
            images = convert_from_path(input_path)

        output_files = []

        for i, image in enumerate(images):

            output_filename = f"page_{i+1}.jpg"
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)

            image.save(output_path, "JPEG")

            output_files.append(output_filename)

        return render_template("pdf_to_jpg_result.html", files=output_files)

    return render_template("pdf_to_jpg.html")


if __name__ == "__main__":
    app.run(debug=True)