# need to tests that:
# 1. On multiple tenants, the search mode is set to internal if elastic is disabled
# 2. On multiple tenants, the search mode is set to the tenant configuration
# 3. On single tenant, the search mode is set to elastic if elastic is enabled
# 4. On single tenant, the search mode is set to internal if elastic is disabled


"""
def test_search_mode_internal_on_multiple_tenants(mocker):
    tenant_configuration = TenantConfiguration()
    tenant_configuration.get_configuration = mocker.Mock(return_value=None)
    search_engine = SearchEngine("test-tenant")
    assert search_engine.search_mode == SearchMode.INTERNAL


def test_search_mode_tenant_configuration_on_multiple_tenants(mocker):
    tenant_configuration = TenantConfiguration()
    tenant_configuration.get_configuration = mocker.Mock(
        return_value=SearchMode.ELASTIC
    )
    search_engine = SearchEngine("test-tenant")
    assert search_engine.search_mode == SearchMode.ELASTIC
"""
