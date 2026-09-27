import { renderHook } from "@testing-library/react";
import type { Session } from "next-auth";
import { NextAuthProvider } from "../auth-provider";
import { useHydratedSession } from "@/shared/lib/hooks/useHydratedSession";

jest.unmock("next-auth/react");

const session: Session = {
  user: {
    id: "proxy-user",
    name: "Proxy User",
    email: "user@example.com",
    accessToken: "oauth2proxy:user@example.com",
  },
  accessToken: "oauth2proxy:user@example.com",
  expires: "2099-01-01T00:00:00.000Z",
};

describe("NextAuthProvider", () => {
  it("provides the server session on the first render and after hydration", () => {
    const renders: string[] = [];
    const { result } = renderHook(
      () => {
        const value = useHydratedSession();
        renders.push(value.status);
        return value;
      },
      {
        wrapper: ({ children }) => (
          <NextAuthProvider session={session}>{children}</NextAuthProvider>
        ),
      }
    );

    expect(renders.every((status) => status === "authenticated")).toBe(true);
    expect(result.current.data).toEqual(session);
    expect(result.current.update).toEqual(expect.any(Function));
  });

  it("preserves an explicitly unauthenticated server session", () => {
    const { result } = renderHook(() => useHydratedSession(), {
      wrapper: ({ children }) => (
        <NextAuthProvider session={null}>{children}</NextAuthProvider>
      ),
    });

    expect(result.current.status).toBe("unauthenticated");
    expect(result.current.data).toBeNull();
  });
});
