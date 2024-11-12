// AuthenticationType.ts

export enum AuthenticationType {
  AUTH0 = "AUTH0",
  DB = "DB",
  KEYCLOAK = "KEYCLOAK",
  OAUTH2PROXY = "OAUTH2PROXY",
  AZUREAD = "AZUREAD",
  NOAUTH = "NOAUTH", // Default
}

// Backward compatibility
export const MULTI_TENANT = "MULTI_TENANT";
export const SINGLE_TENANT = "SINGLE_TENANT";
export const NO_AUTH = "NO_AUTH";

export const NoAuthUserEmail = "keep";
export const NoAuthTenant = "keep";
