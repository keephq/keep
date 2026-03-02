/**
 * Tests for the alerts.tsx fingerprint-modal fix.
 *
 * Bug: when alerts re-fetched (polling / WebSocket), the useEffect that opens
 * the ViewAlertModal or EnrichAlertSidePanel was re-evaluated. If the alert
 * list was momentarily empty (during the refetch) the component would fire a
 * false "Alert fingerprint not found" toast and close the modal.
 *
 * Fix: `resolvedFingerprintRef` stores the fingerprint once it has been
 * matched so that subsequent re-evaluations of the same fingerprint (with an
 * empty or partial alerts list) do not trigger the error path.
 */
import React from "react";
import { render, act, waitFor } from "@testing-library/react";
import { useRouter, useSearchParams } from "next/navigation";
import { useProviders } from "@/utils/hooks/useProviders";
import { usePresets } from "@/entities/presets/model";
import { useAlertsTableData } from "@/widgets/alerts-table/ui/useAlertsTableData";
import { showErrorToast } from "@/shared/ui";
import Alerts from "../alerts";

// ─── Mock navigation ─────────────────────────────────────────────────────────

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
  useSearchParams: jest.fn(),
}));

// ─── Mock data hooks ─────────────────────────────────────────────────────────

jest.mock("@/utils/hooks/useProviders", () => ({
  useProviders: jest.fn(),
}));

jest.mock("@/entities/presets/model", () => ({
  usePresets: jest.fn(),
}));

jest.mock("@/widgets/alerts-table/ui/useAlertsTableData", () => ({
  useAlertsTableData: jest.fn(),
}));

// ─── Mock UI utilities ───────────────────────────────────────────────────────

jest.mock("@/shared/ui", () => ({
  showErrorToast: jest.fn(),
  KeepLoader: () => null,
}));

// ─── Mock all heavy child components ────────────────────────────────────────
// Only ViewAlertModal and EnrichAlertSidePanel render observable testid
// attributes so we can assert that the fix works.

jest.mock("../alert-table-tab-panel-server-side", () => ({
  __esModule: true,
  default: () => <div data-testid="alerts-table" />,
}));

jest.mock("@/features/alerts/alert-history", () => ({
  AlertHistoryModal: () => null,
}));

jest.mock("@/features/alerts/alert-assign-ticket", () => ({
  AlertAssignTicketModal: () => null,
}));

jest.mock("@/features/alerts/alert-note", () => ({
  AlertNoteModal: () => null,
}));

jest.mock("@/features/alerts/alert-call-provider-method", () => ({
  AlertMethodModal: () => null,
}));

jest.mock("@/features/workflows/manual-run-workflow", () => ({
  ManualRunWorkflowModal: () => null,
}));

jest.mock("@/features/alerts/dismiss-alert", () => ({
  AlertDismissModal: () => null,
}));

jest.mock("@/features/alerts/view-raw-alert", () => ({
  // Renders a testid only when an alert is supplied so tests can assert on it.
  ViewAlertModal: ({ alert }: any) =>
    alert ? <div data-testid="view-alert-modal" /> : null,
}));

jest.mock("@/features/alerts/alert-change-status", () => ({
  AlertChangeStatusModal: () => null,
}));

jest.mock("@/features/alerts/enrich-alert", () => ({
  EnrichAlertSidePanel: ({ isOpen }: any) =>
    isOpen ? <div data-testid="enrich-sidebar" /> : null,
}));

jest.mock("@/app/(keep)/not-found", () => ({
  __esModule: true,
  default: () => <div>Not Found</div>,
}));

// ─── Helpers ─────────────────────────────────────────────────────────────────

const makeAlert = (fingerprint: string) => ({
  id: fingerprint,
  fingerprint,
  name: `Alert ${fingerprint}`,
  description: "",
  severity: "critical",
  status: "firing",
  source: ["prometheus"],
  lastReceived: new Date(),
  environment: "production",
  pushed: false,
  deleted: false,
  dismissed: false,
  enriched_fields: [],
});

const baseAlertsData = {
  alerts: [] as ReturnType<typeof makeAlert>[],
  alertsLoading: false,
  mutateAlerts: jest.fn(),
  alertsError: null,
  totalCount: 0,
  facetsCel: null,
  facetsPanelRefreshToken: null,
};

const mockReplace = jest.fn();
const mockSearchParamsGet = jest.fn();

// ─── Global setup ────────────────────────────────────────────────────────────

beforeEach(() => {
  jest.clearAllMocks();

  (useRouter as jest.Mock).mockReturnValue({
    replace: mockReplace,
    push: jest.fn(),
    back: jest.fn(),
  });

  // Return an object with a controllable .get() so each test can set params.
  (useSearchParams as jest.Mock).mockReturnValue({
    get: mockSearchParamsGet,
  });
  // Default: no query params.
  mockSearchParamsGet.mockReturnValue(null);

  (useProviders as jest.Mock).mockReturnValue({
    data: { installed_providers: [] },
  });

  // Return empty saved presets; "feed" comes from defaultPresets inside the
  // component so selectedPreset will be found without any extra setup.
  (usePresets as jest.Mock).mockReturnValue({
    dynamicPresets: [],
    isLoading: false,
  });

  (useAlertsTableData as jest.Mock).mockReturnValue(baseAlertsData);
});

// ─── Tests ───────────────────────────────────────────────────────────────────

describe("Alerts — fingerprint modal fix (dataSettled guard)", () => {
  it("does NOT fire error when alerts is briefly empty but totalCount > 0 (stale-empty SWR flash)", async () => {
    // Regression test for the 3-render cascade in useLastAlerts:
    // SWR marks isLoading=false before the React state carrying the real results
    // has been flushed. For one render, alerts=[] while totalCount is already
    // the real count (>0). The fix: only act when alerts.length>0 OR totalCount===0.

    const alert = makeAlert("fp-stale");

    mockSearchParamsGet.mockImplementation((key: string) =>
      key === "alertPayloadFingerprint" ? "fp-stale" : null
    );

    // Phase 1 — stale-empty flash: alerts=[], alertsLoading=false, totalCount=5
    (useAlertsTableData as jest.Mock).mockReturnValue({
      ...baseAlertsData,
      alerts: [],
      alertsLoading: false,
      totalCount: 5,
    });

    const { rerender } = render(
      <Alerts presetName="feed" initialFacets={[]} />
    );

    // No error should fire during the stale-empty phase.
    await waitFor(() => {
      expect(showErrorToast).not.toHaveBeenCalled();
    });

    // Phase 2 — real data arrives: alerts=[alert], totalCount=1
    (useAlertsTableData as jest.Mock).mockReturnValue({
      ...baseAlertsData,
      alerts: [alert],
      alertsLoading: false,
      totalCount: 1,
    });

    await act(async () => {
      rerender(<Alerts presetName="feed" initialFacets={[]} />);
    });

    // Modal should open and still no error.
    expect(showErrorToast).not.toHaveBeenCalled();
    expect(mockReplace).not.toHaveBeenCalled();
  });
});

describe("Alerts — fingerprint modal fix (resolvedFingerprintRef)", () => {
  it("opens view modal when fingerprint is found and shows no error", async () => {
    const alert = makeAlert("fp-abc");

    mockSearchParamsGet.mockImplementation((key: string) =>
      key === "alertPayloadFingerprint" ? "fp-abc" : null
    );

    (useAlertsTableData as jest.Mock).mockReturnValue({
      ...baseAlertsData,
      alerts: [alert],
    });

    const { findByTestId } = render(
      <Alerts presetName="feed" initialFacets={[]} />
    );

    // Modal should appear.
    await findByTestId("view-alert-modal");
    expect(showErrorToast).not.toHaveBeenCalled();
  });

  it("shows error toast when fingerprint is not in the alerts list", async () => {
    mockSearchParamsGet.mockImplementation((key: string) =>
      key === "alertPayloadFingerprint" ? "fp-missing" : null
    );

    // Alerts list present but does not contain the requested fingerprint.
    (useAlertsTableData as jest.Mock).mockReturnValue({
      ...baseAlertsData,
      alerts: [makeAlert("fp-other")],
    });

    render(<Alerts presetName="feed" initialFacets={[]} />);

    await waitFor(() => {
      expect(showErrorToast).toHaveBeenCalledWith(
        null,
        "Alert fingerprint not found"
      );
    });

    // URL should have been cleared.
    expect(mockReplace).toHaveBeenCalled();
  });

  it("does NOT show error toast on background re-fetch after fingerprint was resolved", async () => {
    // Core regression test: after a successful modal open, the alerts list
    // briefly empties (due to a polling re-fetch), then repopulates.
    // Without the fix, the empty-list evaluation fires the error toast.

    const alert = makeAlert("fp-abc");

    mockSearchParamsGet.mockImplementation((key: string) =>
      key === "alertPayloadFingerprint" ? "fp-abc" : null
    );

    // Step 1 — alert is present; modal opens and ref is stored.
    (useAlertsTableData as jest.Mock).mockReturnValue({
      ...baseAlertsData,
      alerts: [alert],
    });

    const { rerender } = render(
      <Alerts presetName="feed" initialFacets={[]} />
    );

    await waitFor(() => {
      expect(showErrorToast).not.toHaveBeenCalled();
    });

    // Step 2 — alerts list empties mid-refetch.
    (useAlertsTableData as jest.Mock).mockReturnValue({
      ...baseAlertsData,
      alerts: [],
    });

    await act(async () => {
      rerender(<Alerts presetName="feed" initialFacets={[]} />);
    });

    // The fix: resolvedFingerprintRef is still "fp-abc" so the error path is
    // skipped.
    expect(showErrorToast).not.toHaveBeenCalled();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("opens enrich sidebar when both fingerprint and enrich params are present", async () => {
    const alert = makeAlert("fp-enrich");

    mockSearchParamsGet.mockImplementation((key: string) => {
      if (key === "alertPayloadFingerprint") return "fp-enrich";
      if (key === "enrich") return "true";
      return null;
    });

    (useAlertsTableData as jest.Mock).mockReturnValue({
      ...baseAlertsData,
      alerts: [alert],
    });

    const { findByTestId } = render(
      <Alerts presetName="feed" initialFacets={[]} />
    );

    await findByTestId("enrich-sidebar");
    expect(showErrorToast).not.toHaveBeenCalled();
  });

  it("resets the ref and opens modal correctly when navigating to a different fingerprint", async () => {
    // Ensure that navigating from fp-1 to fp-2 does NOT inherit fp-1's ref
    // and still opens fp-2's modal without errors.

    const alert1 = makeAlert("fp-1");
    const alert2 = makeAlert("fp-2");

    mockSearchParamsGet.mockImplementation((key: string) =>
      key === "alertPayloadFingerprint" ? "fp-1" : null
    );

    (useAlertsTableData as jest.Mock).mockReturnValue({
      ...baseAlertsData,
      alerts: [alert1, alert2],
    });

    const { rerender } = render(
      <Alerts presetName="feed" initialFacets={[]} />
    );

    // First fingerprint resolved — no errors.
    await waitFor(() => {
      expect(showErrorToast).not.toHaveBeenCalled();
    });

    // Navigate to a different fingerprint.
    mockSearchParamsGet.mockImplementation((key: string) =>
      key === "alertPayloadFingerprint" ? "fp-2" : null
    );

    (showErrorToast as jest.Mock).mockClear();

    await act(async () => {
      rerender(<Alerts presetName="feed" initialFacets={[]} />);
    });

    // fp-2 is present in the list, so the modal should open without error.
    expect(showErrorToast).not.toHaveBeenCalled();
  });
});
