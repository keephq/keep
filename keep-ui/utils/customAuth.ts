import { AuthOptions, CallbacksOptions, Session } from "next-auth";
import {
  SessionContextValue,
  useSession as useNextAuthSession,
} from "next-auth/react";
import { getServerSession as useNextGetServerSession } from "next-auth/next";
import {
  GetServerSidePropsContext,
  NextApiRequest,
  NextApiResponse,
} from "next";

const isSingleTenant = process.env.AUTH_ENABLED == "false";

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
  if (isSingleTenant) {
    // Return a modified session object or perform any additional logic
    // specific to "single tenant" mode
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return useCustomSession() as R;
  }

  // eslint-disable-next-line react-hooks/rules-of-hooks
  return useNextGetServerSession(...args);
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
