import { renderHook } from "@testing-library/react";
import { useWorkflowExecutionsV2 } from "../useWorkflowExecutionsV2";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";

// Mock the dependencies
jest.mock("@/shared/lib/hooks/useApi");
jest.mock("next/navigation", () => ({
  useSearchParams: jest.fn(),
}));
jest.mock("swr");

const mockUseApi = useApi as jest.MockedFunction<typeof useApi>;
const mockUseSearchParams = useSearchParams as jest.MockedFunction<
  typeof useSearchParams
>;
const mockUseSWR = useSWR as jest.MockedFunction<typeof useSWR>;

describe("useWorkflowExecutionsV2", () => {
  const mockWorkflowId = "test-workflow-id";
  const mockApi = {
    isReady: jest.fn().mockReturnValue(true),
    get: jest.fn(),
    isServer: false,
    additionalHeaders: {},
    session: null,
    config: {},
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
    patch: jest.fn(),
    head: jest.fn(),
    options: jest.fn(),
    trace: jest.fn(),
    connect: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseApi.mockReturnValue(mockApi as any);
    mockUseSearchParams.mockReturnValue(
      // @ts-ignore
      new URLSearchParams()
    );
    mockUseSWR.mockReturnValue({
      data: null,
      error: null,
      isLoading: false,
      isValidating: false,
      mutate: jest.fn(),
    });
  });

  it("should use default limit and offset when no search params", () => {
    renderHook(() => useWorkflowExecutionsV2(mockWorkflowId));

    expect(mockUseSWR).toHaveBeenCalledWith(
      expect.stringContaining(
        "workflow-executions::list::test-workflow-id::25::0::"
      ),
      expect.any(Function)
    );
  });

  it("should use search params for limit and offset when provided", () => {
    const searchParams = new URLSearchParams();
    searchParams.set("limit", "50");
    searchParams.set("offset", "100");
    mockUseSearchParams.mockReturnValue(
      // @ts-ignore
      searchParams
    );

    renderHook(() => useWorkflowExecutionsV2(mockWorkflowId));

    expect(mockUseSWR).toHaveBeenCalledWith(
      expect.stringContaining(
        "workflow-executions::list::test-workflow-id::50::100::"
      ),
      expect.any(Function)
    );
  });

  it("should cap limit at 50 when exceeding 100", () => {
    const searchParams = new URLSearchParams();
    searchParams.set("limit", "150");
    mockUseSearchParams.mockReturnValue(
      // @ts-ignore
      searchParams
    );

    renderHook(() => useWorkflowExecutionsV2(mockWorkflowId));

    expect(mockUseSWR).toHaveBeenCalledWith(
      expect.stringContaining(
        "workflow-executions::list::test-workflow-id::50::0::"
      ),
      expect.any(Function)
    );
  });

  it("should use default limit when provided limit is <= 0", () => {
    const searchParams = new URLSearchParams();
    searchParams.set("limit", "0");
    mockUseSearchParams.mockReturnValue(
      // @ts-ignore
      searchParams
    );

    renderHook(() => useWorkflowExecutionsV2(mockWorkflowId));

    expect(mockUseSWR).toHaveBeenCalledWith(
      expect.stringContaining(
        "workflow-executions::list::test-workflow-id::25::0::"
      ),
      expect.any(Function)
    );
  });

  it("should not allow negative offset", () => {
    const searchParams = new URLSearchParams();
    searchParams.set("offset", "-10");
    mockUseSearchParams.mockReturnValue(
      // @ts-ignore
      searchParams
    );

    renderHook(() => useWorkflowExecutionsV2(mockWorkflowId));

    expect(mockUseSWR).toHaveBeenCalledWith(
      expect.stringContaining(
        "workflow-executions::list::test-workflow-id::25::0::"
      ),
      expect.any(Function)
    );
  });

  it("should include additional search params in the cache key", () => {
    const searchParams = new URLSearchParams();
    searchParams.set("status", "completed");
    searchParams.set("sort", "desc");
    mockUseSearchParams.mockReturnValue(
      // @ts-ignore
      searchParams
    );

    renderHook(() => useWorkflowExecutionsV2(mockWorkflowId));

    expect(mockUseSWR).toHaveBeenCalledWith(
      expect.stringContaining("status=completed&sort=desc"),
      expect.any(Function)
    );
  });

  it("should return null cache key when api is not ready", () => {
    const mockApiNotReady = {
      ...mockApi,
      isReady: jest.fn().mockReturnValue(false),
    };
    mockUseApi.mockReturnValue(mockApiNotReady as any);

    const { result } = renderHook(() =>
      useWorkflowExecutionsV2(mockWorkflowId)
    );

    expect(mockUseSWR).toHaveBeenCalledWith(null, expect.any(Function));
  });
});
