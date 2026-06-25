from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .auth import get_tenant_access_token
from .errors import BitableAttachmentUploadError, FeishuApiError
from .http import post_json, post_multipart


@dataclass
class BitableAttachmentUploadRequest:
    app_token: str
    attachment_paths: list[str]
    access_token: str | None = None
    endpoint: str = "https://open.feishu.cn"
    provider: str = "bitable_context_upload_user_identity"


@dataclass
class BitableAttachmentUploadResult:
    ok: bool
    status: str
    provider: str
    file_tokens: list[str]
    uploaded: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    message: str


class FeishuClient:
    """Feishu API client supporting both app_identity and user_identity modes.

    Usage:
        # App identity (tenant access token):
        client = FeishuClient(app_id="cli_xxx", app_secret="xxx")

        # User identity (user access token):
        client = FeishuClient(user_access_token="u-xxx")
    """

    def __init__(
        self,
        endpoint: str = "https://open.feishu.cn",
        app_id: str | None = None,
        app_secret: str | None = None,
        tenant_access_token: str | None = None,
        user_access_token: str | None = None,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.app_id = app_id
        self.app_secret = app_secret
        self._tenant_access_token = tenant_access_token
        self._user_access_token = user_access_token

    @property
    def _auth_token(self) -> str:
        """Get the active auth token. User token takes precedence."""
        if self._user_access_token:
            return self._user_access_token
        if self._tenant_access_token:
            return self._tenant_access_token
        if self.app_id and self.app_secret:
            self._tenant_access_token = get_tenant_access_token(
                self.endpoint, self.app_id, self.app_secret
            )
            return self._tenant_access_token
        raise FeishuApiError(
            "No authentication method configured. Provide either "
            "(app_id + app_secret) or user_access_token."
        )

    def _get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._auth_token}"}

    def _api_request(
        self,
        path: str,
        method: str = "GET",
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a Feishu Open API request with automatic authentication."""
        from urllib.parse import urlencode

        url = f"{self.endpoint}{path}"
        if query:
            url = f"{url}?{urlencode({k: v for k, v in query.items() if v is not None})}"

        if method == "GET":
            # For GET, we use post_json with empty body and custom method
            # Actually we need a separate get function, let's implement inline
            from urllib import request
            from .http import _read_json_response

            req = request.Request(url, headers=self._get_headers(), method="GET")
            return _read_json_response(req)
        elif method == "POST":
            return post_json(url, body or {}, headers=self._get_headers())
        else:
            raise ValueError(f"Unsupported method: {method}")

    #
    # Bitable Table Operations
    #

    def bitable_list_tables(self, app_token: str) -> list[dict[str, Any]]:
        """List all tables in a Bitable app with pagination."""
        page_token: str | None = None
        items: list[dict[str, Any]] = []
        while True:
            response = self._api_request(
                f"/open-apis/bitable/v1/apps/{app_token}/tables",
                query={"page_size": 100, "page_token": page_token},
            )
            data = response.get("data") or {}
            items.extend(list(data.get("items") or []))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
            if not page_token:
                break
        return items

    def bitable_list_fields(
        self, app_token: str, table_id: str
    ) -> list[dict[str, Any]]:
        """List all fields in a Bitable table with pagination."""
        page_token: str | None = None
        items: list[dict[str, Any]] = []
        while True:
            response = self._api_request(
                f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
                query={"page_size": 500, "page_token": page_token},
            )
            data = response.get("data") or {}
            items.extend(list(data.get("items") or []))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
            if not page_token:
                break
        return items

    def bitable_list_records(
        self, app_token: str, table_id: str
    ) -> list[dict[str, Any]]:
        """List all records in a Bitable table with pagination."""
        page_token: str | None = None
        items: list[dict[str, Any]] = []
        while True:
            response = self._api_request(
                f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                query={"page_size": 500, "page_token": page_token},
            )
            data = response.get("data") or {}
            items.extend(list(data.get("items") or []))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
            if not page_token:
                break
        return items

    def bitable_batch_create(
        self,
        app_token: str,
        table_id: str,
        records: list[dict[str, Any]],
        batch_size: int = 200,
    ) -> dict[str, Any]:
        """Batch create records with automatic chunking.

        Returns dict with 'total_written' and 'results' per chunk.
        """
        if not table_id:
            raise ValueError("Missing Bitable table_id.")

        total_written = 0
        results: list[dict[str, Any]] = []

        # Chunk records
        chunks: list[list[dict[str, Any]]] = []
        for i in range(0, len(records), max(1, min(batch_size, 500))):
            chunks.append(records[i : i + batch_size])

        for chunk in chunks:
            response = self._api_request(
                f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
                method="POST",
                body={"records": chunk},
            )
            data = response.get("data", {}) if isinstance(response, dict) else {}
            items = data.get("records", []) if isinstance(data, dict) else []
            count = len(items) if items else len(chunk)
            total_written += count
            results.append({"count": count, "response": response})

        return {"total_written": total_written, "results": results}

    def bitable_batch_update(
        self,
        app_token: str,
        table_id: str,
        records: list[dict[str, Any]],
        batch_size: int = 200,
    ) -> dict[str, Any]:
        """Batch update records with automatic chunking."""
        if not table_id:
            raise ValueError("Missing Bitable table_id.")

        total_written = 0
        results: list[dict[str, Any]] = []

        chunks: list[list[dict[str, Any]]] = []
        for i in range(0, len(records), max(1, min(batch_size, 500))):
            chunks.append(records[i : i + batch_size])

        for chunk in chunks:
            response = self._api_request(
                f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update",
                method="POST",
                body={"records": chunk},
            )
            data = response.get("data", {}) if isinstance(response, dict) else {}
            items = data.get("records", []) if isinstance(data, dict) else []
            count = len(items) if items else len(chunk)
            total_written += count
            results.append({"count": count, "response": response})

        return {"total_written": total_written, "results": results}

    #
    # Attachment Upload
    #

    @staticmethod
    def _choose_parent_type(path: str | Path) -> str:
        suffix = Path(path).suffix.lower()
        return (
            "bitable_image"
            if suffix in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
            else "bitable_file"
        )

    def bitable_upload_attachment(
        self,
        app_token: str,
        file_path: str | Path,
    ) -> dict[str, Any]:
        """Upload a single file to Bitable context.

        Returns: {path, file_name, file_token, parent_type, mime_type, size}
        """
        path = Path(file_path)
        if not path.exists():
            raise BitableAttachmentUploadError(
                f"Attachment file does not exist: {path}"
            )

        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        parent_type = self._choose_parent_type(path)
        response = post_multipart(
            f"{self.endpoint}/open-apis/drive/v1/medias/upload_all",
            fields={
                "file_name": path.name,
                "parent_type": parent_type,
                "parent_node": app_token,
                "size": str(path.stat().st_size),
            },
            file_field_name="file",
            file_name=path.name,
            file_bytes=path.read_bytes(),
            content_type=mime_type,
            headers=self._get_headers(),
        )
        data = response.get("data", {}) if isinstance(response, dict) else {}
        file_token = str(data.get("file_token") or "")
        if not file_token:
            raise BitableAttachmentUploadError(
                f"Feishu did not return file_token for {path.name}."
            )
        return {
            "path": str(path),
            "file_name": path.name,
            "file_token": file_token,
            "parent_type": parent_type,
            "mime_type": mime_type,
            "size": path.stat().st_size,
        }

    def bitable_batch_upload_attachments(
        self,
        request: BitableAttachmentUploadRequest,
    ) -> BitableAttachmentUploadResult:
        """Batch upload multiple files to Bitable context with error collection."""
        if not request.access_token and not self._user_access_token:
            raise BitableAttachmentUploadError(
                "Missing user access token for bitable-context attachment upload."
            )

        # Create a temporary client with the request's token if provided
        upload_client = self
        if request.access_token:
            upload_client = FeishuClient(
                endpoint=request.endpoint,
                user_access_token=request.access_token,
            )

        uploaded: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        file_tokens: list[str] = []

        for raw_path in request.attachment_paths:
            path = Path(raw_path)
            if not path.exists():
                errors.append(
                    {
                        "path": raw_path,
                        "code": "file_not_found",
                        "message": f"Attachment file does not exist: {raw_path}",
                    }
                )
                continue
            try:
                uploaded_item = upload_client.bitable_upload_attachment(
                    request.app_token, path
                )
                uploaded.append(uploaded_item)
                if uploaded_item.get("file_token"):
                    file_tokens.append(str(uploaded_item["file_token"]))
            except FeishuApiError as exc:
                errors.append(
                    {
                        "path": str(path),
                        "file_name": path.name,
                        "code": "upload_failed",
                        "message": str(exc),
                    }
                )

        ok = not errors and bool(uploaded)
        return BitableAttachmentUploadResult(
            ok=ok,
            status="completed" if ok else "partial_failed",
            provider=request.provider,
            file_tokens=file_tokens,
            uploaded=uploaded,
            errors=errors,
            message=(
                "Uploaded attachments to bitable context with user identity."
                if ok
                else "One or more attachments failed during bitable-context upload."
            ),
        )

    @staticmethod
    def build_attachment_field_value(file_tokens: list[str]) -> list[dict[str, str]]:
        """Build Bitable attachment field value from file tokens."""
        return [{"file_token": token} for token in file_tokens if str(token).strip()]

    #
    # IM Message Sending
    #

    def _upload_im_image(self, image_path: str | Path) -> str:
        """Upload an image via Feishu IM API, return image_key."""
        import json as _json

        path = Path(image_path)
        if not path.exists():
            raise FeishuApiError(f"IM image file does not exist: {path}")

        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        response = post_multipart(
            f"{self.endpoint}/open-apis/im/v1/images",
            fields={"image_type": "message"},
            file_field_name="image",
            file_name=path.name,
            file_bytes=path.read_bytes(),
            content_type=mime_type,
            headers=self._get_headers(),
        )
        data = response.get("data", {}) if isinstance(response, dict) else {}
        image_key = str(data.get("image_key") or "")
        if not image_key:
            raise FeishuApiError(
                f"Feishu did not return image_key for uploaded image: {_json.dumps(response)}"
            )
        return image_key

    def _send_im_message(
        self,
        receive_id: str,
        receive_id_type: str,
        msg_type: str,
        content: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a message via Feishu IM API."""
        import json as _json

        return self._api_request(
            path="/open-apis/im/v1/messages",
            method="POST",
            query={"receive_id_type": receive_id_type},
            body={
                "receive_id": receive_id,
                "msg_type": msg_type,
                "content": _json.dumps(content, ensure_ascii=False),
            },
        )

    def send_im_image(
        self,
        chat_id: str,
        image_path: str | Path,
        *,
        receive_id_type: str = "chat_id",
    ) -> dict[str, Any]:
        """Upload an image and send it as an image message to a Feishu chat.

        Two-step: upload image via IM API to get image_key, then send image message.

        Returns the send-message API response.
        """
        image_key = self._upload_im_image(image_path)
        return self._send_im_message(
            receive_id=chat_id,
            receive_id_type=receive_id_type,
            msg_type="image",
            content={"image_key": image_key},
        )

    def send_im_text(
        self,
        chat_id: str,
        text: str,
        *,
        receive_id_type: str = "chat_id",
    ) -> dict[str, Any]:
        """Send a plain text message to a Feishu chat.

        Returns the send-message API response.
        """
        return self._send_im_message(
            receive_id=chat_id,
            receive_id_type=receive_id_type,
            msg_type="text",
            content={"text": text},
        )
