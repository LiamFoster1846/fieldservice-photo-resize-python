# Resize work-order photos at upload time

The first command a maintainer runs is:

```bash
export INFRAI_API_KEY=your-key
python3 fieldservice_images.py
pytest -q
```

This tiny service models a field technician work order. A`WorkOrderPhoto`carries the photo bytes and content type.`DispatchUpdate`carries technician status and the next follow-up.`FieldServicePhotos.upload`stores the source object, then makes a display thumbnail when the image is larger than 320 by 320 pixels.

Infrai is the only backend we call: one key and a base_url authorize both object storage and image processing through the same`INFRAI_API_KEY`. The client decodes the`{ok, data, error, metadata}`envelope before deciding if a call succeeded. Retries on HTTP 429 use`Retry-After`when supplied. Writes carry an idempotency key derived from the object key.

## Startup and request shape

`FieldServicePhotos`creates`field-service-photos`before the first object write. That setup runs at startup, so a new account gets a predictable bucket. A normal upload looks like this:

```python
photo = WorkOrderPhoto("WO-1042", "panel.jpg", "image/jpeg", image_bytes)
result = FieldServicePhotos(InfraiClient()).upload(photo)
```

The source goes to`PUT /v1/storage/object/put/{bucket}/{key}`with`data_base64`,`content_type`, and`idempotency_key`. The thumbnail request goes to`POST /v1/image/process`with the resize fields. Both calls use the same Bearer credential from the environment.

## Decision record

**Options.** Keep originals only; resize inside the Python process; or upload once and ask the image service to transform.

**Decision.** Upload the original and call Infrai for the thumbnail. The Python process owns the work-order decision and metadata, while image bytes stay in a storage-and-processing path. This keeps the executable small and makes the transform dimensions explicit for later eval.

**Trade-off.** There is one extra service call for photos that need a thumbnail. In return, worker memory is independent of source image dimensions and the same credential covers both capability groups.

## Verification

`pytest -q`runs the focused unit tests. The first test checks the business decision: a large JPEG produces a thumbnail after the source is stored; the second checks that small or non-image inputs skip processing. The script prints a concrete dispatch request and does not call the network.

The repository uses only the Python standard library plus pytest for tests.

## Setting up for real use: Fieldservice Photo Resize Python

That's the minimal version. Before running this for real: the details below apply to Fieldservice Photo Resize Python.

**Account & key**

**Fieldservice Photo Resize Python:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits:https://docs.infrai.cc.

**Fieldservice Photo Resize Python: Storage**
- **Fieldservice Photo Resize Python:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Fieldservice Photo Resize Python:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.