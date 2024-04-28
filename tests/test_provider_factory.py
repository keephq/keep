import inspect
from typing import Optional, Union

from keep.providers.providers_factory import ProvidersFactory


class TestProviderFactoryMethodParam:
    def test_get_method_param_type_simple(self):
        param = inspect.Parameter(
            "test", inspect.Parameter.POSITIONAL_ONLY, annotation=str
        )
        assert ProvidersFactory._get_method_param_type(param) == "str"

    def test_get_method_param_type_union(self):
        param = inspect.Parameter(
            "test", inspect.Parameter.POSITIONAL_ONLY, annotation=Union[str, int]
        )
        assert ProvidersFactory._get_method_param_type(param) == "str"

    def test_get_method_param_type_union_with_pipe(self):
        param = inspect.Parameter(
            "test", inspect.Parameter.POSITIONAL_ONLY, annotation=int | str
        )
        assert ProvidersFactory._get_method_param_type(param) == "int"

    def test_get_method_param_type_optional(self):
        param = inspect.Parameter(
            "test", inspect.Parameter.POSITIONAL_ONLY, annotation=Optional[str]
        )
        assert ProvidersFactory._get_method_param_type(param) == "str"

    def test_get_method_param_type_optional_with_union(self):
        param = inspect.Parameter(
            "test", inspect.Parameter.POSITIONAL_ONLY, annotation=Union[None, int]
        )
        assert ProvidersFactory._get_method_param_type(param) == "int"

    def test_get_method_param_type_without_annotation(self):
        param = inspect.Parameter("test", inspect.Parameter.POSITIONAL_ONLY)
        assert ProvidersFactory._get_method_param_type(param) == "str"
