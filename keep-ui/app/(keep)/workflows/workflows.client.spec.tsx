import { fireEvent, getByText, render } from "@testing-library/react";
import { WorkflowsPage } from "./workflows.client";
import { Workflow } from "@/shared/api/workflows";
import { ApiClient } from "@/shared/api/ApiClient";

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

global.fetch = jest.fn((...args) => {
  if (args[0].includes("workflows")) {
    return Promise.resolve({
      json: () => Promise.resolve({ data: { workflows: [workflow] } }),
    });
  }
}) as jest.Mock;

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
  usePathname: () => "/workflows",
}));

describe("WorkflowsPage", () => {
  it("should render", () => {
    const { getByTestId } = render(<WorkflowsPage />);
    expect(getByTestId("workflow-list")).toHaveTextContent("Test Workflow");
  });

  it("should update list after workflow is deleted", () => {
    const { getByTestId } = render(<WorkflowsPage />);
    const threeDotsMenu = getByTestId("workflow-menu");
    fireEvent.click(threeDotsMenu);
    const deleteButton = getByText(threeDotsMenu, "Delete");
    fireEvent.click(deleteButton);

    expect(getByTestId("workflow-list")).not.toHaveTextContent("Test Workflow");
  });
});
