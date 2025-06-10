# Column Configuration Migration to Backend

## Overview

This document explains the new backend-based column configuration feature that allows users to create custom views with saved column settings that are shared across devices and sessions.

## What Changed

Previously, column configuration (visibility, order, rename mapping, time/list formats) was stored in browser local storage with keys like:
- `column-visibility-${presetName}`
- `column-order-${presetName}`
- `column-rename-mapping-${presetName}`
- `column-time-formats-${presetName}`
- `column-list-formats-${presetName}`

Now, these configurations can be stored in the backend as part of preset options, enabling:
- ✅ Sharing column configurations across different browsers/devices
- ✅ Team collaboration with shared column views
- ✅ Persistent column settings tied to specific presets
- ✅ Backward compatibility with existing local storage

## Backend Implementation

### Database Structure

Column configurations are stored in the preset's `options` JSON array with these labels:
- `column_visibility`: `Record<string, boolean>` - which columns are visible
- `column_order`: `string[]` - the order of columns
- `column_rename_mapping`: `Record<string, string>` - custom column names
- `column_time_formats`: `Record<string, string>` - time formatting options
- `column_list_formats`: `Record<string, string>` - list formatting options

### API Endpoints

#### Get Column Configuration
```
GET /preset/{preset_id}/column-config
```
Returns the column configuration for a specific preset.

#### Update Column Configuration
```
PUT /preset/{preset_id}/column-config
```
Updates the column configuration for a specific preset.

**Request Body:**
```json
{
  "column_visibility": {"name": true, "description": false},
  "column_order": ["severity", "status", "name"],
  "column_rename_mapping": {"lastReceived": "Last Seen"},
  "column_time_formats": {"lastReceived": "timeago"},
  "column_list_formats": {"tags": "badges"}
}
```

## Frontend Implementation

### New Hooks

#### `usePresetColumnConfig()`
Low-level hook for direct backend column configuration management.

```typescript
const { columnConfig, updateColumnConfig, isLoading } = usePresetColumnConfig({
  presetId: "preset-uuid"
});
```

#### `usePresetColumnState()`
High-level hook that provides a unified interface for both local storage and backend-based column configuration.

```typescript
const {
  columnVisibility,
  columnOrder,
  columnRenameMapping,
  columnTimeFormats,
  columnListFormats,
  setColumnVisibility,
  setColumnOrder,
  setColumnRenameMapping,
  setColumnTimeFormats,
  setColumnListFormats,
  isLoading,
  useBackend
} = usePresetColumnState({
  presetName: "my-preset",
  presetId: "preset-uuid", // Optional: enables backend usage
  useBackend: true // Optional: explicit backend usage flag
});
```

### Backward Compatibility

The system maintains full backward compatibility:

1. **No Preset ID**: Falls back to local storage (existing behavior)
2. **With Preset ID**: Uses backend configuration
3. **Hybrid Mode**: Backend takes precedence, falls back to local storage if backend config is empty

### Visual Indicators

When using backend-based configuration, users see a "Synced across devices" indicator in the column selection UI.

## Migration Strategy

### Phase 1: Opt-in Backend Usage (Current)
- Backend functionality is available when `presetId` is provided
- Existing local storage usage continues to work
- Users can gradually migrate their column configurations

### Phase 2: Gradual Migration (Future)
- Add migration utilities to move local storage configs to backend
- Provide user notifications about the new feature
- Maintain local storage as fallback

### Phase 3: Full Backend Migration (Future)
- Default to backend configuration for all presets
- Keep local storage only for non-preset views

## Usage Examples

### Updating a Component to Use Backend Config

**Before:**
```typescript
const [columnVisibility, setColumnVisibility] = useLocalStorage<VisibilityState>(
  `column-visibility-${presetName}`,
  DEFAULT_COLS_VISIBILITY
);
```

**After:**
```typescript
const { columnVisibility, setColumnVisibility } = usePresetColumnState({
  presetName,
  presetId, // When available
  useBackend: !!presetId
});
```

### Creating a Shared Column View

1. User configures columns in the UI
2. Configuration is automatically saved to the backend when `presetId` is available
3. Other users accessing the same preset see the same column configuration
4. Changes are immediately synced across all users

## Testing

To test the new functionality:

1. Create a preset with a specific ID
2. Configure columns (visibility, order, renaming, formats)
3. Access the same preset from another browser/device
4. Verify that column configuration is preserved
5. Test fallback to local storage when preset ID is not available

## Benefits

1. **Cross-device Synchronization**: Column preferences follow users across devices
2. **Team Collaboration**: Teams can share optimized column configurations
3. **Persistent Views**: Column settings are tied to specific presets and persist across sessions
4. **Improved UX**: Users don't lose their custom column configurations
5. **Backward Compatibility**: Existing local storage usage continues to work

## Future Enhancements

- User-specific overrides of shared column configurations
- Column configuration templates
- Import/export of column configurations
- Version history of column configuration changes