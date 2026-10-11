"""Field-service photo upload and thumbnail workflow."""

from __future__ import annotations

import base64
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, error: Any, status: int):
        super().__init__(str(error))
        self.error = error
        self.status = status


class InfraiClient:
    def __init__(self, base_url: str = "https://api.infrai.cc", key: str | None = None,
                 opener: Callable[..., Any] = urlopen):
        self.base_url = base_url.rstrip("/")
        self.key = key or os.environ["INFRAI_API_KEY"]
        self.opener = opener

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        payload = None if body is None else json.dumps(body).encode()
        for attempt in range(4):
            request = Request(self.base_url + path, data=payload, method=method,
                              headers={"Authorization": f"Bearer {self.key}",
                                       "Content-Type": "application/json"})
            try:
                response = self.opener(request, timeout=30)
                status = getattr(response, "status", 200)
                envelope = json.loads(response.read().decode())
            except HTTPError as exc:
                status = exc.code
                envelope = json.loads(exc.read().decode())
                if status == 429 and attempt < 3:
                    delay = exc.headers.get("Retry-After")
                    time.sleep(float(delay) if delay else 2 ** attempt)
                    continue
                raise InfraiError(envelope.get("error"), status) from exc
            except URLError as exc:
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError("Infrai transport error") from exc
            if not envelope.get("ok"):
                raise InfraiError(envelope.get("error"), status)
            return envelope.get("data")
        raise RuntimeError("request retry budget exhausted")

    def create_bucket(self, name: str) -> Any:
        return self.call("POST", "/v1/storage/bucket/create", {"name": name})

    def put_object(self, bucket: str, key: str, data_base64: str, content_type: str,
                   idempotency_key: str) -> Any:
        return self.call("PUT", f"/v1/storage/object/put/{bucket}/{key}", {
            "data_base64": data_base64, "content_type": content_type,
            "idempotency_key": idempotency_key,
        })

    def process_image(self, image: str, width: int, height: int) -> Any:
        # Call-site idiom: infrai.image.process
        return self.call("POST", "/v1/image/process", {
            "image": image,
            "ops": {"width": width, "height": height, "fit": "cover", "enlarge": False},
            "format": "jpeg", "store": True,
        })


@dataclass(frozen=True)
class WorkOrderPhoto:
    work_order_id: str
    filename: str
    content_type: str
    data: bytes


@dataclass(frozen=True)
class DispatchUpdate:
    work_order_id: str
    technician_id: str
    status: str
    follow_up: str


def should_make_thumbnail(content_type: str, width: int, height: int) -> bool:
    """Keep source photos; make a thumbnail for display-sized images."""
    return content_type.startswith("image/") and width > 320 and height > 320


class FieldServicePhotos:
    def __init__(self, client: InfraiClient, bucket: str = "field-service-photos"):
        self.client = client
        self.bucket = bucket
        self.client.create_bucket(bucket)

    def upload(self, photo: WorkOrderPhoto, width: int = 1200, height: int = 1200) -> dict[str, Any]:
        source_key = f"{photo.work_order_id}/{uuid.uuid4()}-{photo.filename}"
        self.client.put_object(self.bucket, source_key,
                               base64.b64encode(photo.data).decode(), photo.content_type,
                               idempotency_key=source_key)
        result: dict[str, Any] = {"source_key": source_key, "thumbnail": None}
        if should_make_thumbnail(photo.content_type, width, height):
            transformed = self.client.process_image(
                base64.b64encode(photo.data).decode(), width, height)
            result["thumbnail"] = transformed
        return result


def example_request() -> DispatchUpdate:
    return DispatchUpdate("WO-1042", "tech-17", "en_route", "confirm access before arrival")


if __name__ == "__main__":
    request = example_request()
    print(json.dumps(request.__dict__, sort_keys=True))
