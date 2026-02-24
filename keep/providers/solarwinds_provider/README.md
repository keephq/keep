# SolarWinds Provider

This provider ingests SolarWinds alert notifications into Keep over webhook.

## Expected payload

Send JSON with typical fields:

- `AlertObjectID`
- `AlertName`
- `Severity` (Information/Warning/Major/Critical)
- `NodeName`
- `EntityCaption`
- `Message`
- `TriggeredDateTime`
- `IsAcknowledged`
- `IsActive`
- `AlertDetailsUrl`

See `alerts_mock.py` for an example.
