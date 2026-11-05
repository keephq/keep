// Keep client roles, strongest first, so that resolving a user with more than
// one role always yields the same value. The role names match the backend
// `Roles` enum (keep/identitymanager/rbac.py).
const KNOWN_ROLES = ["admin", "noc", "workflowrunner", "webhook"] as const;

export type KeepRole = (typeof KNOWN_ROLES)[number];

/**
 * Extracts the Keep role a Keycloak sign-in should get.
 *
 * Sources, in order:
 * 1. the `keep_role` claim on the profile (mapped in Keycloak)
 * 2. the strongest known role inside `resource_access[clientId].roles` of
 *    the access token
 *
 * Returns null when the user has no known Keep role. Users without any Keep
 * client role are rejected by every backend API call, so sign-in must fail
 * with a clear error instead of creating a session that makes the browser
 * loop between the frontend and Keycloak forever.
 *
 * The JWT signature is not verified here: NextAuth has already validated the
 * token with Keycloak, we only need to read its claims.
 */
export function getKeepRoleFromKeycloak(
  profile: Record<string, unknown> | undefined | null,
  accessToken: string | undefined | null,
  clientId: string | undefined | null
): KeepRole | null {
  const keepRole = profile?.keep_role;
  if (
    typeof keepRole === "string" &&
    (KNOWN_ROLES as readonly string[]).includes(keepRole)
  ) {
    return keepRole as KeepRole;
  }

  if (!accessToken || !clientId) {
    return null;
  }

  const payload = decodeJwtPayload(accessToken);
  const resourceAccess = asRecord(asRecord(payload)?.["resource_access"]);
  const clientAccess = asRecord(resourceAccess?.[clientId]);
  const roles = clientAccess?.["roles"];
  if (!Array.isArray(roles)) {
    return null;
  }

  return KNOWN_ROLES.find((role) => roles.includes(role)) ?? null;
}

/** Narrows an unknown JSON value to a record, or null when it's not an object. */
function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : null;
}

/**
 * Decodes the payload segment of a JWT. Returns null for malformed tokens so
 * callers can treat them as "no role available" instead of crashing sign-in.
 */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const [, base64Payload] = token.split(".");
    if (!base64Payload) {
      return null;
    }
    // JWTs use base64url; normalize before decoding.
    const normalized = base64Payload.replace(/-/g, "+").replace(/_/g, "/");
    const binary = atob(normalized);
    const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
    // TextDecoder is unavailable in some environments (e.g. jest's jsdom),
    // where Node's Buffer covers it.
    const decoded =
      typeof TextDecoder !== "undefined"
        ? new TextDecoder().decode(bytes)
        : Buffer.from(bytes).toString("utf8");
    return JSON.parse(decoded);
  } catch (error) {
    console.warn("Failed to decode JWT payload:", error);
    return null;
  }
}
