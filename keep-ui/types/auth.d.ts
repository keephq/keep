import type { DefaultSession } from "next-auth";
import type { JWT } from "next-auth/jwt";

declare module "next-auth" {
  interface Session {
    accessToken: string;
    tenantId?: string;
    userRole?: string;
    user: {
      id: string;
      name: string;
      email: string;
      image?: string;
      accessToken: string;
      tenantId?: string;
      role?: string;
    } & DefaultSession["user"];
  }

  interface User {
    id: string;
    name: string;
    email: string;
    accessToken: string;
    tenantId?: string;
    // a list of {"tenant_id": id, "tenant_name": name} objects
    tenantIds?: {
      tenant_id: string;
      tenant_name: string;
      tenant_logo_url?: string;
    }[];
    role?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken: string;
    tenantId?: string;
    role?: string;
  }
}

interface GuestSession {
  accessToken: "unauthenticated";
}
