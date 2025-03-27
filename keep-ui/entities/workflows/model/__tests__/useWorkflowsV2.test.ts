import { useWorkflowsV2 } from "../useWorkflowsV2";
import { renderHook, waitFor } from "@testing-library/react";
import { useApi } from "@/shared/lib/hooks/useApi";
import { mockWorkflow } from "../__mocks__/mock-workflow";

describe("useWorkflowsV2", () => {
  const mockPost = jest.fn();

  beforeEach(() => {
    (useApi as jest.Mock).mockReturnValue({
      post: mockPost,
      isReady: () => true,
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("should return workflows", async () => {
    mockPost.mockResolvedValue({
      results: [mockWorkflow],
      count: 1,
      limit: 12,
      offset: 0,
    });

    const { result } = renderHook(() =>
      useWorkflowsV2({
        cel: "",
        limit: 12,
        offset: 0,
        sortBy: "created_at",
        sortDir: "desc",
      })
    );
    expect(result.current.isLoading).toEqual(true);

    await waitFor(() => {
      expect(result.current.isLoading).toEqual(false);
      expect(result.current.totalCount).toEqual(1);
      expect(result.current.workflows).toEqual([mockWorkflow]);
    });
  });
});
