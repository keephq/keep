import { Session } from "next-auth";
import {
  SessionContextValue,
  useSession as useNextAuthSession,
} from "next-auth/react";

const isSingleTenant = process.env.AUTH_ENABLED == "false";

type UpdateSession = (data?: any) => Promise<Session | null>;

function useCustomSession(): SessionContextValue {
  // Modify the session object or perform additional logic specific to "single tenant" mode
  // Here's an example where we add a custom property to the session object
  const modifiedSession = {
    data: {
      accessToken: "123",
    } as Session,
    status: "authenticated" as "authenticated",
    update: null as unknown as UpdateSession,
  };

  return modifiedSession;
}

export function useSession(): SessionContextValue {
  if (isSingleTenant) {
    // Return a modified session object or perform any additional logic
    // specific to "single tenant" mode
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return useCustomSession();
  }

  // eslint-disable-next-line react-hooks/rules-of-hooks
  const session = useNextAuthSession();

  // Return the original session object as is
  return session;
}
