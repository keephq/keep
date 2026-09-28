import { renderHook } from "@testing-library/react";
import { useSession } from "next-auth/react";
import { useApi } from "../useApi";

// jest.setup.ts mocks useApi globally; this test needs the real hook.
jest.unmock("@/shared/lib/hooks/useApi");

jest.mock("next-auth/react", () => ({
  useSession: jest.fn(),
}));

describe("useApi", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("does not throw when rendered outside <SessionProvider> (#6546)", () => {
    // Previously: "Cannot destructure property 'data' of useSession() as it
    // is undefined", which crashed the global error page itself.
    (useSession as jest.Mock).mockReturnValue(undefined);

    const { result } = renderHook(() => useApi());

    expect(result.current.isReady()).toBe(false);
  });
});
