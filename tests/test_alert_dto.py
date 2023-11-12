from keep.api.models.alert import AlertDto


def test_alert_dto_fingerprint_none():
    name = "Alert name"
    alert_dto = AlertDto(
        id="1234",
        name=name,
        status="firing",
        lastReceived="2021-01-01T00:00:00.000Z",
        environment="production",
        isDuplicate=False,
        duplicateReason=None,
        service="backend",
        source=["keep"],
        message="Alert message",
        description="Alert description",
        severity="critical",
        fatigueMeter=0,
        pushed=True,
        event_id="1234",
        url="https://www.google.com/search?q=open+source+alert+management",
    )
    assert alert_dto.fingerprint == name
