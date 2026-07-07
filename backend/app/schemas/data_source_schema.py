from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataSourceType(str, Enum):
    FILE = "file"
    SQL_SERVER = "sql_server"


class FileFormat(str, Enum):
    CSV = "csv"
    EXCEL = "excel"


class AuthenticationType(str, Enum):
    WINDOWS = "windows"
    SQL_SERVER = "sql_server"


class SqlServerConnectionCreate(BaseModel):
    connection_name: str = Field(min_length=1, max_length=255)
    server_host: str = Field(min_length=1, max_length=255)
    database_name: str = Field(min_length=1, max_length=255)
    authentication_type: AuthenticationType
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_credentials_for_sql_authentication(self) -> "SqlServerConnectionCreate":
        if self.authentication_type == AuthenticationType.SQL_SERVER:
            if not self.username or not self.password:
                raise ValueError(
                    "username and password are required for SQL Server Authentication"
                )
        return self


class ConnectionTestResult(BaseModel):
    success: bool
    message: str


class DataSourceResponse(BaseModel):
    """Public representation of any data source. Credentials are never exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    source_type: DataSourceType
    created_at: datetime

    # Uploaded file fields (null for database connections)
    original_filename: str | None = None
    file_format: FileFormat | None = None
    file_size_bytes: int | None = None

    # SQL Server fields (null for uploaded files; password intentionally absent)
    server_host: str | None = None
    database_name: str | None = None
    authentication_type: AuthenticationType | None = None
    username: str | None = None