import logging
from typing import Optional
from io import BytesIO

logger = logging.getLogger(__name__)

class FileService:
    """
    Service for handling file uploads and parsing (PDF/DOCX).
    """

    @staticmethod
    def extract_text(content: bytes, filename: str) -> str:
        """
        Extract text from file content based on extension.
        """
        filename = filename.lower()
        
        if filename.endswith(".pdf"):
            return FileService._parse_pdf(content)
        elif filename.endswith(".docx"):
            return FileService._parse_docx(content)
        else:
            # Try plain text
            try:
                return content.decode("utf-8")
            except Exception:
                return "Unsupported file format. Please upload PDF or DOCX."

    @staticmethod
    def _parse_pdf(content: bytes) -> str:
        try:
            import pypdf
            reader = pypdf.PdfReader(BytesIO(content))
            text = "\n".join([page.extract_text() for page in reader.pages])
            return text if text.strip() else "Empty PDF content."
        except ImportError:
            logger.warning("pypdf not installed.")
            return "PDF Parser unavailable. Please install pypdf."
        except Exception as e:
            logger.error(f"PDF parsing error: {e}")
            return "Error parsing PDF file."

    @staticmethod
    def _parse_docx(content: bytes) -> str:
        try:
            import docx
            doc = docx.Document(BytesIO(content))
            return "\n".join([para.text for para in doc.paragraphs])
        except ImportError:
            logger.warning("python-docx not installed.")
            return "Docx module unavailable. Please install python-docx."
        except Exception as e:
            logger.error(f"DOCX parsing error: {e}")
            return "Error parsing DOCX file."
