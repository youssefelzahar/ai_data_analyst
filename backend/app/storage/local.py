from pathlib import Path
from typing import BinaryIO

from app.storage.base import FileStorage, FileTooLargeError

_CHUNK_SIZE_BYTES = 1024 * 1024  # 1 MiB


class LocalFileStorage(FileStorage):
    """Stores uploaded files on the local filesystem."""

    def __init__(self, upload_directory: str) -> None:
        self._upload_directory = Path(upload_directory)
        self._upload_directory.mkdir(parents=True, exist_ok=True)

    def save_file(self, file_stream: BinaryIO, stored_filename: str, max_size_bytes: int) -> int:
        destination_path = self._upload_directory / stored_filename
        bytes_written = 0
        try:
            with destination_path.open("wb") as destination_file:
                while chunk := file_stream.read(_CHUNK_SIZE_BYTES):
                    bytes_written += len(chunk)
                    if bytes_written > max_size_bytes:
                        raise FileTooLargeError(max_size_bytes)
                    destination_file.write(chunk)
        except FileTooLargeError:
            destination_path.unlink(missing_ok=True)
            raise
        return bytes_written

    def delete_file(self, stored_filename: str) -> None:
        (self._upload_directory / stored_filename).unlink(missing_ok=True)

    def get_file_path(self, stored_filename: str) -> str:
        return str(self._upload_directory / stored_filename)