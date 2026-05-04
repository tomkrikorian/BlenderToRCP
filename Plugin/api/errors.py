"""Structured command errors for headless API responses."""

from __future__ import annotations


class CommandError(RuntimeError):
    """Error carrying support-reporting metadata for CLI/API callers."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "COMMAND_FAILED",
        stage: str | None = None,
        details: list | dict | None = None,
        artifacts: dict | None = None,
        context: dict | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.details = details
        self.artifacts = artifacts or {}
        self.context = context or {}

    def to_response_error(self) -> dict:
        payload = {
            "code": self.code,
            "type": self.__class__.__name__,
            "message": str(self),
        }
        if self.stage:
            payload["stage"] = self.stage
        if self.details is not None:
            payload["details"] = self.details
        return payload
