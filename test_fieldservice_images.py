from fieldservice_images import DispatchUpdate, FieldServicePhotos, InfraiClient, WorkOrderPhoto, should_make_thumbnail


class FakeClient:
    def __init__(self):
        self.calls = []

    def create_bucket(self, name):
        self.calls.append(("bucket", name))

    def put_object(self, bucket, key, data_base64, content_type, idempotency_key):
        self.calls.append(("put", bucket, content_type, idempotency_key))

    def process_image(self, image, width, height):
        self.calls.append(("process", width, height))
        return {"key": "thumb.jpg"}


def test_large_photo_is_stored_and_resized():
    client = FakeClient()
    service = FieldServicePhotos(client)
    result = service.upload(WorkOrderPhoto("WO-7", "meter.jpg", "image/jpeg", b"pixels"), 800, 600)
    assert result["thumbnail"] == {"key": "thumb.jpg"}
    assert [call[0] for call in client.calls] == ["bucket", "put", "process"]


def test_small_or_non_image_photo_skips_transform():
    assert not should_make_thumbnail("application/pdf", 1000, 1000)
    assert not should_make_thumbnail("image/jpeg", 300, 300)


def test_dispatch_model_keeps_follow_up():
    update = DispatchUpdate("WO-7", "tech-2", "complete", "send invoice")
    assert update.follow_up == "send invoice"
