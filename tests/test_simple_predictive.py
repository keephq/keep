# tests/test_simple_predictive.py
from keep.api.routes.predictive_engine import PredictiveEngine


def test_simple_integration():
    engine = PredictiveEngine(tenant_id="test")
    print("✅ PredictiveEngine imported successfully")

