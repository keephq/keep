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


export async function getServerSession<
  O extends GetServerSessionOptions,
  R = O["callbacks"] extends { session: (...args: any[]) => infer U }
    ? U
    : Session
>(...args: GetServerSessionParams<O>): Promise<R | null> {
  // eslint-disable-next-line react-hooks/rules-of-hooks
  return useNextGetServerSession(...args);
}

export function useSession<R extends boolean>(
  options?: UseSessionOptions<R>
): SessionContextValue {
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
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const session = useGetSession(params);
  return session;
}
