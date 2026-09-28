import { renderHook } from "@testing-library/react";
import { useSession } from "next-auth/react";
import { useHydratedSession } from "../useHydratedSession";

jest.mock("next-auth/react", () => ({
  useSession: jest.fn(),
}));

describe("useHydratedSession", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete window.__NEXT_AUTH;
  });

  it("returns a loading session instead of undefined outside <SessionProvider>", () => {
    // In production builds next-auth's useSession() returns undefined when
    // there is no <SessionProvider>, e.g. inside app/global-error.tsx (#6546).
    (useSession as jest.Mock).mockReturnValue(undefined);

    const { result } = renderHook(() => useHydratedSession());

    expect(result.current).toBeDefined();
    expect(result.current.data).toBeNull();
    expect(result.current.status).toBe("loading");
  });

  it("returns the next-auth session when a provider is present", () => {
    const session = {
      data: { accessToken: "token", expires: "2099-01-01" },
      status: "authenticated",
      update: jest.fn(),
    };
    (useSession as jest.Mock).mockReturnValue(session);

    const { result } = renderHook(() => useHydratedSession());

    expect(result.current).toBe(session);
  });
});
