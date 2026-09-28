import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { useRouter } from "next/navigation";
import { ExecutionsTable } from "../ExecutionsTable";
import { PaginatedEnrichmentExecutionDto } from "@/shared/api/enrichment-events";

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}));

const executions: PaginatedEnrichmentExecutionDto = {
  items: [
    {
      id: "exec-1",
      rule_id: 42,
      status: "success",
      timestamp: "2026-08-17T10:00:00",
      alert_id: "alert-1",
    } as any,
  ],
  count: 1,
  limit: 20,
  offset: 0,
};

describe("ExecutionsTable", () => {
  const mockPush = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({ push: mockPush });
  });

  it("routes to the mapping execution page by default", () => {
    render(
      <ExecutionsTable executions={executions} setPagination={jest.fn()} />
    );

    fireEvent.click(screen.getByText("exec-1"));

    expect(mockPush).toHaveBeenCalledWith("/mapping/42/executions/exec-1");
  });

  it("routes to the extraction execution page when basePath is extraction", () => {
    render(
      <ExecutionsTable
        executions={executions}
        setPagination={jest.fn()}
        basePath="extraction"
      />
    );

    fireEvent.click(screen.getByText("exec-1"));

    expect(mockPush).toHaveBeenCalledWith("/extraction/42/executions/exec-1");
  });
});
