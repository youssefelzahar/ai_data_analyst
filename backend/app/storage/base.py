from abc import ABC, abstractmethod
from typing import BinaryIO


class FileStorage(ABC):
    """Storage abstraction for uploaded dataset files.

    Services depend only on this interface, so the local-disk implementation
    can be swapped for object storage (e.g. MinIO/S3) without touching
    business logic.
    """

    @abstractmethod
    def save_file(self, file_stream: BinaryIO, stored_filename: str, max_size_bytes: int) -> int:
        """Persist a file stream under `stored_filename`.

        Returns the number of bytes written.
        Raises FileTooLargeError if the stream exceeds `max_size_bytes`.
        """

    @abstractmethod
    def delete_file(self, stored_filename: str) -> None:
        """Remove a stored file. Missing files are ignored."""

    @abstractmethod
    def get_file_path(self, stored_filename: str) -> str:
        """Return a local filesystem path for reading the stored file."""


class FileTooLargeError(Exception):
    def __init__(self, max_size_bytes: int) -> None:
        self.max_size_bytes = max_size_bytes
        super().__init__(f"File exceeds the maximum allowed size of {max_size_bytes} bytes")