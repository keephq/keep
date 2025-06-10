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
  useAlertTableTheme: jest.fn(() => ({ theme: 'default' })),
  useAlerts: jest.fn(() => ({
    useAlertAudit: jest.fn(() => ({
      data: [],
      isLoading: false,
      mutate: jest.fn(),
    })),
  })),
  useAlertRowStyle: jest.fn(() => ['default', jest.fn()]),
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
  useAlertTableCols: jest.fn(() => [
    { id: 'name', header: 'Name', cell: ({ row }: any) => row.original.name },
    { id: 'severity', header: 'Severity', cell: ({ row }: any) => row.original.severity },
  ]),
}));

// Mock the actual component that renders alerts with action buttons
jest.mock('@/widgets/alerts-table/ui/alerts-table-body', () => ({
  AlertsTableBody: ({ table, onRowClick }: any) => (
    <tbody data-testid="alerts-table-body">
      {table.getRowModel().rows.map((row: any) => (
        <tr key={row.id} onClick={() => onRowClick(row.original)} data-testid={`alert-row-${row.id}`}>
          <td>{row.original.name}</td>
          <td>
            <button
              data-testid={`view-alert-${row.id}`}
              onClick={(e) => {
                e.stopPropagation();
                onRowClick(row.original);
              }}
            >
              View Details
            </button>
          </td>
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

  beforeEach(() => {
    // Reset AlertSidebar state
    alertSidebarState = {
      isOpen: false,
      alert: null,
    };

    // Mock successful data fetching
    useIncidentAlerts.mockReturnValue({
      data: {
        items: mockAlerts,
        count: 2,
        limit: 20,
        offset: 0,
      },
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

    // Click the view details button for the second alert
    const viewButton = screen.getByTestId('view-alert-alert-2');
    fireEvent.click(viewButton);

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

  it('should switch between different alerts in sidebar', async () => {
    render(<IncidentAlerts incident={mockIncident} />);

    // Open sidebar for first alert
    fireEvent.click(screen.getByTestId('alert-row-alert-1'));
    
    await waitFor(() => {
      const sidebarContent = screen.getByTestId('alert-sidebar-content');
      expect(sidebarContent).toHaveTextContent('Test Alert 1');
    });
    expect(alertSidebarState.alert?.name).toBe('Test Alert 1');

    // Click on second alert to switch
    fireEvent.click(screen.getByTestId('view-alert-alert-2'));

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
});