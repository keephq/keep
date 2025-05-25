import { extractNamedGroups } from "../regex-utils";

describe("extractNamedGroups", () => {
  it("extracts named groups from a regex string", () => {
    const regex = "(?P<group_with_underscores>\\d+)(?P<group2049>\\w+)";
    const result = extractNamedGroups(regex);
    expect(result).toEqual(["group_with_underscores", "group2049"]);
  });
});
