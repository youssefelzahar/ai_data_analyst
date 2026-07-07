from pathlib import Path

from app.schemas.data_source_schema import FileFormat

_EXTENSION_TO_FORMAT: dict[str, FileFormat] = {
    ".csv": FileFormat.CSV,
    ".xlsx": FileFormat.EXCEL,
    ".xls": FileFormat.EXCEL,
}


class UploadValidationError(Exception):
    """Raised when an uploaded file fails validation."""


class FileUploadValidator:
    """Validates uploaded dataset files before they are stored."""

    def validate_uploaded_file(self, original_filename: str | None) -> FileFormat:
        """Return the detected file format, or raise UploadValidationError."""
        if not original_filename or not original_filename.strip():
            raise UploadValidationError("The uploaded file has no filename.")

        file_extension = Path(original_filename).suffix.lower()
        detected_format = _EXTENSION_TO_FORMAT.get(file_extension)
        if detected_format is None:
            supported_extensions = ", ".join(sorted(_EXTENSION_TO_FORMAT))
            raise UploadValidationError(
                f"Unsupported file type '{file_extension or 'none'}'. "
                f"Supported types: {supported_extensions}."
            )
        return detected_format