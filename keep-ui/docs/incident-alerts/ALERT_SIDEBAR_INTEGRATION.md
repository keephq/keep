# Alert Sidebar Integration for Incident Alerts

## Overview
This document describes the integration of AlertSidebar and ViewAlertModal components in the incident alerts view. The implementation provides two ways to view alert details:

1. **ViewAlertModal** - Opened by clicking the view button in the action tray
2. **AlertSidebar** - Opened by clicking on the alert row

## Implementation Details

### Components Used
1. **ViewAlertModal** (`@/features/alerts/view-raw-alert`) - The modal component for viewing raw alert JSON
2. **AlertSidebar** (`@/features/alerts/alert-detail-sidebar`) - The sidebar component showing detailed alert information

### Key Changes

#### State Management
```typescript
// State for ViewAlertModal (opened by view button)
const [viewAlertModal, setViewAlertModal] = useState<AlertDto | null>(null);

// State for AlertSidebar (opened by row click)
const [selectedAlert, setSelectedAlert] = useState<AlertDto | null>(null);
const [isSidebarOpen, setIsSidebarOpen] = useState(false);
```

#### User Interactions
1. **View Button Click** - Opens ViewAlertModal with raw alert JSON
   - Located in the action tray for each alert
   - Provides JSON editing capabilities
   - Allows enrichment/un-enrichment of fields

2. **Row Click** - Opens AlertSidebar with alert details
   - Shows alert timeline, related services, and incidents
   - Provides a consistent experience with the main alerts table
   - Cannot edit alert data

### Benefits
1. **Dual Viewing Options** - Users can choose between viewing raw JSON (modal) or formatted details (sidebar)
2. **Consistency** - AlertSidebar provides the same viewing experience as in the main alerts table
3. **Feature Completeness** - Both viewing methods are available without removing existing functionality

## Testing

The implementation includes comprehensive tests for both components:

### Test Coverage
- Alert rendering and display
- ViewAlertModal opening via view button
- AlertSidebar opening via row click
- Closing both components
- Having both components open simultaneously
- Empty state handling
- Loading state handling

### Running Tests
```bash
cd keep-ui
npm test -- --testPathPattern="incident-alerts-sidebar"
```

## Component Features

### ViewAlertModal Features
- Raw JSON view of alert data
- Syntax highlighting
- Edit mode for modifying alert fields
- Enrichment/un-enrichment capabilities
- Copy to clipboard functionality

### AlertSidebar Features
- Alert name and severity display
- Alert description
- Source information
- Fingerprint details
- Related incidents
- Alert timeline
- Related services topology view

## Usage Example

```typescript
// In incident-alerts.tsx
<>
  {/* ViewAlertModal - opened by the view button in the action tray */}
  <ViewAlertModal
    alert={viewAlertModal}
    handleClose={() => setViewAlertModal(null)}
    mutate={() => mutateAlerts()}
  />

  {/* AlertSidebar - opened by clicking on the alert row */}
  <AlertSidebar
    isOpen={isSidebarOpen}
    toggle={handleSidebarClose}
    alert={selectedAlert}
    setIsIncidentSelectorOpen={setIsIncidentSelectorOpen}
  />
</>
```