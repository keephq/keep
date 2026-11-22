import React from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useHealth } from "../useHealth";

// Fresh SWR cache per test so results don't leak between tests.
const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(
    SWRConfig,
    { value: { provider: () => new Map(), dedupingInterval: 0 } },
    children
  );

describe("useHealth", () => {
  const originalTimeout = (AbortSignal as any).timeout;

  beforeAll(() => {
    // jsdom lacks AbortSignal.timeout, which useHealth passes to the request.
    if (typeof originalTimeout !== "function") {
      (AbortSignal as any).timeout = () => new AbortController().signal;
    }
  });

  afterAll(() => {
    (AbortSignal as any).timeout = originalTimeout;
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("does not call /healthcheck until the API client is ready", async () => {
    // Otherwise a missing session/config (e.g. on the global error page)
    // is reported as an unhealthy backend and hides the real error.
    const request = jest.fn();
    (useApi as jest.Mock).mockReturnValue({ isReady: () => false, request });

    const { result } = renderHook(() => useHealth(), { wrapper });

    await waitFor(() => expect(result.current.isHealthy).toBe(true));
    expect(request).not.toHaveBeenCalled();
  });

  it("reports unhealthy when the ready API's healthcheck fails", async () => {
    const request = jest.fn().mockRejectedValue(new Error("down"));
    (useApi as jest.Mock).mockReturnValue({ isReady: () => true, request });

    const { result } = renderHook(() => useHealth(), { wrapper });

    await waitFor(() => expect(result.current.isHealthy).toBe(false));
    expect(request).toHaveBeenCalledWith("/healthcheck", expect.any(Object));
  });
});
