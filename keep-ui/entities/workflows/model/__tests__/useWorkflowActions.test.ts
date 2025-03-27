import { renderHook } from "@testing-library/react";
import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";
import { useWorkflowRevalidation } from "@/entities/workflows/model/useWorkflowRevalidation";
import { useApi } from "@/shared/lib/hooks/useApi";

jest.mock("@/entities/workflows/model/useWorkflowRevalidation");
jest.mock("@/shared/lib/hooks/useApi");

describe("useWorkflowActions", () => {
  const mockRevalidateWorkflow = jest.fn();
  const mockRevalidateLists = jest.fn();
  const mockRequest = jest.fn();
  const mockDelete = jest.fn();

  beforeEach(() => {
    (useWorkflowRevalidation as jest.Mock).mockReturnValue({
      revalidateWorkflow: mockRevalidateWorkflow,
      revalidateLists: mockRevalidateLists,
    });

    (useApi as jest.Mock).mockReturnValue({
      request: mockRequest,
      delete: mockDelete,
      isReady: () => true,
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("should revalidate workflows after upload", async () => {
    const mockResponse = {
      workflow_id: "123",
      status: "created",
      revision: 1,
    };

    mockRequest.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useWorkflowActions());
    const uploadWorkflowFiles = result.current.uploadWorkflowFiles;

    // Create a mock FileList with a file
    const mockFile = new File([""], "test.yaml");
    const mockFileList = {
      length: 1,
      item: (index: number) => mockFile,
      [0]: mockFile,
      [Symbol.iterator]: function* () {
        yield mockFile;
      },
    } as unknown as FileList;

    await uploadWorkflowFiles(mockFileList);

    expect(mockRequest).toHaveBeenCalledWith("/workflows", expect.any(Object));
    expect(mockRevalidateWorkflow).toHaveBeenCalledWith(
      mockResponse.workflow_id
    );
    expect(mockRevalidateLists).toHaveBeenCalled();
  });

  it("should create workflow", async () => {
    const { result } = renderHook(() => useWorkflowActions());
    const createWorkflow = result.current.createWorkflow;

    const mockResponse = {
      workflow_id: "123",
      status: "created",
      revision: 1,
    };

    mockRequest.mockResolvedValue(mockResponse);

    await createWorkflow("<fake-workflow-yaml>");

    expect(mockRequest).toHaveBeenCalledWith(
      "/workflows/json",
      expect.any(Object)
    );
    expect(mockRevalidateWorkflow).toHaveBeenCalledWith(
      mockResponse.workflow_id
    );
  });

  it("should update workflow", async () => {
    const { result } = renderHook(() => useWorkflowActions());
    const updateWorkflow = result.current.updateWorkflow;

    await updateWorkflow("123", "<fake-workflow-yaml>");

    expect(mockRequest).toHaveBeenCalledWith(
      "/workflows/123",
      expect.any(Object)
    );
    expect(mockRevalidateWorkflow).toHaveBeenCalledWith("123");
  });

  it("should not delete workflow if user cancels confirmation", async () => {
    const { result } = renderHook(() => useWorkflowActions());
    const deleteWorkflow = result.current.deleteWorkflow;

    (window.confirm as jest.Mock).mockImplementation(() => false);
    await deleteWorkflow("123");

    expect(mockDelete).not.toHaveBeenCalled();
  });

  it("should delete workflow and revalidate workflows after confirmation", async () => {
    const { result } = renderHook(() => useWorkflowActions());
    const deleteWorkflow = result.current.deleteWorkflow;

    (window.confirm as jest.Mock).mockImplementation(() => true);
    await deleteWorkflow("123");

    expect(mockDelete).toHaveBeenCalledWith("/workflows/123");
    // NOTE: revalidateWorkflow calls revalidateLists
    expect(mockRevalidateWorkflow).toHaveBeenCalledWith("123");
  });
});
