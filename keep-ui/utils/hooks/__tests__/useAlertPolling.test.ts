import { parsePollAlertsPayload } from "../useAlertPolling";

describe("parsePollAlertsPayload", () => {
  it("returns empty array for missing payload", () => {
    expect(parsePollAlertsPayload(null)).toEqual([]);
    expect(parsePollAlertsPayload(undefined)).toEqual([]);
  });

  it("parses fingerprints from object payload", () => {
    expect(
      parsePollAlertsPayload({ fingerprints: ["fp-1", "fp-2"] })
    ).toEqual(["fp-1", "fp-2"]);
  });

  it("parses fingerprints from legacy string payload", () => {
    expect(parsePollAlertsPayload('{"fingerprints":["fp-1"]}')).toEqual([
      "fp-1",
    ]);
  });

  it("filters invalid fingerprint values", () => {
    expect(
      parsePollAlertsPayload({
        fingerprints: ["fp-1", "", 2, null, "fp-2"],
      })
    ).toEqual(["fp-1", "fp-2"]);
  });

  it("ignores extra status-transition fields and still returns fingerprints", () => {
    const payload = {
      fingerprints: ["fp-1", "fp-2"],
      alerts: [
        { fingerprint: "fp-1", status: "resolved", previous_status: "acknowledged" },
        { fingerprint: "fp-2", status: "firing", previous_status: null },
      ],
      statuses: { "fp-1": "resolved", "fp-2": "firing" },
      resolved_fingerprints: ["fp-1"],
    };
    expect(parsePollAlertsPayload(payload)).toEqual(["fp-1", "fp-2"]);
  });

  it("handles payload with status fields but empty fingerprints", () => {
    const payload = {
      fingerprints: [],
      alerts: [],
      statuses: {},
      resolved_fingerprints: [],
    };
    expect(parsePollAlertsPayload(payload)).toEqual([]);
  });
});
