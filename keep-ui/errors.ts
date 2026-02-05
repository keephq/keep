import { AuthError } from "next-auth";

export class AuthenticationError extends AuthError {
  code = "authentication_error";
  constructor(message: string) {
    super(message);
    this.code = message;
  }
}

export const AuthErrorCodes = {
  INVALID_CREDENTIALS: "invalid_credentials",
  CONNECTION_REFUSED: "connection_refused",
  SERVICE_UNAVAILABLE: "service_unavailable",
  INVALID_TOKEN: "invalid_token",
  SERVER_ERROR: "server_error",
} as const;
