# Column Configuration Fixes

## Issues Fixed

### Bug 1: E2E Test Failure - Checkbox State Not Reflecting Updates
**Problem**: The test `test_backend_column_configuration_persistence` was failing with timeout when checking if `tags.customerName` column checkbox was checked after adding the column.

**Root Cause**: In `ColumnSelection.tsx`, checkboxes used `defaultChecked={columnVisibility[column]}` which only sets initial state. When column visibility state changed (like when columns were added via backend), the checkboxes didn't update because `defaultChecked` is only applied once on initial render.

**Fix**: Changed from `defaultChecked` to `checked` to ensure checkboxes reflect current state:
```typescript
// Before
<input
  name={column}
  type="checkbox"
  defaultChecked={columnVisibility[column]}
/>

// After  
<input
  name={column}
  type="checkbox"
  checked={columnVisibility[column] || false}
/>
```

### Bug 2: Columns Disappearing When Moved Left
**Problem**: When users moved columns left (or performed any reordering), added columns would disappear.

**Root Cause**: Column movement operations (`moveColumn`, drag & drop) only updated local state via direct setters like `setColumnOrder(newOrder)`. For dynamic presets using backend storage, this created a state synchronization issue where:
1. Column movement updated only local state
2. Backend state wasn't updated
3. On next render, backend state would overwrite local changes
4. Columns would disappear

**Fix**: Implemented unified column update functions that handle both local and backend updates:

1. **Added unified update functions in `AlertTableServerSide`**:
```typescript
const handleColumnOrderChange = async (newOrder: ColumnOrderState) => {
  if (!!presetId) {
    // For backend presets, use the batched update
    await updateMultipleColumnConfigs({ columnOrder: newOrder });
  } else {
    // For local presets, use direct setter
    setColumnOrder(newOrder);
  }
};

const handleColumnVisibilityChange = async (newVisibility: VisibilityState) => {
  if (!!presetId) {
    // For backend presets, use the batched update
    await updateMultipleColumnConfigs({ columnVisibility: newVisibility });
  } else {
    // For local presets, use direct setter
    setColumnVisibility(newVisibility);
  }
};
```

2. **Updated headers component to handle async operations**:
```typescript
// Updated function signatures to support async
setColumnOrder: (order: ColumnOrderState) => Promise<void> | void;
setColumnVisibility: (visibility: VisibilityState) => Promise<void> | void;

// Updated moveColumn function
const moveColumn = async (direction: "left" | "right") => {
  // ... column reordering logic ...
  try {
    await setColumnOrder(newOrder);
  } catch (error) {
    console.error("Failed to update column order:", error);
  }
};

// Updated drag & drop handler
const onDragEnd = async (event: DragEndEvent) => {
  // ... drag logic ...
  try {
    await setColumnOrder(reorderedCols);
  } catch (error) {
    console.error("Failed to update column order via drag and drop:", error);
  }
};
```

3. **Maintained backward compatibility for deprecated component**:
```typescript
// In AlertTable.tsx (deprecated), kept synchronous wrappers
const handleColumnOrderChange = (newOrder: ColumnOrderState) => {
  setColumnOrder(newOrder);
};
```

## Files Modified

- `keep-ui/widgets/alerts-table/ui/ColumnSelection.tsx`: Fixed checkbox state synchronization
- `keep-ui/widgets/alerts-table/ui/alert-table-server-side.tsx`: Added unified column update functions
- `keep-ui/widgets/alerts-table/ui/alert-table-headers.tsx`: Updated to handle async column operations
- `keep-ui/widgets/alerts-table/ui/alert-table.tsx`: Maintained backward compatibility

## Expected Behavior After Fix

### For Static Presets (feed):
- Continue using local storage (no change in behavior)
- Synchronous operations maintained

### For Dynamic Presets:
1. **Column Addition**: 
   - User adds column → Saves to backend → Checkbox immediately reflects current state ✅
   - Test `tags.customerName` checkbox is properly checked ✅

2. **Column Movement**:
   - User moves column left/right → Saves to backend → Column stays visible ✅
   - Drag & drop reordering → Saves to backend → Order persists ✅

3. **Cross-Device Sync**:
   - Column configuration changes sync across devices ✅
   - "Synced across devices" indicator shows when using backend ✅

## Performance Benefits

- **Single API Call**: Batched updates prevent multiple API calls and toast messages
- **Error Handling**: Proper error handling for failed backend updates
- **State Consistency**: Unified approach ensures local and backend state stay synchronized

## Testing

- TypeScript compilation passes ✅
- No breaking changes to existing functionality ✅
- Backward compatibility maintained for deprecated components ✅

## Summary

Both bugs were related to state synchronization issues between UI components and the underlying data storage (local vs backend). The fixes ensure that:

1. UI components properly reflect the current state (checkboxes)
2. All column operations (add, remove, reorder) are consistently saved to the appropriate storage
3. Backend and local state remain synchronized
4. No data loss during column operations

The solution maintains the existing architecture while ensuring robust state management across different preset types.