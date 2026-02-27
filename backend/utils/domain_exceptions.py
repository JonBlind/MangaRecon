from typing import Any, Optional

class DomainError(Exception):
    def __init__(self, *, status_code: int, code: str, message: str, detail=None):
        self.status_code = status_code
        self.code = code
        self.message = message        
        self.detail = detail          
        super().__init__(message)


class NotFoundError(DomainError):
    def __init__(self, *, code: str, message: str, detail: Optional[Any] = None):
        super().__init__(status_code=404, code=code, message=message, detail=detail)

class BadRequestError(DomainError):
    def __init__(self, *, code: str, message: str, detail: Optional[Any] = None):
        super().__init__(status_code=400, code=code, message=message, detail=detail)

class ConflictError(DomainError):
    def __init__(self, *, code: str, message: str, detail: Optional[Any] = None):
        super().__init__(status_code=409, code=code, message=message, detail=detail)


class ForbiddenError(DomainError):
    def __init__(self, *, code: str, message: str, detail: Optional[Any] = None):
        super().__init__(status_code=403, code=code, message=message, detail=detail)


class UnauthorizedError(DomainError):
    def __init__(self, *, code: str, message: str, detail: Optional[Any] = None):
        super().__init__(status_code=401, code=code, message=message, detail=detail)