class TomeError(Exception):
    pass


class PDFExtractionError(TomeError):
    pass


class ChapterizationError(TomeError):
    pass


class ModelDownloadError(TomeError):
    pass


class GlossaryError(TomeError):
    pass


class PromptValidationError(TomeError):
    pass
