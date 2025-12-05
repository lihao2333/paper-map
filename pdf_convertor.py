from tika import parser

class PdfConvertor:

    def __init__(self, pdf_path):
        self._pdf_path = pdf_path

    def convert_to_text(self):
        parsed = parser.from_file(self._pdf_path)
        return parsed['content'].strip()


