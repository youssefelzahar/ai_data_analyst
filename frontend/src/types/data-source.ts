// Mirrors backend/app/schemas/data_source_schema.py — keep in sync.

export type DataSourceType = "file" | "sql_server";
export type FileFormat = "csv" | "excel";
export type AuthenticationType = "windows" | "sql_server";

export interface DataSource {
  id: string;
  name: string;
  source_type: DataSourceType;
  created_at: string;

  original_filename: string | null;
  file_format: FileFormat | null;
  file_size_bytes: number | null;

  server_host: string | null;
  database_name: string | null;
  authentication_type: AuthenticationType | null;
  username: string | null;
}

export interface SqlServerConnectionCreate {
  connection_name: string;
  server_host: string;
  database_name: string;
  authentication_type: AuthenticationType;
  username?: string;
  password?: string;
}

export interface ConnectionTestResult {
  success: boolean;
  message: string;
}