// utils/authEnvUtils.ts
import { AuthType } from "@/utils/authenticationType";

export interface AuthEnvVars {
  [key: string]: string;
}

export function getAuthTypeEnvVars(authType: string | undefined): AuthEnvVars {
  const maskValue = (value: string | undefined) =>
    value ? value.slice(0, 6) + value.slice(6).replace(/[^-]/g, "X") : "NULL";

  switch (authType) {
    case AuthType.AZUREAD:
      return {
        KEEP_AZUREAD_TENANT_ID: maskValue(process.env.KEEP_AZUREAD_TENANT_ID),
        KEEP_AZUREAD_CLIENT_ID: maskValue(process.env.KEEP_AZUREAD_CLIENT_ID),
        KEEP_AZUREAD_CLIENT_SECRET: maskValue(
          process.env.KEEP_AZUREAD_CLIENT_SECRET
        ),
      };
    case AuthType.AUTH0:
      return {
        AUTH0_CLIENT_ID: maskValue(process.env.AUTH0_CLIENT_ID),
        AUTH0_CLIENT_SECRET: maskValue(process.env.AUTH0_CLIENT_SECRET),
        AUTH0_ISSUER: maskValue(process.env.AUTH0_ISSUER),
      };
    case AuthType.KEYCLOAK:
      return {
        KEYCLOAK_ID: maskValue(process.env.KEYCLOAK_ID),
        KEYCLOAK_SECRET: maskValue(process.env.KEYCLOAK_SECRET),
        KEYCLOAK_ISSUER: maskValue(process.env.KEYCLOAK_ISSUER),
      };
    case AuthType.DB:
      return {
        API_URL: maskValue(process.env.API_URL),
      };
    case AuthType.NOAUTH:
      return {};
    default:
      return {};
  }
}
