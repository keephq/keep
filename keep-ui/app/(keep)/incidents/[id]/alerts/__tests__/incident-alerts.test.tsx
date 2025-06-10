import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { useRouter } from 'next/navigation';
import IncidentAlerts from '../incident-alerts';
import type { 
  IncidentDto, 
} from '@/entities/incidents/model';
import { 
  Status as IncidentStatus,
  Severity as IncidentSeverity 
} from '@/entities/incidents/model/models';
import type { 
  AlertDto, 
} from '@/entities/alerts/model/types';
import { 
  Status as AlertStatus, 
  Severity as AlertSeverity 
} from '@/entities/alerts/model/types';
import { useIncidentAlerts, usePollIncidentAlerts } from '@/utils/hooks/useIncidents';
import { useIncidentActions } from '@/entities/incidents/model';
import { useProviders } from '@/utils/hooks/useProviders';
import { useConfig } from '@/utils/hooks/useConfig';

// Mock the dependencies
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

jest.mock('@/utils/hooks/useIncidents', () => ({
  useIncidentAlerts: jest.fn(),
  usePollIncidentAlerts: jest.fn(),
}));

jest.mock('@/entities/incidents/model', () => ({
  ...jest.requireActual('@/entities/incidents/model'),
  useIncidentActions: jest.fn(),
}));

jest.mock('@/utils/hooks/useProviders', () => ({
  useProviders: jest.fn(),
}));

jest.mock('@/utils/hooks/useConfig', () => ({
  useConfig: jest.fn(),
}));

// Mock the alerts model module with all required exports
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
  Status: {
    Firing: 'firing',
    Resolved: 'resolved',
    Acknowledged: 'acknowledged',
    Suppressed: 'suppressed',
    Pending: 'pending',
  },
  Severity: {
    Critical: 'critical',
    High: 'high',
    Warning: 'warning',
    Low: 'low',
    Info: 'info',
    Error: 'error',
  },
}));

// Mock the AlertSidebar component to verify it's called with correct props
jest.mock('@/features/alerts/alert-detail-sidebar', () => ({
  AlertSidebar: ({ isOpen, toggle, alert }: any) => {
    if (!isOpen) return null;
    return (
      <div data-testid="alert-sidebar">
        <div data-testid="alert-sidebar-content">
          {alert?.name || 'Alert Details'}
        </div>
        <button onClick={toggle} data-testid="close-sidebar">
          Close
        </button>
      </div>
    );
  },
}));

// Mock alert table utilities
jest.mock('@/widgets/alerts-table/lib/alert-table-utils', () => ({
  useAlertTableCols: jest.fn(() => [
    { id: 'severity', header: 'Severity', cell: () => null },
    { id: 'checkbox', header: '', cell: () => null },
    { id: 'status', header: 'Status', cell: () => null },
    { id: 'source', header: 'Source', cell: () => null },
    { id: 'name', header: 'Name', cell: () => null },
    { id: 'description', header: 'Description', cell: () => null },
    { id: 'is_created_by_ai', header: 'Correlation', cell: () => null },
    { id: 'alertMenu', header: '', cell: () => null },
  ]),
}));

// Mock AlertsTableBody
jest.mock('@/widgets/alerts-table/ui/alerts-table-body', () => ({
  AlertsTableBody: ({ onRowClick, table }: any) => {
    return (
      <tbody>
        {table.getRowModel().rows.map((row: any) => (
          <tr key={row.id} onClick={() => onRowClick(row.original)}>
            <td>{row.original.name}</td>
          </tr>
        ))}
      </tbody>
    );
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

describe('IncidentAlerts', () => {
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

  const mockAlertsResponse = {
    items: mockAlerts,
    count: 2,
    limit: 20,
    offset: 0,
  };

  beforeEach(() => {
    // Reset all mocks before each test
    jest.clearAllMocks();

    // Setup default mock returns
    (useRouter as jest.Mock).mockReturnValue({
      push: jest.fn(),
    });

    (useIncidentAlerts as jest.Mock).mockReturnValue({
      data: mockAlertsResponse,
      isLoading: false,
      error: null,
      mutate: jest.fn(),
    });

    (usePollIncidentAlerts as jest.Mock).mockReturnValue(undefined);

    (useIncidentActions as jest.Mock).mockReturnValue({
      unlinkAlertsFromIncident: jest.fn(),
    });

    (useProviders as jest.Mock).mockReturnValue({
      data: {
        installed_providers: [
          { id: 'provider-1', display_name: 'Prometheus' },
          { id: 'provider-2', display_name: 'Grafana' },
        ],
      },
    });

    (useConfig as jest.Mock).mockReturnValue({
      data: { KEEP_DOCS_URL: 'https://docs.keephq.dev' },
    });
  });

  it('renders incident alerts table', () => {
    render(<IncidentAlerts incident={mockIncident} />);

    // Check if alerts are rendered
    expect(screen.getByText('Test Alert 1')).toBeInTheDocument();
    expect(screen.getByText('Test Alert 2')).toBeInTheDocument();
  });

  it('opens AlertSidebar when clicking view alert button', async () => {
    render(<IncidentAlerts incident={mockIncident} />);

    // Find and click the view alert button for the first alert
    const viewButtons = screen.getAllByLabelText('View Alert Details');
    fireEvent.click(viewButtons[0]);

    // Check if AlertSidebar is opened with correct alert
    await waitFor(() => {
      expect(screen.getByTestId('alert-sidebar')).toBeInTheDocument();
      expect(screen.getByTestId('alert-sidebar-content')).toHaveTextContent('Test Alert 1');
    });
  });

  it('opens AlertSidebar when clicking on alert row', async () => {
    render(<IncidentAlerts incident={mockIncident} />);

    // Click on the first alert row
    const alertRow = screen.getByText('Test Alert 1').closest('tr');
    if (alertRow) {
      fireEvent.click(alertRow);
    }

    // Check if AlertSidebar is opened
    await waitFor(() => {
      expect(screen.getByTestId('alert-sidebar')).toBeInTheDocument();
      expect(screen.getByTestId('alert-sidebar-content')).toHaveTextContent('Test Alert 1');
    });
  });

  it('closes AlertSidebar when clicking close button', async () => {
    render(<IncidentAlerts incident={mockIncident} />);

    // Open the sidebar
    const viewButtons = screen.getAllByLabelText('View Alert Details');
    fireEvent.click(viewButtons[0]);

    // Verify sidebar is open
    await waitFor(() => {
      expect(screen.getByTestId('alert-sidebar')).toBeInTheDocument();
    });

    // Close the sidebar
    fireEvent.click(screen.getByTestId('close-sidebar'));

    // Verify sidebar is closed
    await waitFor(() => {
      expect(screen.queryByTestId('alert-sidebar')).not.toBeInTheDocument();
    });
  });

  it('displays correlation information correctly', () => {
    render(<IncidentAlerts incident={mockIncident} />);

    // Check AI correlation
    expect(screen.getByTitle('Correlated with AI')).toBeInTheDocument();
    
    // Check manual correlation
    expect(screen.getByTitle('Correlated manually')).toBeInTheDocument();
  });

  it('displays topology correlation for topology incidents', () => {
    const topologyIncident = {
      ...mockIncident,
      incident_type: 'topology',
    };

    render(<IncidentAlerts incident={topologyIncident} />);

    // Check topology correlation
    const topologyElements = screen.getAllByTitle('Correlated with topology');
    expect(topologyElements).toHaveLength(2); // Both alerts should show topology
  });

  it('handles unlink alert action for non-candidate incidents', async () => {
    const mockUnlink = jest.fn();
    (useIncidentActions as jest.Mock).mockReturnValue({
      unlinkAlertsFromIncident: mockUnlink,
    });

    render(<IncidentAlerts incident={mockIncident} />);

    // Find and click the unlink button
    const unlinkButtons = screen.getAllByLabelText('Unlink from incident');
    fireEvent.click(unlinkButtons[0]);

    // Verify unlink function was called
    await waitFor(() => {
      expect(mockUnlink).toHaveBeenCalledWith(
        'incident-123',
        ['alert-1'],
        expect.any(Function)
      );
    });
  });

  it('does not show unlink button for candidate incidents', () => {
    const candidateIncident = {
      ...mockIncident,
      is_candidate: true,
    };

    render(<IncidentAlerts incident={candidateIncident} />);

    // Verify unlink buttons are not present
    expect(screen.queryByLabelText('Unlink from incident')).not.toBeInTheDocument();
  });

  it('handles empty alerts state', () => {
    (useIncidentAlerts as jest.Mock).mockReturnValue({
      data: { items: [], count: 0, limit: 20, offset: 0 },
      isLoading: false,
      error: null,
      mutate: jest.fn(),
    });

    render(<IncidentAlerts incident={mockIncident} />);

    // Check for empty state
    expect(screen.getByText('No alerts yet')).toBeInTheDocument();
    expect(screen.getByText('Alerts will show up here as they are correlated into this incident.')).toBeInTheDocument();
    
    // Check for action buttons in empty state
    expect(screen.getByText('Add Alerts Manually')).toBeInTheDocument();
    expect(screen.getByText('Try AI Correlation')).toBeInTheDocument();
  });

  it('handles loading state', () => {
    (useIncidentAlerts as jest.Mock).mockReturnValue({
      data: null,
      isLoading: true,
      error: null,
      mutate: jest.fn(),
    });

    render(<IncidentAlerts incident={mockIncident} />);

    // Should show skeleton loader
    expect(screen.getByRole('table')).toBeInTheDocument();
  });

  it('handles pagination correctly', async () => {
    const largeMockAlertsResponse = {
      items: mockAlerts,
      count: 50,
      limit: 20,
      offset: 0,
    };

    (useIncidentAlerts as jest.Mock).mockReturnValue({
      data: largeMockAlertsResponse,
      isLoading: false,
      error: null,
      mutate: jest.fn(),
    });

    render(<IncidentAlerts incident={mockIncident} />);

    // Verify pagination is shown when there are more items than page size
    expect(screen.getByRole('navigation')).toBeInTheDocument();
  });

  it('switches between different alerts in sidebar', async () => {
    render(<IncidentAlerts incident={mockIncident} />);

    // Open sidebar for first alert
    const viewButtons = screen.getAllByLabelText('View Alert Details');
    fireEvent.click(viewButtons[0]);

    await waitFor(() => {
      expect(screen.getByTestId('alert-sidebar-content')).toHaveTextContent('Test Alert 1');
    });

    // Close sidebar
    fireEvent.click(screen.getByTestId('close-sidebar'));

    await waitFor(() => {
      expect(screen.queryByTestId('alert-sidebar')).not.toBeInTheDocument();
    });

    // Open sidebar for second alert
    fireEvent.click(viewButtons[1]);

    await waitFor(() => {
      expect(screen.getByTestId('alert-sidebar-content')).toHaveTextContent('Test Alert 2');
    });
  });
});