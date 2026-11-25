import { AuthError } from "next-auth";

export class AuthenticationError extends AuthError {
  code = "authentication_error";
  constructor(message: string) {
    super(message);
    this.code = message;
  }
}

/**
 * Thrown when a user signs in via Keycloak without any known Keep role.
 * Uses NextAuth's client-safe "AccessDenied" type so NextAuth redirects the
 * user to the error page with a clear message, instead of creating a session
 * that the backend rejects on every API call (which used to cause an endless
 * frontend <-> Keycloak redirect loop).
 */
export class MissingRoleError extends AuthError {
  static type = "AccessDenied";
}

export const AuthErrorCodes = {
  INVALID_CREDENTIALS: "invalid_credentials",
  CONNECTION_REFUSED: "connection_refused",
  SERVICE_UNAVAILABLE: "service_unavailable",
  INVALID_TOKEN: "invalid_token",
  SERVER_ERROR: "server_error",
} as const;
