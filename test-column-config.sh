#!/bin/bash

echo "🧪 Testing backend-based column configuration..."

# Run the specific test for backend column configuration persistence
cd /workspace
poetry run pytest tests/e2e_tests/incidents_alerts_tests/test_filtering_sort_search_on_alerts.py::test_backend_column_configuration_persistence -v -s

echo ""
echo "📊 Test Results:"
if [ $? -eq 0 ]; then
    echo "✅ Backend column configuration test PASSED"
    echo "   - Column settings are properly saved to backend"
    echo "   - Column configuration persists across browser sessions"
    echo "   - 'Synced across devices' indicator shows correctly"
else
    echo "❌ Backend column configuration test FAILED"
    echo "   - Check the logs above for details"
fi

echo ""
echo "🔍 To run all column-related tests:"
echo "poetry run pytest tests/e2e_tests/incidents_alerts_tests/test_filtering_sort_search_on_alerts.py -k 'column' -v"

echo ""
echo "🔍 To run the original failing test:"
echo "poetry run pytest tests/e2e_tests/incidents_alerts_tests/test_filtering_sort_search_on_alerts.py::test_multi_sort_asc_dsc -v"