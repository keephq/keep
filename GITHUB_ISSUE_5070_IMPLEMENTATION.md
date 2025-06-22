# GitHub Issue #5070 Implementation Summary

## Issue: Support conditional namespace display in Teams Adaptive Cards when label may be missing

### Problem Description
When creating Teams Adaptive Cards for alert notifications, users encountered errors when trying to access alert properties that might not exist (like `namespace` in alert labels). Direct property access in templates would fail with "Could not find key" errors when the field was missing.

### Root Cause Analysis
The issue occurs during mustache template rendering in the IOHandler when:
1. Templates use direct property access (e.g., `{{ alert.labels.namespace }}`)
2. The referenced field doesn't exist in the alert data
3. The template rendering engine fails with a `RenderException` due to `safe=True` being used in `render_context()`

**Key Code Location**: `keep/iohandler/iohandler.py:488` - Regular strings are rendered with `safe=True`, causing failures when keys are missing.

### Solution Implemented

#### 1. Comprehensive Test Coverage
Added 3 new test functions to `tests/test_teams_provider.py`:

- **`test_github_issue_5070_mustache_template_rendering()`** - Demonstrates the actual issue with mustache template rendering in the IOHandler
- **`test_teams_adaptive_card_safe_rendering_patterns()`** - Tests Teams provider with safe rendering patterns 
- **`test_render_context_safe_parameter_handling()`** - Tests the render_context method's handling of safe parameters

#### 2. Safe Template Rendering Solutions
Documented and tested two approaches:

**Option A: `keep.dictget()` function** (Recommended)
```mustache
**📦 Namespace**: keep.dictget({{ alert.labels }}, 'namespace', 'N/A')
```

**Option B: Mustache conditionals**
```mustache
**📦 Namespace**: {{#alert.labels.namespace}}{{ alert.labels.namespace }}{{/alert.labels.namespace}}{{^alert.labels.namespace}}N/A{{/alert.labels.namespace}}
```

#### 3. Example Workflow
Created `examples/workflows/teams-adaptive-cards-safe-rendering.yaml` demonstrating:
- Safe rendering patterns for missing fields
- Multiple approaches (dictget vs conditionals)
- Real-world Teams Adaptive Card structure
- Best practices for handling optional alert fields

### Test Results
All tests pass successfully:
```
tests/test_teams_provider.py::test_github_issue_5070_mustache_template_rendering PASSED
tests/test_teams_provider.py::test_teams_adaptive_card_safe_rendering_patterns PASSED  
tests/test_teams_provider.py::test_render_context_safe_parameter_handling PASSED
```

### Key Findings

1. **Direct Property Access Issue**: Using `{{ alert.labels.namespace }}` fails with `RenderException` when the field is missing due to `safe=True` in the IOHandler.

2. **`keep.dictget()` Solution**: The `keep.dictget()` function provides safe access with default values and works with `safe=True` rendering.

3. **Mustache Conditionals**: Work but require `safe=False` rendering, making them less ideal for some use cases.

4. **Template Rendering Flow**: The issue occurs in `IOHandler.render_context()` → `_render_template_with_context()` → `_render()` where `safe=True` causes failures.

### Recommendations

1. **Use `keep.dictget()` for optional fields**:
   ```mustache
   keep.dictget({{ alert.labels }}, 'namespace', 'default_value')
   ```

2. **Use mustache conditionals for complex logic**:
   ```mustache
   {{#alert.labels.namespace}}{{ alert.labels.namespace }}{{/alert.labels.namespace}}{{^alert.labels.namespace}}N/A{{/alert.labels.namespace}}
   ```

3. **Avoid direct property access** for optional fields in templates.

### Files Modified

1. **`tests/test_teams_provider.py`** - Added comprehensive test coverage
2. **`examples/workflows/teams-adaptive-cards-safe-rendering.yaml`** - Added example workflow

### Backward Compatibility
- All existing functionality remains unchanged
- New tests validate existing behavior
- Example workflows provide migration guidance
- No breaking changes introduced

### Impact
This implementation resolves GitHub issue #5070 by:
- ✅ Providing clear solutions for handling missing namespace fields
- ✅ Adding comprehensive test coverage for the issue
- ✅ Documenting safe rendering patterns
- ✅ Creating example workflows for users
- ✅ Maintaining backward compatibility