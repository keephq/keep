import { renderHook } from "@testing-library/react";
import { useWorkflowRevalidation } from "@/entities/workflows/model/useWorkflowRevalidation";
import { useSWRConfig } from "swr";
import { workflowKeys } from "@/entities/workflows/model/workflowKeys";

// Mock the dependencies
jest.mock("swr");

const mockUseSWRConfig = useSWRConfig as jest.MockedFunction<
  typeof useSWRConfig
>;

describe("useWorkflowRevalidation", () => {
  const mockMutate = jest.fn();
  const mockWorkflowId = "test-workflow-id";

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseSWRConfig.mockReturnValue({
      mutate: mockMutate,
      cache: new Map(),
    } as any);
  });

  it("should revalidate workflow lists", () => {
    const { result } = renderHook(() => useWorkflowRevalidation());

    result.current.revalidateLists();

    // Verify that mutate was called with a function that matches list keys
    expect(mockMutate).toHaveBeenCalledTimes(1);
    const matcherFunction = mockMutate.mock.calls[0][0];
    expect(typeof matcherFunction).toBe("function");
    expect(matcherFunction("workflows::list::")).toBe(true);
    expect(matcherFunction("workflows::detail::")).toBe(false);
  });

  it("should revalidate specific workflow detail", () => {
    const { result } = renderHook(() => useWorkflowRevalidation());

    result.current.revalidateDetail(mockWorkflowId);

    expect(mockMutate).toHaveBeenCalledWith(
      workflowKeys.detail(mockWorkflowId)
    );
  });

  it("should revalidate both lists and specific workflow detail", () => {
    const { result } = renderHook(() => useWorkflowRevalidation());

    result.current.revalidateWorkflow(mockWorkflowId);

    expect(mockMutate).toHaveBeenCalledTimes(2);

    // Verify list matcher function
    const listMatcherFunction = mockMutate.mock.calls[0][0];
    expect(typeof listMatcherFunction).toBe("function");
    expect(listMatcherFunction("workflows::list::")).toBe(true);
    expect(listMatcherFunction("workflows::detail::")).toBe(false);

    // Verify detail key
    expect(mockMutate.mock.calls[1][0]).toBe(
      workflowKeys.detail(mockWorkflowId)
    );
  });
});
