// AuthenticationType.ts

export enum AuthenticationType {
    AUTH0 = "AUTH0",
    DB = "DB",
    KEYCLOAK = "KEYCLOAK",
    NOAUTH = "NOAUTH"  // Default
}

// Backward compatibility
export const MULTI_TENANT = AuthenticationType.AUTH0;
export const SINGLE_TENANT = AuthenticationType.DB;
export const NO_AUTH = AuthenticationType.NOAUTH;

export const NoAuthUserEmail = "keep";
export const NoAuthTenant = "keep";
