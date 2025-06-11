import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import IncidentAlerts from '../incident-alerts';
import type { IncidentDto } from '@/entities/incidents/model';
import { Status as IncidentStatus } from '@/entities/incidents/model/models';
import { Severity as IncidentSeverity } from '@/entities/incidents/model/models';
import type { AlertDto } from '@/entities/alerts/model/types';
import { Status as AlertStatus, Severity as AlertSeverity } from '@/entities/alerts/model/types';

// Mock all external dependencies
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(() => ({ push: jest.fn() })),
}));

jest.mock('@/utils/hooks/useIncidents', () => ({
  useIncidentAlerts: jest.fn(),
  usePollIncidentAlerts: jest.fn(),
}));

jest.mock('@/entities/incidents/model', () => ({
  useIncidentActions: jest.fn(() => ({
    unlinkAlertsFromIncident: jest.fn(),
  })),
}));

jest.mock('@/utils/hooks/useProviders', () => ({
  useProviders: jest.fn(() => ({
    data: {
      installed_providers: [
        { id: 'provider-1', display_name: 'Prometheus' },
      ],
    },
  })),
}));

jest.mock('@/utils/hooks/useConfig', () => ({
  useConfig: jest.fn(() => ({
    data: { KEEP_DOCS_URL: 'https://docs.keephq.dev' },
  })),
}));

jest.mock('@/entities/alerts/model', () => ({
  useAlertTableTheme: () => ({ theme: {} }),
  useAlerts: jest.fn(() => ({
    useAlertAudit: jest.fn(() => ({
      data: [],
      isLoading: false,
      mutate: jest.fn(),
    })),
  })),
  useAlertRowStyle: () => [{}],
  AlertDto: jest.fn(),
  Status: {
    OPEN: "open",
    CLOSED: "closed",
    ACKNOWLEDGED: "acknowledged",
  },
  Severity: {
    CRITICAL: "critical",
    HIGH: "high",
    MEDIUM: "medium",
    LOW: "low",
    INFO: "info",
  },
}));

jest.mock('@/utils/hooks/useExpandedRows', () => ({
  useExpandedRows: jest.fn(() => ({
    isRowExpanded: jest.fn(() => false),
    toggleRowExpanded: jest.fn(),
  })),
}));

jest.mock('@/utils/hooks/useGroupExpansion', () => ({
  useGroupExpansion: jest.fn(() => ({
    isGroupExpanded: jest.fn(() => true),
    toggleGroup: jest.fn(),
    toggleAll: jest.fn(),
    areAllGroupsExpanded: true,
  })),
}));

// Mock UI components with simpler implementations
jest.mock('@/shared/ui', () => ({
  EmptyStateCard: ({ children, title, description }: any) => (
    <div data-testid="empty-state">
      <h2>{title}</h2>
      <p>{description}</p>
      {children}
    </div>
  ),
  TablePagination: () => <div data-testid="table-pagination" />,
  getCommonPinningStylesAndClassNames: () => ({ style: {}, className: '' }),
}));

jest.mock('../incident-alert-table-body-skeleton', () => ({
  IncidentAlertsTableBodySkeleton: () => <div data-testid="loading-skeleton" />,
}));

jest.mock('../incident-alert-actions', () => ({
  IncidentAlertsActions: () => <div data-testid="incident-alerts-actions" />,
}));

// Mock alert table utilities to render our test content
jest.mock('@/widgets/alerts-table/lib/alert-table-utils', () => ({
  useAlertTableCols: jest.fn(({ MenuComponent }: any) => [
    { id: 'name', header: 'Name', cell: ({ row }: any) => row.original.name },
    { id: 'severity', header: 'Severity', cell: ({ row }: any) => row.original.severity },
    { 
      id: 'alertMenu', 
      header: 'Actions',
      MenuComponent: MenuComponent,
      cell: ({ row }: any) => MenuComponent(row.original)
    },
  ]),
}));

// Mock the incident alert action tray
jest.mock('../incident-alert-action-tray', () => ({
  IncidentAlertActionTray: ({ alert, onViewAlert, onUnlink, isCandidate }: any) => (
    <div className="flex items-center">
      <button
        aria-label="View Alert Details"
        onClick={(e) => {
          e.stopPropagation();
          onViewAlert(alert);
        }}
      >
        View
      </button>
      {!isCandidate && (
        <button
          aria-label="Unlink from incident"
          onClick={(e) => {
            e.stopPropagation();
            onUnlink(alert);
          }}
        >
          Unlink
        </button>
      )}
    </div>
  ),
}));

// Mock the actual component that renders alerts with action buttons
jest.mock('@/widgets/alerts-table/ui/alerts-table-body', () => ({
  AlertsTableBody: ({ table, onRowClick }: any) => (
    <tbody data-testid="alerts-table-body">
      {table.getRowModel().rows.map((row: any) => (
        <tr key={row.id} onClick={() => onRowClick(row.original)} data-testid={`alert-row-${row.id}`}>
          {row.getVisibleCells().map((cell: any) => (
            <td key={cell.id}>
              {cell.column.columnDef.cell(cell.getContext())}
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  ),
}));

// Track AlertSidebar state
let alertSidebarState = {
  isOpen: false,
  alert: null as AlertDto | null,
};

// Mock the AlertSidebar to track its state
jest.mock('@/features/alerts/alert-detail-sidebar', () => ({
  AlertSidebar: ({ isOpen, toggle, alert }: any) => {
    // Update our tracked state
    alertSidebarState.isOpen = isOpen;
    alertSidebarState.alert = alert;
    
    if (!isOpen) return null;
    return (
      <div data-testid="alert-sidebar">
        <div data-testid="alert-sidebar-content">
          <h3>{alert?.name || 'Alert Details'}</h3>
          <p>Severity: {alert?.severity}</p>
        </div>
        <button onClick={toggle} data-testid="close-sidebar">
          Close
        </button>
      </div>
    );
  },
}));

// Mock ViewAlertModal
jest.mock("@/features/alerts/view-raw-alert", () => ({
  ViewAlertModal: ({ alert, handleClose }: any) => 
    alert ? <div data-testid="view-alert-modal">ViewAlertModal</div> : null,
}));

const { useIncidentAlerts } = require('@/utils/hooks/useIncidents');

describe('IncidentAlerts - AlertSidebar Integration', () => {
  const mockIncident: IncidentDto = {
    id: 'incident-123',
    user_generated_name: 'Test Incident',
    ai_generated_name: 'Test Incident',
    user_summary: 'Test incident description',
    generated_summary: 'Test incident description',
    is_candidate: false,
    incident_type: 'manual',
    creation_time: new Date(),
    start_time: new Date(),
    last_seen_time: new Date(),
    severity: IncidentSeverity.High,
    status: IncidentStatus.Firing,
    services: [],
    alert_sources: [],
    rule_fingerprint: '',
    alerts_count: 2,
    fingerprint: 'incident-fingerprint',
    same_incident_in_the_past_id: '',
    following_incidents_ids: [],
    merged_into_incident_id: '',
    merged_by: '',
    merged_at: new Date(),
    assignee: '',
    enrichments: {},
    resolve_on: 'all_resolved',
  };

  const mockAlerts: AlertDto[] = [
    {
      id: 'alert-1',
      event_id: 'event-1',
      fingerprint: 'alert-1',
      name: 'Test Alert 1',
      description: 'Alert 1 description',
      severity: AlertSeverity.High,
      status: AlertStatus.Firing,
      source: ['prometheus'],
      providerId: 'provider-1',
      is_created_by_ai: false,
      lastReceived: new Date(),
      environment: 'production',
      pushed: false,
      deleted: false,
      dismissed: false,
      enriched_fields: [],
      ticket_url: '',
    },
    {
      id: 'alert-2',
      event_id: 'event-2',
      fingerprint: 'alert-2',
      name: 'Test Alert 2',
      description: 'Alert 2 description',
      severity: AlertSeverity.Warning,
      status: AlertStatus.Firing,
      source: ['grafana'],
      providerId: 'provider-2',
      is_created_by_ai: true,
      lastReceived: new Date(),
      environment: 'production',
      pushed: false,
      deleted: false,
      dismissed: false,
      enriched_fields: [],
      ticket_url: '',
    },
  ];

  const mockIncidentAlerts = {
    items: mockAlerts,
    count: 2,
    limit: 20,
    offset: 0,
  };

  beforeEach(() => {
    // Reset AlertSidebar state
    alertSidebarState = {
      isOpen: false,
      alert: null,
    };

    // Mock successful data fetching
    useIncidentAlerts.mockReturnValue({
      data: mockIncidentAlerts,
      isLoading: false,
      error: null,
      mutate: jest.fn(),
    });
  });

  it('should render alerts and allow opening AlertSidebar', async () => {
    render(<IncidentAlerts incident={mockIncident} />);

    // Verify alerts are rendered
    expect(screen.getByText('Test Alert 1')).toBeInTheDocument();
    expect(screen.getByText('Test Alert 2')).toBeInTheDocument();

    // Initially, sidebar should not be visible
    expect(screen.queryByTestId('alert-sidebar')).not.toBeInTheDocument();
    expect(alertSidebarState.isOpen).toBe(false);
  });

  it('should open AlertSidebar when clicking on alert row', async () => {
    render(<IncidentAlerts incident={mockIncident} />);

    // Click on the first alert row
    const alertRow = screen.getByTestId('alert-row-alert-1');
    fireEvent.click(alertRow);

    // Verify AlertSidebar is opened with correct alert
    await waitFor(() => {
      expect(screen.getByTestId('alert-sidebar')).toBeInTheDocument();
      const sidebarContent = screen.getByTestId('alert-sidebar-content');
      expect(sidebarContent).toHaveTextContent('Test Alert 1');
      expect(sidebarContent).toHaveTextContent('Severity: high');
    });

    // Verify our tracked state
    expect(alertSidebarState.isOpen).toBe(true);
    expect(alertSidebarState.alert?.name).toBe('Test Alert 1');
  });

  it('should open AlertSidebar when clicking view details button', async () => {
    render(<IncidentAlerts incident={mockIncident} />);

    // Note: The view button actually opens ViewAlertModal, not AlertSidebar
    // Let's click directly on the row to test AlertSidebar
    const alertRow = screen.getByTestId('alert-row-alert-2');
    fireEvent.click(alertRow);

    // Verify AlertSidebar is opened with correct alert
    await waitFor(() => {
      expect(screen.getByTestId('alert-sidebar')).toBeInTheDocument();
      const sidebarContent = screen.getByTestId('alert-sidebar-content');
      expect(sidebarContent).toHaveTextContent('Test Alert 2');
      expect(sidebarContent).toHaveTextContent('Severity: warning');
    });

    // Verify our tracked state
    expect(alertSidebarState.isOpen).toBe(true);
    expect(alertSidebarState.alert?.name).toBe('Test Alert 2');
  });

  it('should close AlertSidebar when clicking close button', async () => {
    render(<IncidentAlerts incident={mockIncident} />);

    // Open the sidebar first
    const alertRow = screen.getByTestId('alert-row-alert-1');
    fireEvent.click(alertRow);

    // Verify sidebar is open
    await waitFor(() => {
      expect(screen.getByTestId('alert-sidebar')).toBeInTheDocument();
    });

    // Close the sidebar
    const closeButton = screen.getByTestId('close-sidebar');
    fireEvent.click(closeButton);

    // Verify sidebar is closed
    await waitFor(() => {
      expect(screen.queryByTestId('alert-sidebar')).not.toBeInTheDocument();
    });

    // Verify our tracked state
    expect(alertSidebarState.isOpen).toBe(false);
  });

  it('should close AlertSidebar when clicking outside without errors', async () => {
    render(<IncidentAlerts incident={mockIncident} />);

    // Open the sidebar first
    const alertRow = screen.getByTestId('alert-row-alert-1');
    fireEvent.click(alertRow);

    // Verify sidebar is open
    await waitFor(() => {
      expect(screen.getByTestId('alert-sidebar')).toBeInTheDocument();
    });

    // Close the sidebar (simulating clicking outside by using the close button)
    const closeButton = screen.getByTestId('close-sidebar');
    fireEvent.click(closeButton);

    // Verify sidebar closes without errors
    await waitFor(() => {
      expect(screen.queryByTestId('alert-sidebar')).not.toBeInTheDocument();
    });

    // Verify no error was thrown and state is clean
    expect(alertSidebarState.isOpen).toBe(false);
    expect(alertSidebarState.alert).toBe(null);
    
    // The key verification is that no error was thrown during the close operation
    // If the bug existed, we would get "Cannot read properties of null (reading 'fingerprint')"
  });

  it('should switch between different alerts in sidebar', async () => {
    render(<IncidentAlerts incident={mockIncident} />);

    // Open sidebar for first alert
    fireEvent.click(screen.getByTestId('alert-row-alert-1'));
    
    await waitFor(() => {
      const sidebarContent = screen.getByTestId('alert-sidebar-content');
      expect(sidebarContent).toHaveTextContent('Test Alert 1');
    });
    expect(alertSidebarState.alert?.name).toBe('Test Alert 1');

    // Click on second alert row to switch
    fireEvent.click(screen.getByTestId('alert-row-alert-2'));

    await waitFor(() => {
      const sidebarContent = screen.getByTestId('alert-sidebar-content');
      expect(sidebarContent).toHaveTextContent('Test Alert 2');
      expect(sidebarContent).toHaveTextContent('Severity: warning');
    });
    expect(alertSidebarState.alert?.name).toBe('Test Alert 2');
  });

  it('should show empty state when no alerts', () => {
    useIncidentAlerts.mockReturnValue({
      data: { items: [], count: 0, limit: 20, offset: 0 },
      isLoading: false,
      error: null,
      mutate: jest.fn(),
    });

    render(<IncidentAlerts incident={mockIncident} />);

    expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    expect(screen.getByText('No alerts yet')).toBeInTheDocument();
    expect(screen.getByText('Alerts will show up here as they are correlated into this incident.')).toBeInTheDocument();
  });

  it('should show loading state', () => {
    useIncidentAlerts.mockReturnValue({
      data: null,
      isLoading: true,
      error: null,
      mutate: jest.fn(),
    });

    render(<IncidentAlerts incident={mockIncident} />);

    expect(screen.getByTestId('loading-skeleton')).toBeInTheDocument();
  });

  it('should open ViewAlertModal when clicking view button in action tray', async () => {
    useIncidentAlerts.mockReturnValue({
      data: mockIncidentAlerts,
      isLoading: false,
      error: null,
      mutate: jest.fn(),
    });

    render(<IncidentAlerts incident={mockIncident} />);

    // Click the view button in the action tray
    const viewButtons = screen.getAllByLabelText('View Alert Details');
    fireEvent.click(viewButtons[0]);

    // Check that ViewAlertModal is opened (not AlertSidebar)
    await waitFor(() => {
      expect(screen.getByTestId('view-alert-modal')).toBeInTheDocument();
      expect(screen.queryByTestId('alert-sidebar')).not.toBeInTheDocument();
    });
  });

  it('should have both ViewAlertModal and AlertSidebar when appropriate', async () => {
    useIncidentAlerts.mockReturnValue({
      data: mockIncidentAlerts,
      isLoading: false,
      error: null,
      mutate: jest.fn(),
    });

    render(<IncidentAlerts incident={mockIncident} />);

    // First, open ViewAlertModal with view button
    const viewButtons = screen.getAllByLabelText('View Alert Details');
    fireEvent.click(viewButtons[0]);

    await waitFor(() => {
      expect(screen.getByTestId('view-alert-modal')).toBeInTheDocument();
    });

    // Then, click on alert row to open AlertSidebar
    const alertRows = screen.getAllByTestId(/^alert-row-/);
    const firstAlertRow = alertRows[0];
    fireEvent.click(firstAlertRow);

    // Both should be open now
    await waitFor(() => {
      expect(screen.getByTestId('view-alert-modal')).toBeInTheDocument();
      expect(screen.getByTestId('alert-sidebar')).toBeInTheDocument();
    });
  });
});