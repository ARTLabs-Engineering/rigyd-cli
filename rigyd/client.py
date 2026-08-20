"""Blocking HTTP client for the Rigyd public conversion API.

Dependency-free (stdlib ``urllib`` + a hand-rolled multipart encoder). Every
method blocks; the high-level helpers in ``rigyd/__init__.py``, ``Job``, and the
CLI build on these.
"""

from __future__ import annotations

import json
import mimetypes
import os
import uuid
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from ._version import __version__
from .errors import RigydError

CLIENT_NAME = "rigyd"
# Sent as X-Rigyd-Client so the API can attribute usage per entry path
# (stored on each job as parameters.client). The CLI overrides this with "cli".
DEFAULT_CLIENT_TAG = "python-sdk"


def _mime_for(path: str) -> str:
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


def _encode_multipart(fields: Dict[str, str], files: List[tuple]) -> tuple:
    """(field, value) text parts + (name, filename, bytes, ctype) file parts."""
    boundary = f"----rigyd{uuid.uuid4().hex}"
    crlf = b"\r\n"
    out = bytearray()
    for name, value in fields.items():
        out += b"--" + boundary.encode() + crlf
        out += f'Content-Disposition: form-data; name="{name}"'.encode() + crlf + crlf
        out += str(value).encode() + crlf
    for field_name, filename, data, content_type in files:
        out += b"--" + boundary.encode() + crlf
        out += (
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"'.encode()
            + crlf
        )
        out += f"Content-Type: {content_type}".encode() + crlf + crlf
        out += data + crlf
    out += b"--" + boundary.encode() + b"--" + crlf
    return bytes(out), f"multipart/form-data; boundary={boundary}"


class RigydClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 120.0,
                 client_tag: str = DEFAULT_CLIENT_TAG):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.client_tag = client_tag

    def _request(self, method, path, *, body=None, content_type=None, accept_json=True):
        if not self.api_key:
            raise RigydError(
                "No API key. Run `rigyd login`, set RIGYD_API_KEY, or call "
                "rigyd.configure(api_key=...)."
            )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": f"{CLIENT_NAME}/{__version__}",
            "X-Rigyd-Client": self.client_tag,
        }
        if content_type:
            headers["Content-Type"] = content_type
        if accept_json:
            headers["Accept"] = "application/json"
        req = urllib.request.Request(f"{self.base_url}{path}", data=body,
                                     headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                return (json.loads(raw.decode("utf-8")) if raw else {}) if accept_json else raw
        except urllib.error.HTTPError as err:
            raise RigydError(self._extract_error(err), status=err.code) from err
        except urllib.error.URLError as err:
            raise RigydError(f"Cannot reach Rigyd API: {err.reason}") from err

    @staticmethod
    def _extract_error(err: "urllib.error.HTTPError") -> str:
        try:
            payload = json.loads(err.read().decode("utf-8"))
        except Exception:
            return f"HTTP {err.code} {err.reason}"
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                return error.get("message") or error.get("name") or f"HTTP {err.code}"
            if isinstance(error, str):
                return error
            data_error = (payload.get("data") or {}).get("error")
            if isinstance(data_error, str):
                return data_error
            if isinstance(payload.get("message"), str):
                return payload["message"]
        return f"HTTP {err.code}"

    def _post_json(self, path, payload):
        return self._request("POST", path, body=json.dumps(payload).encode("utf-8"),
                             content_type="application/json")

    # -- endpoints ---------------------------------------------------------
    def pricing(self) -> Dict[str, Any]:
        return self._request("GET", "/conversions/pricing").get("data", {})

    def me(self) -> Dict[str, Any]:
        return self._request("GET", "/me").get("data", {})

    def list_jobs(self, page: int = 1, page_size: int = 25) -> Dict[str, Any]:
        """Full response: {data: [...jobs], meta: {page, pageSize, pageCount, total}}."""
        return self._request("GET", f"/conversions?page={page}&pageSize={page_size}")

    def create_from_file(self, file_path: str,
                         target_triangle_count: Optional[int] = None) -> Dict[str, Any]:
        with open(file_path, "rb") as fh:
            data = fh.read()
        fields: Dict[str, str] = {}
        if target_triangle_count is not None:
            fields["optimize"] = "true"
            fields["target_triangle_count"] = str(int(target_triangle_count))
        body, ctype = _encode_multipart(
            fields, [("file", os.path.basename(file_path), data, _mime_for(file_path))])
        return self._request("POST", "/conversions", body=body, content_type=ctype).get("data", {})

    def get_job(self, job_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/conversions/{job_id}").get("data", {})

    def simulate(self, job_id: str, scene: Optional[str] = None) -> Dict[str, Any]:
        return self._post_json(f"/conversions/{job_id}/simulate",
                              {"scene": scene} if scene else {}).get("data", {})

    def download_result(self, job_id: str, dest_zip_path: str, fmt: str = "mjcf") -> str:
        raw = self._request("GET", f"/conversions/{job_id}/result?format={fmt}", accept_json=False)
        with open(dest_zip_path, "wb") as fh:
            fh.write(raw)
        return dest_zip_path
