import { render, act } from "@testing-library/react";
import { useRouter } from "next/navigation";
import Maintenance from "../maintenance";
import { MaintenanceRule } from "../model";

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}));
jest.mock("@/utils/hooks/useMaintenanceRules", () => ({
  useMaintenanceRules: () => ({
    data: [{ id: 1 }],
    isLoading: false,
  }),
}));
jest.mock("@/app/(keep)/loading", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/shared/ui", () => ({
  EmptyStateCard: () => null,
}));
jest.mock("../create-or-update-maintenance-rule", () => ({
  __esModule: true,
  default: () => null,
}));

const mockTable: { editCallback?: (rule: MaintenanceRule) => void } = {};
jest.mock("../maintenance-rules-table", () => ({
  __esModule: true,
  default: (props: { editCallback: (rule: MaintenanceRule) => void }) => {
    mockTable.editCallback = props.editCallback;
    return null;
  },
}));

describe("Maintenance", () => {
  it("encodes the CEL query when a rule is opened for editing", () => {
    const replaceMock = jest.fn();
    (useRouter as jest.Mock).mockReturnValue({ replace: replaceMock });
    render(<Maintenance />);

    const cel = 'name == "Disk" && labels.database_id == "test:123"';
    act(() => mockTable.editCallback!({ cel_query: cel } as MaintenanceRule));

    expect(replaceMock).toHaveBeenCalledWith(
      `/maintenance?cel=${encodeURIComponent(cel)}`
    );
  });
});
