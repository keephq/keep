import { Workflow } from "@/shared/api/workflows";
import { useWorkflowsV2 } from "../useWorkflowsV2";
import { renderHook, waitFor } from "@testing-library/react";

jest.mock("next-auth/react", () => ({
  SessionProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  useSession: () => ({
    data: {
      user: {
        id: "test-user-id",
        name: "Test User",
        email: "test@example.com",
        image: null,
        accessToken: "test-token",
      },
      expires: "2024-12-31",
    },
    status: "authenticated",
  }),
}));

const workflow: Workflow = {
  id: "1",
  name: "Test Workflow",
  description: "Test Description",
  disabled: false,
  provisioned: false,
  created_by: "test",
  creation_time: "2023-01-01",
  interval: "1d",
  providers: [],
  triggers: [],
  last_execution_time: "2023-01-01",
  last_execution_status: "success",
  last_updated: "2023-01-01",
  workflow_raw: "workflow_raw",
  workflow_raw_id: "1",
};

jest.mock("@/shared/lib/hooks/useApi", () => ({
  useApi: () => ({
    isReady: () => true,
    post: (...args: any[]) => {
      return Promise.resolve({
        results: [workflow],
        count: 1,
        limit: 12,
        offset: 0,
      });
    },
  }),
}));

describe("useWorkflowsV2", () => {
  it("should return workflows", async () => {
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
      expect(result.current.workflows).toEqual([workflow]);
    });
  });
});
