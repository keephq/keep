import os
import pytest
import random
import numpy as np

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from keep.api.models.db.alert import Alert
from keep.api.models.db.tenant import Tenant
from ee.experimental.incident_utils import mine_incidents_and_create_objects, calculate_pmi_matrix, DEFAULT_TEMP_DIR_LOCATION

random.seed(42)

@pytest.mark.asyncio
async def test_mine_incidents_and_create_objects(db_session, tenant_id='test', n_alerts=10000, n_fingerprints=50):
    # Add alerts
    current_time = datetime.now()
    time_lags = [int(round(random.normalvariate(mu=60*24*30/2, sigma=60*24*30/6))) for _ in range(n_alerts)]
    alerts = [
        Alert(
            tenant_id=tenant_id,
            provider_type="test",
            provider_id="test",
            event={
                "id": f"test-{i}",
                "name": f"Test Alert {i}",
                "fingerprint": f"fp-{i % n_fingerprints}",
                "lastReceived": (current_time - timedelta(minutes=time_lags[i])).isoformat(),
                "severity": "critical",
                "source": ["test-source"],
            },
            fingerprint=f"fp-{i % n_fingerprints}",
            timestamp=current_time - timedelta(minutes=time_lags[i])
        )
        for i in range(n_alerts)
    ]
    db_session.add_all(alerts)
    db_session.commit()
    
    # add Tenant
    tenant = Tenant(
        id=tenant_id,
        name=tenant_id,
        configuration={
            "ee_enabled": True,
        }
    )
    db_session.add(tenant)
    db_session.commit()

    # Mock dependencies and call the function
    with patch('ee.experimental.incident_utils.get_pusher_client') as mock_pusher, \
         patch('ee.experimental.incident_utils.get_pool') as mock_get_pool:
        
        mock_pusher.return_value = MagicMock()
        mock_pool = AsyncMock()
        mock_get_pool.return_value = mock_pool

        result = await mine_incidents_and_create_objects(None, tenant_id)
        
    assert result is not None
    assert mock_pusher.called
    assert mock_get_pool.called
    
def test_calculate_pmi_matrix(db_session, tenant_id='test', n_alerts=10000, n_fingerprints=50):
    # Add Alerts
    current_time = datetime.now()
    time_lags = [int(round(random.normalvariate(mu=60*24*30/2, sigma=60*24*30/6))) for _ in range(n_alerts)]
    alerts = [
        Alert(
            tenant_id=tenant_id,
            provider_type="test",
            provider_id="test",
            event={
                "id": f"test-{i}",
                "name": f"Test Alert {i}",
                "fingerprint": f"fp-{i % n_fingerprints}",
                "lastReceived": (current_time - timedelta(minutes=time_lags[i])).isoformat(),
                "severity": "critical",
                "source": ["test-source"],
            },
            fingerprint=f"fp-{i % n_fingerprints}",
            timestamp=current_time - timedelta(minutes=time_lags[i])
        )
        for i in range(n_alerts)
    ]
    db_session.add_all(alerts)
    db_session.commit()
    
    # add Tenant
    tenant = Tenant(
        id=tenant_id,
        name=tenant_id,
        configuration={
            "ee_enabled": True,
        }
    )
    db_session.add(tenant)
    db_session.commit()
    
    # Call the function
    result = calculate_pmi_matrix(None, tenant_id)
    
    assert result == {"status": "success"}
    temp_dir = os.environ.get("AI_TEMP_FOLDER", DEFAULT_TEMP_DIR_LOCATION)
    assert os.path.exists(f"{temp_dir}/{tenant_id}/pmi_matrix.npz")
    pmi_matrix = np.load(f"{temp_dir}/{tenant_id}/pmi_matrix.npz", allow_pickle=True)
    assert (np.unique(pmi_matrix["fingerprints"]) == np.unique([f"fp-{i % n_fingerprints}" for i in range(n_fingerprints)])).all()
    assert pmi_matrix["pmi_matrix"].shape == (n_fingerprints, n_fingerprints)
    

@pytest.mark.asyncio
async def test_mine_incidents_and_create_objects_with_no_alerts(db_session, tenant_id='test'):
    # add Tenant
    tenant = Tenant(
        id=tenant_id,
        name=tenant_id,
        configuration={
            "ee_enabled": True,
        }
    )
    
    with patch('ee.experimental.incident_utils.get_pusher_client') as mock_pusher, \
         patch('ee.experimental.incident_utils.get_pool') as mock_get_pool:
        
        mock_pusher.return_value = MagicMock()
        mock_pool = AsyncMock()
        mock_get_pool.return_value = mock_pool

        result = await mine_incidents_and_create_objects(None, tenant_id)
        
    assert result=={"incidents": []}
        
    
