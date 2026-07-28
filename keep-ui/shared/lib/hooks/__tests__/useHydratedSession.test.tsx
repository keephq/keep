import { act, render, screen } from "@testing-library/react";
import type { Session } from "next-auth";
import type { ReactNode } from "react";
import { NextAuthProvider } from "@/app/auth-provider";
import { useHydratedSession } from "../useHydratedSession";

type SessionState = {
  data: Session | null | undefined;
  status: "authenticated" | "loading" | "unauthenticated";
  update: jest.Mock;
};

let mockInitialClientState: SessionState | undefined;
let mockSetSessionState:
  React.Dispatch<React.SetStateAction<SessionState>> | undefined;
const mockUpdate = jest.fn();

jest.mock("next-auth/react", () => {
  const React = jest.requireActual<typeof import("react")>("react");
  const SessionContext = React.createContext<SessionState | undefined>(
    undefined
  );

  return {
    SessionProvider: ({
      children,
      session,
    }: {
      children: ReactNode;
      session?: Session | null;
    }) => {
      const [sessionState, setSessionState] = React.useState<SessionState>(
        session
          ? {
              data: session,
              status: "authenticated",
              update: mockUpdate,
            }
          : (mockInitialClientState ?? {
              data: null,
              status: "unauthenticated",
              update: mockUpdate,
            })
      );

      mockSetSessionState = setSessionState;

      return (
        <SessionContext.Provider value={sessionState}>
          {children}
        </SessionContext.Provider>
      );
    },
    useSession: () => {
      const sessionState = React.useContext(SessionContext);

      if (!sessionState) {
        throw new Error("useSession must be wrapped in a SessionProvider");
      }

      return sessionState;
    },
  };
});

const oauth2ProxySession: Session = {
  accessToken: "oauth2-proxy-access-token",
  tenantId: "keep",
  expires: "2099-01-01T00:00:00.000Z",
  user: {
    id: "oauth2-proxy-user",
    name: "OAuth2 Proxy User",
    email: "oauth2-proxy@example.com",
    accessToken: "oauth2-proxy-access-token",
    tenantId: "keep",
  },
};

function SessionConsumer() {
  const session = useHydratedSession();

  return (
    <div>
      <span data-testid="status">{session.status}</span>
      <span data-testid="access-token">
        {session.data?.accessToken ?? "no-token"}
      </span>
      <span data-testid="tenant">{session.data?.tenantId ?? "no-tenant"}</span>
    </div>
  );
}

function renderConsumer(session: Session | null) {
  return render(
    <NextAuthProvider session={session}>
      <SessionConsumer />
    </NextAuthProvider>
  );
}

describe("useHydratedSession", () => {
  beforeEach(() => {
    mockInitialClientState = undefined;
    mockSetSessionState = undefined;
    mockUpdate.mockReset();
  });

  it("uses the server-resolved OAuth2-Proxy session on the first render", () => {
    mockInitialClientState = {
      data: undefined,
      status: "loading",
      update: mockUpdate,
    };

    renderConsumer(oauth2ProxySession);

    expect(screen.getByTestId("status")).toHaveTextContent("authenticated");
    expect(screen.getByTestId("access-token")).toHaveTextContent(
      "oauth2-proxy-access-token"
    );
    expect(screen.getByTestId("tenant")).toHaveTextContent("keep");
  });

  it("returns a defined unauthenticated session context for null input", () => {
    renderConsumer(null);

    expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated");
    expect(screen.getByTestId("access-token")).toHaveTextContent("no-token");
    expect(screen.getByTestId("tenant")).toHaveTextContent("no-tenant");
  });

  it("stays defined while the client session transitions from loading to authenticated", () => {
    mockInitialClientState = {
      data: undefined,
      status: "loading",
      update: mockUpdate,
    };

    renderConsumer(null);

    expect(screen.getByTestId("status")).toHaveTextContent("loading");
    expect(screen.getByTestId("access-token")).toHaveTextContent("no-token");

    act(() => {
      mockSetSessionState?.({
        data: oauth2ProxySession,
        status: "authenticated",
        update: mockUpdate,
      });
    });

    expect(screen.getByTestId("status")).toHaveTextContent("authenticated");
    expect(screen.getByTestId("access-token")).toHaveTextContent(
      "oauth2-proxy-access-token"
    );
  });

  it("uses an explicit unauthenticated state after an empty client refresh", () => {
    renderConsumer(oauth2ProxySession);

    act(() => {
      mockSetSessionState?.({
        data: null,
        status: "unauthenticated",
        update: mockUpdate,
      });
    });

    expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated");
    expect(screen.getByTestId("access-token")).toHaveTextContent("no-token");
    expect(screen.getByTestId("tenant")).toHaveTextContent("no-tenant");
  });
});
