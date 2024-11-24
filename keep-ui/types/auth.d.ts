import type { DefaultSession } from "@auth/core/types";

declare module "@auth/core/types" {
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
    };
  }

  interface User {
    id: string;
    name: string;
    email: string;
    accessToken: string;
    tenantId?: string;
    role?: string;
  }
}

declare module "@auth/core/jwt" {
  interface JWT {
    accessToken: string; // Changed to required
    tenantId?: string;
    role?: string;
  }
}
