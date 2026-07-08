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
});
