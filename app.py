from flask import Flask, request, render_template, send_file, jsonify
import subprocess
import os
import threading
import time
import platform
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)

# limit upload size
app.config['MAX_CONTENT_LENGTH'] = 6 * 1024 * 1024

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

        command = [
            gs_command,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/screen",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={output_path}",
            input_path
        ]

        subprocess.run(command, check=True)

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
def download(filename):

    path = os.path.join(UPLOAD_FOLDER, filename)

    if not os.path.exists(path):
        return "File not ready", 404

    delete_file_later(path)

    return send_file(path, as_attachment=True, mimetype="application/pdf")


@app.route("/status/<filename>")
def status(filename):

    path = os.path.join(UPLOAD_FOLDER, filename)

    if os.path.exists(path):
        return jsonify({"ready": True})

    return jsonify({"ready": False})


@app.errorhandler(413)
def too_large(e):
    return "File too large. Maximum allowed size is 6MB.", 413