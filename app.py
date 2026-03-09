from flask import Flask, request, render_template, send_file
import subprocess
import os
import threading
import time

app = Flask(__name__)

# Limit upload size to 20 MB
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def delete_file_later(file_path, delay=60):
    def delete():
        time.sleep(delay)
        if os.path.exists(file_path):
            os.remove(file_path)
    threading.Thread(target=delete).start()


@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":

        file = request.files["pdf"]

        input_path = os.path.join(UPLOAD_FOLDER, file.filename)
        output_path = os.path.join(UPLOAD_FOLDER, "compressed_" + file.filename)

        file.save(input_path)

        command = [
            "gs",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/screen",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={output_path}",
            input_path
        ]

        subprocess.run(command)

        # delete files later
        delete_file_later(input_path)
        delete_file_later(output_path)

        return send_file(output_path, as_attachment=True)

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)