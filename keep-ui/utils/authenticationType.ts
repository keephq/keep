
// AuthenticationType.ts

export enum AuthenticationType {
    MULTI_TENANT = "MULTI_TENANT",
    SINGLE_TENANT = "SINGLE_TENANT",
    KEYCLOAK = "KEYCLOAK",
    NO_AUTH = "NO_AUTH"  // Default
}

export const NoAuthUserEmail = "keep";
export const NoAuthTenant = "keep";
