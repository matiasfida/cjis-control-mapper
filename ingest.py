import re
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.documents import Document

PDF_PATH = "data/source/CJIS_Security_Policy_v6-0_20241227.pdf"
SECTION_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+){1,5})\s+[A-Z]", flags=re.MULTILINE)
APPENDIX_PATTERN = re.compile(r"^\s*([A-Z])-\d+\b", flags=re.MULTILINE)


def extract_pages(pdf_path: str) -> list[dict]:
    reader = PdfReader(pdf_path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append({"page_number": i + 1, "text": text})
    return pages


def find_section_headers(text: str) -> list[tuple[int, str]]:
    """Detecta headers de sección numérica (5.x.y) y de apéndice (A-6, B-3, ...)."""
    headers = []
    for m in re.finditer(SECTION_PATTERN, text):
        headers.append((m.start(), m.group(1)))
    for m in re.finditer(APPENDIX_PATTERN, text):
        headers.append((m.start(), f"Appendix {m.group(1)}"))
    headers.sort(key=lambda h: h[0])
    return headers


def section_at_position(headers: list[tuple[int, str]], pos: int, default: str | None = None) -> str | None:
    """Última sección detectada antes de esta posición, arrancando desde `default` si no hay ninguna en este scope."""
    current = default
    for h_pos, h_num in headers:
        if h_pos <= pos:
            current = h_num
        else:
            break
    return current


def build_documents(pages: list[dict]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=150, separators=["\n\n", "\n", ". ", " "]
    )
    docs = []
    last_section = None  # se arrastra entre páginas

    for page in pages:
        text = page["text"]
        headers = find_section_headers(text)
        chunks = splitter.split_text(text)

        search_from = 0
        for chunk in chunks:
            probe = chunk[:60]
            idx = text.find(probe, search_from)
            if idx == -1:
                idx = text.find(probe)
            if idx != -1:
                search_from = idx

            section = section_at_position(headers, idx if idx != -1 else search_from, default=last_section)
            docs.append(Document(
                page_content=chunk,
                metadata={
                    "page": page["page_number"],
                    "section": section,
                    "source": "CJIS_Security_Policy_v6-0_20241227",
                },
            ))

        # actualizo la sección "activa" al cierre de esta página, para que la próxima la herede
        if headers:
            last_section = section_at_position(headers, len(text), default=last_section)

    return docs


if __name__ == "__main__":
    print("Extrayendo texto del PDF...")
    pages = extract_pages(PDF_PATH)
    print(f"  {len(pages)} páginas extraídas")

    print("Chunkeando...")
    docs = build_documents(pages)
    print(f"  {len(docs)} chunks generados")

    with_section = sum(1 for d in docs if d.metadata["section"])
    print(f"  {with_section}/{len(docs)} chunks con sección detectada ({100*with_section//len(docs)}%)")

    print("Indexando en Chroma...")
    vectorstore = Chroma.from_documents(
        documents=docs,
        persist_directory="./chroma_db",
        collection_name="cjis_security_policy_v6",
    )
    print("Listo. Índice persistido en ./chroma_db")