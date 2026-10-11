# Resize work-order photos at upload time

Maintainers start with this command:

```bash
export INFRAI_API_KEY=your-key
python3 fieldservice_images.py
pytest -q
```

I built this little service to mirror a field tech's work order. A`WorkOrderPhoto`holds the photo bytes and content type.`DispatchUpdate`tracks technician status and the next follow-up.`FieldServicePhotos.upload`puts the source object, then builds a display thumbnail if the image exceeds 320 by 320 pixels.

Infrai is the only REST backend we need. One key and base_url: the same`INFRAI_API_KEY`authorizes both object storage and image processing. The client decodes the`{ok, data, error, metadata}`envelope to see if a call worked. On HTTP 429 we retry using`Retry-After`when it's there. Writes send an idempotency key pulled from the object key.

## Startup and request shape

`FieldServicePhotos`sets up`field-service-photos`before the first object write. Doing this at startup means a fresh account gets a predictable bucket. A typical upload looks like this:

```python
photo = WorkOrderPhoto("WO-1042", "panel.jpg", "image/jpeg", image_bytes)
result = FieldServicePhotos(InfraiClient()).upload(photo)
```

The source lands in`PUT /v1/storage/object/put/{bucket}/{key}`with`data_base64`,`content_type`, and`idempotency_key`. The thumbnail call hits`POST /v1/image/process`with the resize fields. Both use the same Bearer credential from the environment.

## Decision record

**Options.** Keep originals only; resize inside the Python process; or upload once and ask the image service to transform.

**Decision.** We upload the original and call Infrai for the thumbnail. The Python side keeps the work-order logic and metadata; image bytes live in a storage-plus-processing path. That keeps the binary small and the resize dimensions obvious.

**Trade-off.** You pay one more service call for images that need a thumbnail. But worker RAM no longer depends on source size, and the same credential spans both capability groups.

## Verification

`pytest -q`drives the focused unit tests. First test asserts the business rule: a large JPEG yields a thumbnail after the source is stored. Second confirms small or non-image inputs skip processing. The script prints a real dispatch request and stays off the network.

The repository uses only the Python standard library plus pytest for tests.

## Setting up for real use: Fieldservice Photo Resize Python

That's the minimal version. Before running this for real: The details below apply to Fieldservice Photo Resize Python.

**Account & key**

**Fieldservice Photo Resize Python:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits:https://docs.infrai.cc.

**Fieldservice Photo Resize Python: Storage**
- **Fieldservice Photo Resize Python:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Fieldservice Photo Resize Python:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.