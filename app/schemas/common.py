from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


class MessageResponse(BaseModel):
    message: str
    success: bool = True
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    message: str
    error_code: Optional[str] = None
    details: Optional[Any] = None
    success: bool = False


class FileUploadResponse(BaseModel):
    filename: str
    file_path: str
    file_size: int
    mime_type: str
    upload_date: datetime
    success: bool = True


class PaginationParams(BaseModel):
    page: int = 1
    size: int = 20
    
    class Config:
        validate_assignment = True
        
    def __init__(self, **data):
        super().__init__(**data)
        if self.page < 1:
            self.page = 1
        if self.size < 1:
            self.size = 20
        if self.size > 100:
            self.size = 100


class SortParams(BaseModel):
    sort_by: Optional[str] = None
    sort_order: str = "asc"  # asc or desc
    
    class Config:
        validate_assignment = True


class FilterParams(BaseModel):
    search: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    is_active: Optional[bool] = None


class ReportParams(BaseModel):
    format: str = "pdf"  # pdf, excel, csv
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    include_details: bool = True


class BulkOperationResponse(BaseModel):
    total_processed: int
    successful: int
    failed: int
    errors: List[str] = []
    success: bool = True


class HealthCheck(BaseModel):
    status: str = "healthy"
    timestamp: datetime
    version: str
    database: str = "connected"
    services: dict = {}


class APIResponse(BaseModel, Generic[T]):
    success: bool
    message: Optional[str] = None
    data: Optional[T] = None
    errors: Optional[List[str]] = None
    timestamp: datetime = datetime.utcnow()


class SearchParams(BaseModel):
    query: str
    filters: Optional[dict] = None
    sort_by: Optional[str] = None
    sort_order: str = "asc"
    page: int = 1
    size: int = 20


class ExportParams(BaseModel):
    format: str = "excel"  # excel, csv, pdf
    columns: Optional[List[str]] = None
    filters: Optional[dict] = None
    filename: Optional[str] = None