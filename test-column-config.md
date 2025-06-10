# Column Configuration Test Guide

This guide helps verify that the new backend-based column configuration works correctly while maintaining backward compatibility.

## Test Cases

### 1. Static Preset (Feed) - Should Use Local Storage
```bash
# Navigate to: http://localhost:3000/alerts/feed
# Expected behavior: Uses local storage, no "Synced across devices" indicator
```

**Steps:**
1. Go to `/alerts/feed`
2. Click Settings (gear icon) → Columns tab
3. **Verify**: No "Synced across devices" badge shown
4. Enable some columns (e.g., search for "tags" and enable tag columns)
5. Click "Save changes"
6. Refresh page → columns should persist (from local storage)
7. Open in incognito/another browser → columns should NOT be shared

### 2. Dynamic Preset - Should Use Backend
```bash
# Navigate to: http://localhost:3000/alerts/[dynamic-preset-name]
# Where [dynamic-preset-name] is a user-created preset
# Expected behavior: Uses backend, shows "Synced across devices" indicator
```

**Steps:**
1. Create a new preset or use existing dynamic preset
2. Go to `/alerts/[preset-name]`  
3. Click Settings → Columns tab
4. **Verify**: "Synced across devices" badge is shown
5. Configure columns
6. Click "Save changes"
7. Open in another browser/device → columns should be shared

### 3. E2E Test Fix Verification
```bash
# Run the specific failing test
cd /workspace
poetry run pytest tests/e2e_tests/incidents_alerts_tests/test_filtering_sort_search_on_alerts.py::test_multi_sort_asc_dsc -v
```

**Expected result:** Test should pass because:
- Feed preset uses local storage (as before)
- Column selection works synchronously
- `tags.customerName` column appears in table header after enabling

## API Testing

### Test Backend Endpoints (for dynamic presets only)
```bash
# Get column config
curl -X GET "http://localhost:8080/preset/{preset-id}/column-config" \
     -H "Authorization: Bearer {token}"

# Update column config  
curl -X PUT "http://localhost:8080/preset/{preset-id}/column-config" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer {token}" \
     -d '{
       "column_visibility": {"name": true, "tags.customerName": true},
       "column_order": ["severity", "status", "name", "tags.customerName"]
     }'
```

## Troubleshooting

### If E2E test still fails:
1. Check that static preset IDs are correct
2. Verify local storage fallback is working
3. Ensure column visibility updates are synchronous for local storage

### If backend config doesn't work:
1. Check preset has valid (non-static) ID
2. Verify API endpoints are accessible
3. Check network requests in browser devtools