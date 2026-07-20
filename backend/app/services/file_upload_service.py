import logging
import uuid
from pathlib import Path
from typing import BinaryIO

from app.db.models.data_source_model import DataSource
from app.repositories.data_source_repository import DataSourceRepository
from app.schemas.data_source_schema import DataSourceType
from app.storage.base import FileStorage
from app.validators.file_upload_validator import FileUploadValidator

logger = logging.getLogger(__name__)


class FileUploadService:
    """Handles dataset file uploads: validation, storage, and registration."""

    def __init__(
        self,
        data_source_repository: DataSourceRepository,
        file_storage: FileStorage,
        upload_validator: FileUploadValidator,
        max_upload_size_bytes: int,
    ) -> None:
        self._data_source_repository = data_source_repository
        self._file_storage = file_storage
        self._upload_validator = upload_validator
        self._max_upload_size_bytes = max_upload_size_bytes

    def upload_dataset(
        self,
        original_filename: str | None,
        file_stream: BinaryIO,
        company_id: str | None = None,
        created_by_user_id: str | None = None,
    ) -> DataSource:
        detected_format = self._upload_validator.validate_uploaded_file(original_filename)

        file_extension = Path(original_filename or "").suffix.lower()
        stored_filename = f"{uuid.uuid4()}{file_extension}"

        file_size_bytes = self._file_storage.save_file(
            file_stream=file_stream,
            stored_filename=stored_filename,
            max_size_bytes=self._max_upload_size_bytes,
        )

        uploaded_data_source = DataSource(
            name=original_filename,
            source_type=DataSourceType.FILE.value,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_format=detected_format.value,
            file_size_bytes=file_size_bytes,
            company_id=company_id,
            created_by_user_id=created_by_user_id,
        )
        saved_data_source = self._data_source_repository.add_data_source(uploaded_data_source)
        logger.info(
            "Registered uploaded dataset %s (%s, %d bytes)",
            saved_data_source.id,
            original_filename,
            file_size_bytes,
        )
        return saved_data_source

    def delete_uploaded_file(self, data_source: DataSource) -> None:
        if data_source.stored_filename:
            self._file_storage.delete_file(data_source.stored_filename)