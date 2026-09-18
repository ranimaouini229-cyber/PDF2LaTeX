from flask import Flask, render_template, request, send_file
import fitz
import os
import shutil
import zipfile
from werkzeug.utils import secure_filename


app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def escape_latex(text):
    """Escape characters that have special meaning in LaTeX."""

    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }

    for character, replacement in replacements.items():
        text = text.replace(character, replacement)

    return text


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():

    file = request.files.get("pdf")

    if not file or file.filename == "":
        return "No PDF selected."

    if not file.filename.lower().endswith(".pdf"):
        return "Please upload a PDF file."

    # Clean the filename
    filename = secure_filename(file.filename)

    project_name = os.path.splitext(filename)[0]

    # Create project folder
    project_folder = os.path.join(
        UPLOAD_FOLDER,
        project_name
    )

    # Remove old version if it already exists
    if os.path.exists(project_folder):
        shutil.rmtree(project_folder)

    os.makedirs(project_folder)

    # Create images folder
    images_folder = os.path.join(
        project_folder,
        "images"
    )

    os.makedirs(images_folder)

    # Save uploaded PDF
    pdf_path = os.path.join(
        project_folder,
        filename
    )

    file.save(pdf_path)

    # Open PDF
    pdf = fitz.open(pdf_path)

    # Store generated LaTeX
    latex_parts = []

    # LaTeX document header
    latex_parts.append(r"\documentclass{article}")
    latex_parts.append(r"\usepackage{graphicx}")
    latex_parts.append(r"\usepackage{float}")
    latex_parts.append(r"\usepackage[utf8]{inputenc}")
    latex_parts.append(r"\usepackage[T1]{fontenc}")
    latex_parts.append("")

    latex_parts.append(r"\begin{document}")
    latex_parts.append("")

    image_count = 0

    # ==========================================
    # PROCESS EVERY PAGE
    # ==========================================

    for page_number, page in enumerate(pdf, start=1):

        # Page separator
        latex_parts.append(
            rf"\section*{{Page {page_number}}}"
        )

        latex_parts.append("")

        # ======================================
        # EXTRACT TEXT
        # ======================================

        blocks = page.get_text("dict")["blocks"]

        for block in blocks:

            # Some PDF blocks are images and don't
            # contain text lines.
            if "lines" not in block:
                continue

            for line in block["lines"]:

                line_text = ""

                font_sizes = []

                # Collect text from every span
                for span in line["spans"]:

                    line_text += span["text"]

                    font_sizes.append(
                        span["size"]
                    )

                line_text = line_text.strip()

                if not line_text:
                    continue

                # Protect special LaTeX characters
                line_text = escape_latex(line_text)

                # Calculate average font size
                average_size = (
                    sum(font_sizes) /
                    len(font_sizes)
                )

                # ==================================
                # BASIC HEADING DETECTION
                # ==================================

                if average_size >= 16:

                    latex_parts.append(
                        rf"\section{{{line_text}}}"
                    )

                elif average_size >= 13:

                    latex_parts.append(
                        rf"\subsection{{{line_text}}}"
                    )

                else:

                    latex_parts.append(
                        line_text
                    )

                latex_parts.append("")

        # ======================================
        # EXTRACT IMAGES
        # ======================================

        images = page.get_images(full=True)

        for image in images:

            xref = image[0]

            image_data = pdf.extract_image(xref)

            image_bytes = image_data["image"]

            image_ext = image_data["ext"]

            image_count += 1

            image_filename = (
                f"image_{image_count}.{image_ext}"
            )

            image_path = os.path.join(
                images_folder,
                image_filename
            )

            # Save image
            with open(
                image_path,
                "wb"
            ) as image_file:

                image_file.write(
                    image_bytes
                )

            # Add image to LaTeX
            latex_parts.append(
                r"\begin{figure}[H]"
            )

            latex_parts.append(
                r"\centering"
            )

            latex_parts.append(
                rf"\includegraphics[width=0.8\textwidth]"
                rf"{{images/{image_filename}}}"
            )

            latex_parts.append(
                r"\end{figure}"
            )

            latex_parts.append("")

    # ==========================================
    # FINISH LATEX DOCUMENT
    # ==========================================

    latex_parts.append(
        r"\end{document}"
    )

    # ==========================================
    # CLOSE PDF
    # ==========================================

    page_count = len(pdf)

    pdf.close()

    # ==========================================
    # CREATE .TEX FILE
    # ==========================================

    tex_path = os.path.join(
        project_folder,
        "document.tex"
    )

    with open(
        tex_path,
        "w",
        encoding="utf-8"
    ) as tex_file:

        tex_file.write(
            "\n".join(latex_parts)
        )

    # ==========================================
    # CREATE ZIP
    # ==========================================

    zip_path = os.path.join(
        UPLOAD_FOLDER,
        f"{project_name}_latex.zip"
    )

    if os.path.exists(zip_path):
        os.remove(zip_path)

    with zipfile.ZipFile(
        zip_path,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zip_file:

        for root, dirs, files in os.walk(
            project_folder
        ):

            for current_file in files:

                full_path = os.path.join(
                    root,
                    current_file
                )

                relative_path = os.path.relpath(
                    full_path,
                    project_folder
                )

                zip_file.write(
                    full_path,
                    relative_path
                )

    # ==========================================
    # SHOW RESULT PAGE
    # ==========================================

    return render_template(
        "result.html",

        filename=filename,

        project_name=project_name,

        page_count=page_count,

        image_count=image_count,

        download_name=(
            f"{project_name}_latex.zip"
        )
    )


@app.route("/download/<project_name>")
def download(project_name):

    zip_path = os.path.join(
        UPLOAD_FOLDER,
        f"{project_name}_latex.zip"
    )

    if not os.path.exists(zip_path):
        return "Project not found.", 404

    return send_file(
        zip_path,
        as_attachment=True
    )


if __name__ == "__main__":
    app.run(debug=True)