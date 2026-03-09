from flask import Flask, request, render_template, send_file
import subprocess
import os
import threading
import time
import platform
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)

# limit upload size (6MB recommended for Render free tier)
app.config['MAX_CONTENT_LENGTH'] = 6 * 1024 * 1024

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def delete_file_later(file_path, delay=300):
    """Delete file after delay (seconds)"""
    def delete():
        time.sleep(delay)
        if os.path.exists(file_path):
            os.remove(file_path)

    threading.Thread(target=delete, daemon=True).start()


def compress_pdf(input_path, output_path):

    print("Compression thread started")

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

        print("Running:", command)

        subprocess.run(command, check=True)

        print("Compression finished:", output_path)

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

        # get original file size
        original_size = os.path.getsize(input_path)
        original_mb = round(original_size / (1024 * 1024), 2)

        # start compression in background
        threading.Thread(
            target=compress_pdf,
            args=(input_path, output_path),
            daemon=True
        ).start()

        return render_template(
            "processing.html",
            file_name=output_filename,
            original_size=original_mb
        )

    return render_template("index.html")


@app.route("/download/<filename>")
def download(filename):

    path = os.path.join("uploads", filename)

    if not os.path.exists(path):
        return "File not ready", 404

    return send_file(path, as_attachment=True, mimetype="application/pdf")


@app.errorhandler(413)
def too_large(e):
    return "File too large. Maximum allowed size is 6MB.", 413


@app.route("/status/<filename>")
def status(filename):

    path = os.path.join("uploads", filename)

    if os.path.exists(path):
        return {"ready": True}

    return {"ready": False}


if __name__ == "__main__":
    app.run(debug=True)