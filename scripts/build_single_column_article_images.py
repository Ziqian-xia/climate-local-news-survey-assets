#!/usr/bin/env python3
import html
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageChops


QSF = Path("Climate_Local_News_-_Initial_may14_revised_congress_lookup.qsf")
OUT = Path("treatment_article_images")

TITLES = {
    "treatment_article_heatwave_causal": "Record Heat Wave Strikes Region",
    "treatment_article_heatwave_contextual": "Record Heat Wave Strikes Region",
    "treatment_article_heatwave_no_mention": "Record Heat Wave Strikes Region",
    "treatment_article_flood_causal": "Devastating Floods Overwhelm Region",
    "treatment_article_flood_contextual": "Devastating Floods Overwhelm Region",
    "treatment_article_flood_no_mention": "Devastating Floods Overwhelm Region",
    "treatment_article_hurricane_causal": "Powerful Hurricane Devastates Coastal Region",
    "treatment_article_hurricane_contextual": "Powerful Hurricane Devastates Coastal Region",
    "treatment_article_hurricane_no_mention": "Powerful Hurricane Devastates Coastal Region",
    "treatment_article_wildfire_causal": "Wildfire Forces Mass Evacuations",
    "treatment_article_wildfire_contextual": "Wildfire Forces Mass Evacuations",
    "treatment_article_wildfire_no_mention": "Wildfire Forces Mass Evacuations",
    "treatment_article_drought_causal": "Drought Emergency Declared as Reservoirs Hit Record Lows",
    "treatment_article_drought_contextual": "Drought Emergency Declared as Reservoirs Hit Record Lows",
    "treatment_article_drought_no_mention": "Drought Emergency Declared as Reservoirs Hit Record Lows",
}


def latex_escape(value):
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "°": r"$^\circ$",
        "–": "-",
        "—": "-",
        "’": "'",
        "“": "``",
        "”": "''",
    }
    return "".join(replacements.get(ch, ch) for ch in value)


def plain_text(question_text):
    text = re.sub(r"<\s*/p\s*>", "\n\n", question_text, flags=re.I)
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


def paragraphs(tag, question_text):
    text = plain_text(question_text)
    title = TITLES[tag]
    if text.startswith(title):
        text = text[len(title):].strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) <= 1:
        # Original QSF text is sometimes flattened; split article body into readable paragraphs.
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks = []
        current = []
        for sentence in sentences:
            current.append(sentence)
            if len(" ".join(current)) > 360:
                chunks.append(" ".join(current))
                current = []
        if current:
            chunks.append(" ".join(current))
        paras = chunks
    return title, paras


def tex_document(title, paras):
    body = "\n\n".join(latex_escape(p) for p in paras)
    return rf"""\documentclass[10pt]{{article}}
\usepackage[T1]{{fontenc}}
\usepackage[utf8]{{inputenc}}
\usepackage[paperwidth=6.2in,paperheight=4.9in,margin=0.24in]{{geometry}}
\usepackage{{microtype}}
\usepackage{{newtxtext}}
\pagestyle{{empty}}
\setlength{{\parindent}}{{1.1em}}
\setlength{{\parskip}}{{0.05in}}

\begin{{document}}
\fontsize{{9.4}}{{10.9}}\selectfont
\begin{{center}}
{{\fontsize{{17}}{{19}}\selectfont\itshape {latex_escape(title)}}}
\end{{center}}
\vspace{{-0.05in}}
\hrule
\vspace{{0.12in}}

{body}

\vspace{{0.08in}}
\hrule
\end{{document}}
"""


def crop_whitespace(path):
    image = Image.open(path).convert("RGB")
    background = Image.new("RGB", image.size, (255, 255, 255))
    diff = ImageChops.difference(image, background)
    # Treat near-white antialiasing as whitespace.
    diff = diff.point(lambda value: 0 if value < 12 else 255)
    bbox = diff.getbbox()
    if not bbox:
        return
    margin = 22
    left = max(bbox[0] - margin, 0)
    upper = max(bbox[1] - margin, 0)
    right = min(bbox[2] + margin, image.size[0])
    lower = min(bbox[3] + margin, image.size[1])
    image.crop((left, upper, right, lower)).save(path)


def main():
    OUT.mkdir(exist_ok=True)
    data = json.loads(QSF.read_text())
    generated = []
    for element in data["SurveyElements"]:
        if element.get("Element") != "SQ":
            continue
        payload = element["Payload"]
        tag = payload.get("DataExportTag", "")
        if tag not in TITLES:
            continue
        condition = tag.removeprefix("treatment_article_")
        title, paras = paragraphs(tag, payload.get("QuestionText", ""))
        tex_path = OUT / f"{condition}.tex"
        pdf_path = OUT / f"{condition}.pdf"
        png_prefix = OUT / condition
        png_path = OUT / f"{condition}.png"
        tex_path.write_text(tex_document(title, paras), encoding="utf-8")
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            cwd=OUT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        subprocess.run(
            ["pdftoppm", "-png", "-r", "200", pdf_path.name, condition],
            cwd=OUT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        page = OUT / f"{condition}-1.png"
        if page.exists():
            page.replace(png_path)
        crop_whitespace(png_path)
        generated.append((condition, title, png_path))
    print(f"Generated {len(generated)} article images in {OUT}")
    for condition, title, png_path in generated:
        print(f"{condition},{png_path},{title}")


if __name__ == "__main__":
    main()
