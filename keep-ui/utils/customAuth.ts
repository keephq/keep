import { AuthOptions, CallbacksOptions, Session } from "next-auth";
import {
  SessionContextValue,
  UseSessionOptions,
  useSession as useNextAuthSession,
  getSession as useGetSession,
} from "next-auth/react";
import { getServerSession as useNextGetServerSession } from "next-auth/next";
import {
  GetServerSidePropsContext,
  NextApiRequest,
  NextApiResponse,
} from "next";

// Set to true if you want to use "single tenant" mode
const isSingleTenant = process.env.NEXT_PUBLIC_AUTH_ENABLED == "false";
// Set to true if you want to use "username/password" authentication
const useAuthentication = process.env.NEXT_PUBLIC_USE_AUTHENTICATION == "true";

type UpdateSession = (data?: any) => Promise<Session | null>;

type GetServerSessionOptions = Partial<Omit<AuthOptions, "callbacks">> & {
  callbacks?: Omit<AuthOptions["callbacks"], "session"> & {
    session?: (...args: Parameters<CallbacksOptions["session"]>) => any;
  };
};

type GetServerSessionParams<O extends GetServerSessionOptions> =
  | [GetServerSidePropsContext["req"], GetServerSidePropsContext["res"], O]
  | [NextApiRequest, NextApiResponse, O]
  | [O]
  | [];

function useCustomSession() {
  // Modify the session object or perform additional logic specific to "single tenant" mode
  // Here's an example where we add a custom property to the session object
  const modifiedSession = {
    data: {
      accessToken: "123",
    } as Session,
    status: "authenticated" as "authenticated",
    update: null as unknown as UpdateSession,
    user: undefined,
    accessToken: "123",
  };

  return modifiedSession;
}

export async function getServerSession<
  O extends GetServerSessionOptions,
  R = O["callbacks"] extends { session: (...args: any[]) => infer U }
    ? U
    : Session
>(...args: GetServerSessionParams<O>): Promise<R | null> {
  if (isSingleTenant && !useAuthentication) {
    // Return a modified session object or perform any additional logic
    // specific to "single tenant" mode
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return useCustomSession() as R;
  }

  // eslint-disable-next-line react-hooks/rules-of-hooks
  return useNextGetServerSession(...args);
}

export function useSession<R extends boolean>(
  options?: UseSessionOptions<R>
): SessionContextValue {
  if (isSingleTenant && !useAuthentication) {
    // Return a modified session object or perform any additional logic
    // specific to "single tenant" mode
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return useCustomSession();
  }

  let session;
  try {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    session = useNextAuthSession(options);
  } catch (e) {
    console.log(e);
    return {
      status: "unauthenticated",
      update: null as unknown as UpdateSession,
      data: null,
    };
  }

  // Return the original session object as is
  return session;
}

export function getSession(params?: any) {
  if (isSingleTenant) {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return Promise.resolve(useCustomSession());
  }

  // eslint-disable-next-line react-hooks/rules-of-hooks
  return useGetSession(params);
}
