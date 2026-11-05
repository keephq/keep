import { getKeepRoleFromKeycloak } from "../keycloakRole";

function createAccessToken(payload: object): string {
  const base64url = (input: string) =>
    Buffer.from(input)
      .toString("base64")
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  return [
    base64url('{"alg":"RS256","typ":"JWT"}'),
    base64url(JSON.stringify(payload)),
    "signature",
  ].join(".");
}

describe("getKeepRoleFromKeycloak", () => {
  it("returns the keep_role claim when it is a known role", () => {
    const token = createAccessToken({});
    expect(getKeepRoleFromKeycloak({ keep_role: "noc" }, token, "keep")).toBe(
      "noc"
    );
  });

  it("falls back to the access token when keep_role is not a known role", () => {
    const token = createAccessToken({
      resource_access: { keep: { roles: ["admin"] } },
    });
    expect(getKeepRoleFromKeycloak({ keep_role: "user" }, token, "keep")).toBe(
      "admin"
    );
  });

  it("resolves the role from the client roles of the access token", () => {
    const token = createAccessToken({
      resource_access: { keep: { roles: ["uma_protection", "noc"] } },
    });
    expect(getKeepRoleFromKeycloak({}, token, "keep")).toBe("noc");
  });

  it("prefers stronger roles when several are assigned", () => {
    const token = createAccessToken({
      resource_access: { keep: { roles: ["webhook", "noc", "admin"] } },
    });
    expect(getKeepRoleFromKeycloak({}, token, "keep")).toBe("admin");
  });

  it("returns null when the user has no known client role", () => {
    const token = createAccessToken({
      resource_access: { keep: { roles: ["uma_protection"] } },
    });
    expect(getKeepRoleFromKeycloak({}, token, "keep")).toBeNull();
  });

  it("returns null when the token has no roles for the client", () => {
    const token = createAccessToken({ resource_access: {} });
    expect(getKeepRoleFromKeycloak({}, token, "keep")).toBeNull();
  });

  it("ignores roles that belong to other clients", () => {
    const token = createAccessToken({
      resource_access: { "other-client": { roles: ["admin"] } },
    });
    expect(getKeepRoleFromKeycloak({}, token, "keep")).toBeNull();
  });

  it("returns null for a malformed access token", () => {
    expect(getKeepRoleFromKeycloak({}, "not-a-jwt", "keep")).toBeNull();
  });

  it("returns null when the access token or client id is missing", () => {
    expect(getKeepRoleFromKeycloak({}, undefined, "keep")).toBeNull();
    expect(getKeepRoleFromKeycloak({}, "some-token", undefined)).toBeNull();
    expect(getKeepRoleFromKeycloak(undefined, undefined, undefined)).toBeNull();
  });

  it("supports non-ascii characters inside the token payload", () => {
    const token = createAccessToken({
      preferred_username: "用户@example.com",
      resource_access: { keep: { roles: ["noc"] } },
    });
    expect(getKeepRoleFromKeycloak({}, token, "keep")).toBe("noc");
  });
});
