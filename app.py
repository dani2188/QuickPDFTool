from flask import Flask, request, render_template, send_file
import subprocess
import os
import threading
import time
import platform
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Limit upload size (20MB)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def delete_file_later(file_path, delay=60):
    """Delete file after delay (seconds)"""
    def delete():
        time.sleep(delay)
        if os.path.exists(file_path):
            os.remove(file_path)

    threading.Thread(target=delete, daemon=True).start()


@app.route("/download/<filename>")
def download(filename):
    path = os.path.join(UPLOAD_FOLDER, filename)
    return send_file(path, as_attachment=True)


@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":

        if "pdf" not in request.files:
            return "No file uploaded", 400

        file = request.files["pdf"]

        if file.filename == "":
            return "No selected file", 400

        # Compression level
        compression_level = request.form.get("compression")

        if compression_level == "high":
            dpi = "72"
        elif compression_level == "medium":
            dpi = "150"
        else:
            dpi = "300"

        # Secure filename
        filename = secure_filename(file.filename)

        # Unique file name to prevent collisions
        unique_id = str(uuid.uuid4())

        input_filename = f"{unique_id}_{filename}"
        output_filename = f"{unique_id}_compressed_{filename}"

        input_path = os.path.join(UPLOAD_FOLDER, input_filename)
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        file.save(input_path)

        # Ghostscript command depending on OS
        if platform.system() == "Windows":
            gs_command = "gswin64c"
        else:
            gs_command = "gs"

        command = [
            gs_command,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            "-dDownsampleColorImages=true",
            f"-dColorImageResolution={dpi}",
            "-dDownsampleGrayImages=true",
            f"-dGrayImageResolution={dpi}",
            "-dDownsampleMonoImages=true",
            f"-dMonoImageResolution={dpi}",
            f"-sOutputFile={output_path}",
            input_path
        ]

        # Run Ghostscript
        subprocess.run(command, check=True)

        # File sizes
        original_size = os.path.getsize(input_path)
        compressed_size = os.path.getsize(output_path)

        original_mb = round(original_size / (1024 * 1024), 2)
        compressed_mb = round(compressed_size / (1024 * 1024), 2)

        reduction = round((1 - compressed_size / original_size) * 100, 1)

        # Delete files later
        delete_file_later(input_path)
        delete_file_later(output_path)

        return render_template(
            "result.html",
            file_name=output_filename,
            original_size=original_mb,
            compressed_size=compressed_mb,
            reduction=reduction
        )

    return render_template("index.html")


@app.errorhandler(413)
def too_large(e):
    return "File too large. Maximum size is 20MB.", 413


if __name__ == "__main__":
    app.run(debug=True)