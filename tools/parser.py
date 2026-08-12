from pathlib import Path

from pypdf import PdfReader
from docx import Document


# TXT 파일에서 텍스트 추출
def parse_txt(file):
    if isinstance(file, (str, Path)):
        data = Path(file).read_bytes()

    else:
        file.seek(0)
        data = file.read()

    # 한글 TXT 파일 인코딩 대응
    for encoding in ["utf-8", "utf-8-sig", "cp949"]:
        try:
            return data.decode(encoding)

        except UnicodeDecodeError:
            pass

    raise ValueError("TXT 파일의 인코딩을 읽을 수 없습니다.")


# PDF 파일에서 텍스트 추출
def parse_pdf(file):
    if not isinstance(file, (str, Path)):
        file.seek(0)

    reader = PdfReader(file)
    pages = []

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            pages.append(page_text)

    return "\n".join(pages)


# DOCX 파일에서 텍스트 추출
def parse_docx(file):
    if not isinstance(file, (str, Path)):
        file.seek(0)

    document = Document(file)
    texts = []

    # 일반 문단 추출
    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            texts.append(paragraph.text)

    # 표 안의 텍스트 추출
    for table in document.tables:
        for row in table.rows:
            row_text = []

            for cell in row.cells:
                if cell.text.strip():
                    row_text.append(cell.text.strip())

            if row_text:
                texts.append(" | ".join(row_text))

    return "\n".join(texts)


# 파일 형식을 확인하고 텍스트 추출
def parse_document(file):
    # 로컬 파일 경로인 경우
    if isinstance(file, (str, Path)):
        filename = Path(file).name
        extension = Path(file).suffix.lower()

    # Streamlit UploadedFile 같은 파일 객체인 경우
    else:
        filename = file.name
        extension = Path(filename).suffix.lower()

    if extension == ".txt":
        text = parse_txt(file)

    elif extension == ".pdf":
        text = parse_pdf(file)

    elif extension == ".docx":
        text = parse_docx(file)

    else:
        raise ValueError(
            "지원하지 않는 파일 형식입니다. "
            "TXT, PDF, DOCX만 사용할 수 있습니다."
        )

    # 텍스트를 하나도 추출하지 못한 경우
    if not text.strip():
        raise ValueError("문서에서 텍스트를 추출하지 못했습니다.")

    # 운영체제에 따라 다른 줄바꿈을 \n으로 통일
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    return {
        "filename": filename,
        "text": text
    }