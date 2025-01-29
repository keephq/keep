import copy
import json
import logging
import os
import re
import typing

from keep.actions.actions_factory import ActionsCRUD
from keep.api.core.config import config
from keep.api.core.db import get_installed_providers, get_workflow_id
from keep.contextmanager.contextmanager import ContextManager
from keep.functions import cyaml
from keep.providers.providers_factory import ProvidersFactory
from keep.step.step import Step, StepType
from keep.step.step_provider_parameter import StepProviderParameter
from keep.workflowmanager.workflow import Workflow, WorkflowStrategy


class Parser:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._loaded_providers_cache = {}
        self._use_loaded_provider_cache = config(
            "KEEP_USE_PROVIDER_CACHE", default=False
        )

    def _get_workflow_id(self, tenant_id, workflow: dict) -> str:
        """Support both CLI and API workflows

        Args:
            workflow (dict): _description_

        Raises:
            ValueError: _description_

        Returns:
            str: _description_
        """
        # for backward compatibility reasons, the id on the YAML is actually the name
        # and the id is a unique generated id stored in the db
        workflow_name = workflow.get("id")
        if workflow_name is None:
            raise ValueError("Workflow dict must have an id")

        # get the workflow id from the database
        workflow_id = get_workflow_id(tenant_id, workflow_name)
        # if the workflow id is not found, it means that the workflow is not stored in the db
        # for example when running from CLI
        # so for backward compatibility, we will use the workflow name as the id
        # todo - refactor CLI to use db also
        if not workflow_id:
            workflow_id = workflow_name
        return workflow_id

    def parse(
        self,
        tenant_id,
        parsed_workflow_yaml: dict,
        providers_file: str = None,
        actions_file: str = None,
    ) -> typing.List[Workflow]:
        """_summary_

        Args:
            parsed_workflow_yaml (str): could be a url or a file path
            providers_file (str, optional): _description_. Defaults to None.

        Returns:
            typing.List[Workflow]: _description_
        """
        # Parse the workflow itself (the alerts here is backward compatibility)
        workflow_providers = parsed_workflow_yaml.get("providers")
        workflow_actions = parsed_workflow_yaml.get("actions")
        if parsed_workflow_yaml.get("workflows") or parsed_workflow_yaml.get("alerts"):
            raw_workflows = parsed_workflow_yaml.get(
                "workflows"
            ) or parsed_workflow_yaml.get("alerts")
            workflows = [
                self._parse_workflow(
                    tenant_id,
                    workflow,
                    providers_file,
                    workflow_providers,
                    actions_file,
                    workflow_actions,
                )
                for workflow in raw_workflows
            ]
        # the alert here is backward compatibility
        elif parsed_workflow_yaml.get("workflow") or parsed_workflow_yaml.get("alert"):
            raw_workflow = parsed_workflow_yaml.get(
                "workflow"
            ) or parsed_workflow_yaml.get("alert")
            workflow = self._parse_workflow(
                tenant_id,
                raw_workflow,
                providers_file,
                workflow_providers,
                actions_file,
                workflow_actions,
            )
            workflows = [workflow]
        # else, if it stored in the db, it stored without the "workflow" key
        else:
            workflow = self._parse_workflow(
                tenant_id,
                parsed_workflow_yaml,
                providers_file,
                workflow_providers,
                actions_file,
                workflow_actions,
            )
            workflows = [workflow]
        return workflows

    def _get_workflow_provider_types_from_steps_and_actions(
        self, steps: list[Step], actions: list[Step]
    ) -> list[str]:
        provider_types = []
        steps_and_actions = [*steps, *actions]
        for step_or_action in steps_and_actions:
            try:
                provider_type = step_or_action.provider.provider_type
                if provider_type not in provider_types:
                    provider_types.append(provider_type)
            except Exception:
                self.logger.warning(
                    "Could not get provider type from step or action",
                    extra={"step_or_action": step_or_action},
                )
        return provider_types

    def _parse_workflow(
        self,
        tenant_id,
        workflow: dict,
        providers_file: str,
        workflow_providers: dict = None,
        actions_file: str = None,
        workflow_actions: dict = None,
    ) -> Workflow:
        self.logger.debug("Parsing workflow")
        workflow_id = self._get_workflow_id(tenant_id, workflow)
        context_manager = ContextManager(
            tenant_id=tenant_id, workflow_id=workflow_id, workflow=workflow
        )
        # Parse the providers (from the workflow yaml or from the providers directory)
        self._load_providers_config(
            tenant_id, context_manager, workflow, providers_file, workflow_providers
        )
        # Parse the actions (from workflow, actions yaml and database)
        self._load_actions_config(
            tenant_id, context_manager, workflow, actions_file, workflow_actions
        )
        workflow_id = self._parse_id(workflow)
        workflow_disabled = self.__class__.parse_disabled(workflow)
        workflow_owners = self._parse_owners(workflow)
        workflow_tags = self._parse_tags(workflow)
        workflow_steps = self._parse_steps(context_manager, workflow)
        workflow_actions = self._parse_actions(context_manager, workflow)
        workflow_interval = self.parse_interval(workflow)
        on_failure_action = self._get_on_failure_action(context_manager, workflow)
        workflow_triggers = self.get_triggers_from_workflow(workflow)
        workflow_provider_types = (
            self._get_workflow_provider_types_from_steps_and_actions(
                workflow_steps, workflow_actions
            )
        )
        workflow_strategy = workflow.get(
            "strategy", WorkflowStrategy.NONPARALLEL_WITH_RETRY.value
        )
        workflow_consts = workflow.get("consts", {})

        workflow = Workflow(
            workflow_id=workflow_id,
            workflow_description=workflow.get("description"),
            workflow_disabled=workflow_disabled,
            workflow_owners=workflow_owners,
            workflow_tags=workflow_tags,
            workflow_interval=workflow_interval,
            workflow_triggers=workflow_triggers,
            workflow_steps=workflow_steps,
            workflow_actions=workflow_actions,
            on_failure=on_failure_action,
            context_manager=context_manager,
            workflow_providers_type=workflow_provider_types,
            workflow_strategy=workflow_strategy,
            workflow_consts=workflow_consts,
        )
        self.logger.debug("Workflow parsed successfully")
        return workflow

    def _load_providers_config(
        self,
        tenant_id,
        context_manager: ContextManager,
        workflow: dict,
        providers_file: str,
        workflow_providers: dict = None,
    ):
        self.logger.debug("Parsing providers")
        providers_file = (
            providers_file or os.environ.get("KEEP_PROVIDERS_FILE") or "providers.yaml"
        )
        if providers_file and os.path.exists(providers_file):
            self._parse_providers_from_file(context_manager, providers_file)

        # if the workflow file itself contain providers (mainly backward compatibility)
        if workflow_providers:
            context_manager.providers_context.update(workflow_providers)

        self._parse_providers_from_env(context_manager)
        self._load_providers_from_db(context_manager, tenant_id)
        self.logger.debug("Providers parsed and loaded successfully")

    def _load_providers_from_db(
        self, context_manager: ContextManager, tenant_id: str = None
    ):
        """_summary_

        Args:
            context_manager (ContextManager): _description_
            tenant_id (str, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """
        # If there is no tenant id, e.g. running from CLI, no db here
        self.logger.debug("Loading installed providers to context")
        if not tenant_id:
            return
        # Load installed providers
        all_providers = ProvidersFactory.get_all_providers()
        # _use_loaded_provider_cache is a flag to control whether to use the loaded providers cache
        if not self._loaded_providers_cache or not self._use_loaded_provider_cache:
            # this should print once when the providers are loaded for the first time
            self.logger.info("Loading installed providers to workfloe")
            installed_providers = ProvidersFactory.get_installed_providers(
                tenant_id=tenant_id, all_providers=all_providers, override_readonly=True
            )
            self._loaded_providers_cache = installed_providers
            self.logger.info("Installed providers loaded successfully")
        else:
            self.logger.debug("Using cached loaded providers")
            # before we can use cache, we need to check if new providers are added or deleted
            _installed_providers = get_installed_providers(tenant_id=tenant_id)
            _installed_providers_ids = set([p.id for p in _installed_providers])
            _cached_provider_ids = set([p.id for p in self._loaded_providers_cache])
            if _installed_providers_ids != _cached_provider_ids:
                # this should print only when provider deleted/added
                self.logger.info("Providers cache is outdated, reloading providers")
                installed_providers = ProvidersFactory.get_installed_providers(
                    tenant_id=tenant_id,
                    all_providers=all_providers,
                    override_readonly=True,
                )
                self._loaded_providers_cache = installed_providers
                self.logger.info("Providers cache reloaded")
            else:
                installed_providers = self._loaded_providers_cache
        for provider in installed_providers:
            self.logger.debug("Loading provider", extra={"provider_id": provider.id})
            try:
                provider_name = provider.details.get("name")
                context_manager.providers_context[provider.id] = provider.details
                # map also the name of the provider, not only the id
                # so that we can use the name to reference the provider
                context_manager.providers_context[provider_name] = provider.details
                self.logger.debug(f"Provider {provider.id} loaded successfully")
            except Exception as e:
                self.logger.error(
                    f"Error loading provider {provider.id}", extra={"exception": e}
                )
        self.logger.debug("Installed providers loaded successfully")
        return installed_providers

    def _parse_providers_from_env(self, context_manager: ContextManager):
        """
        Parse providers from the KEEP_PROVIDERS environment variables.
            Either KEEP_PROVIDERS to load multiple providers or KEEP_PROVIDER_<provider_name> can be used.

        KEEP_PROVIDERS is a JSON string of the providers config.
            (e.g. {"slack-prod": {"authentication": {"webhook_url": "https://hooks.slack.com/services/..."}}})
        """
        providers_json = os.environ.get("KEEP_PROVIDERS")

        # check if env var is absolute or relative path to a providers json file
        if providers_json and re.compile(r"^(\/|\.\/|\.\.\/).*\.json$").match(
            providers_json
        ):
            with open(file=providers_json, mode="r", encoding="utf8") as file:
                providers_json = file.read()

        if providers_json:
            try:
                self.logger.debug(
                    "Parsing providers from KEEP_PROVIDERS environment variable"
                )
                providers_dict = json.loads(providers_json)
                self._inject_env_variables(providers_dict)
                context_manager.providers_context.update(providers_dict)
                self.logger.debug(
                    "Providers parsed successfully from KEEP_PROVIDERS environment variable"
                )
            except json.JSONDecodeError:
                self.logger.error(
                    "Error parsing providers from KEEP_PROVIDERS environment variable"
                )

        for env in os.environ.keys():
            if env.startswith("KEEP_PROVIDER_"):
                # KEEP_PROVIDER_SLACK_PROD
                provider_name = (
                    env.replace("KEEP_PROVIDER_", "").replace("_", "-").lower()
                )
                try:
                    self.logger.debug(f"Parsing provider {provider_name} from {env}")
                    # {'authentication': {'webhook_url': 'https://hooks.slack.com/services/...'}}
                    provider_config = json.loads(os.environ.get(env))
                    self._inject_env_variables(provider_config)
                    context_manager.providers_context[provider_name] = provider_config
                    self.logger.debug(
                        f"Provider {provider_name} parsed successfully from {env}"
                    )
                except json.JSONDecodeError:
                    self.logger.error(
                        f"Error parsing provider config from environment variable {env}"
                    )

    def _inject_env_variables(self, config):
        """
        Recursively inject environment variables into the config.
        """
        if isinstance(config, dict):
            for key, value in config.items():
                config[key] = self._inject_env_variables(value)
        elif isinstance(config, list):
            return [self._inject_env_variables(item) for item in config]
        elif (
            isinstance(config, str) and config.startswith("$(") and config.endswith(")")
        ):
            env_var = config[2:-1]
            env_var_val = os.environ.get(env_var)
            if not env_var_val:
                self.logger.warning(
                    f"Environment variable {env_var} not found while injecting into config"
                )
                return config
            return env_var_val
        return config

    def _parse_providers_from_workflow(
        self, context_manager: ContextManager, workflow: dict
    ) -> None:
        context_manager.providers_context.update(workflow.get("providers"))
        self.logger.debug("Workflow providers parsed successfully")

    def _parse_providers_from_file(
        self, context_manager: ContextManager, providers_file: str
    ):
        with open(providers_file, "r") as file:
            try:
                providers = cyaml.safe_load(file)
            except cyaml.YAMLError:
                self.logger.exception(f"Error parsing providers file {providers_file}")
                raise
            context_manager.providers_context.update(providers)
        self.logger.debug("Providers config parsed successfully")

    def _parse_id(self, workflow) -> str:
        workflow_id = workflow.get("id")
        if workflow_id is None:
            raise ValueError("Workflow ID is required")
        return workflow_id

    def _parse_owners(self, workflow) -> typing.List[str]:
        workflow_owners = workflow.get("owners", [])
        return workflow_owners

    def _parse_tags(self, workflow) -> typing.List[str]:
        workflow_tags = workflow.get("tags", [])
        return workflow_tags

    def parse_interval(self, workflow) -> int:
        # backward compatibility
        workflow_interval = workflow.get("interval", 0)
        triggers = workflow.get("triggers", [])
        for trigger in triggers:
            if trigger.get("type") == "interval":
                workflow_interval = trigger.get("value", 0)
        return workflow_interval

    @staticmethod
    def parse_disabled(workflow_dict: dict) -> bool:
        workflow_is_disabled_in_yml = workflow_dict.get("disabled")
        return (
            True
            if (
                workflow_is_disabled_in_yml == "true"
                or workflow_is_disabled_in_yml is True
            )
            else False
        )

    @staticmethod
    def parse_provider_parameters(provider_parameters: dict) -> dict:
        parsed_provider_parameters = {}
        for parameter in provider_parameters:
            if isinstance(provider_parameters[parameter], (str, list, int, bool)):
                parsed_provider_parameters[parameter] = provider_parameters[parameter]
            elif isinstance(provider_parameters[parameter], dict):
                try:
                    parsed_provider_parameters[parameter] = StepProviderParameter(
                        **provider_parameters[parameter]
                    )
                except Exception:
                    # It could be a dict/list but not of ProviderParameter type
                    parsed_provider_parameters[parameter] = provider_parameters[
                        parameter
                    ]
        return parsed_provider_parameters

    def _parse_steps(
        self, context_manager: ContextManager, workflow
    ) -> typing.List[Step]:
        self.logger.debug("Parsing steps")
        workflow_steps = workflow.get("steps", [])
        workflow_steps_parsed = []
        for _step in workflow_steps:
            provider = self._get_step_provider(context_manager, _step)
            provider_parameters = _step.get("provider", {}).get("with")
            parsed_provider_parameters = Parser.parse_provider_parameters(
                provider_parameters
            )
            step_id = _step.get("name")
            step = Step(
                context_manager=context_manager,
                step_id=step_id,
                config=_step,
                provider=provider,
                provider_parameters=parsed_provider_parameters,
                step_type=StepType.STEP,
            )
            workflow_steps_parsed.append(step)
        self.logger.debug("Steps parsed successfully")
        return workflow_steps_parsed

    def _get_step_provider(self, context_manager: ContextManager, _step: dict) -> dict:
        step_provider = _step.get("provider")
        try:
            step_provider_type = step_provider.pop("type")
        except AttributeError:
            raise ValueError("Step provider type is required")
        try:
            step_provider_config = step_provider.pop("config")
        except KeyError:
            step_provider_config = {"authentication": {}}
        provider_id, provider_config = self._parse_provider_config(
            context_manager, step_provider_type, step_provider_config
        )
        provider = ProvidersFactory.get_provider(
            context_manager, provider_id, step_provider_type, provider_config
        )
        return provider

    def _load_actions_config(
        self,
        tenant_id,
        context_manager: ContextManager,
        workflow: dict,
        actions_file: str,
        workflow_actions: dict = None,
    ):
        self.logger.debug("Parsing actions")
        actions_file = (
            actions_file or os.environ.get("KEEP_ACTIONS_FILE") or "actions.yaml"
        )
        if actions_file and os.path.exists(actions_file):
            self._parse_actions_from_file(context_manager, actions_file)
        # if the workflow file itself contain actions (mainly backward compatibility)
        if workflow_actions:
            for action in workflow_actions:
                context_manager.actions_context.update(
                    {action.get("use") or action.get("name"): action}
                )
        self._load_actions_from_db(context_manager, tenant_id)
        self.logger.debug("Actions parsed and loaded successfully")

    def _parse_actions_from_file(
        self, context_manager: ContextManager, actions_file: str
    ):
        """load actions from file into context manager"""
        if actions_file and os.path.isfile(actions_file):
            with open(actions_file, "r") as file:
                try:
                    actions_content = cyaml.safe_load(file)
                except cyaml.YAMLError:
                    self.logger.exception(f"Error parsing actions file {actions_file}")
                    raise
                # create a hashmap -> action
                for action in actions_content.get("actions", []):
                    context_manager.actions_context.update(
                        {action.get("use") or action.get("name"): action}
                    )

    def _load_actions_from_db(
        self, context_manager: ContextManager, tenant_id: str = None
    ):
        # If there is no tenant id, e.g. running from CLI, no db here
        if not tenant_id:
            return
        # Load actions from db
        actions = ActionsCRUD.get_all_actions(tenant_id)
        for action in actions:
            self.logger.debug("Loading action", extra={"action_id": action.use})
            try:
                context_manager.actions_context[action.use] = action.details
                self.logger.debug(f"action {action.use} loaded successfully")
            except Exception as e:
                self.logger.error(
                    f"Error loading action {action.use}", extra={"exception": e}
                )

    def _get_action(
        self,
        context_manager: ContextManager,
        action: dict,
        action_name: str | None = None,
    ) -> Step:
        name = action_name or action.get("name")
        provider = action.get("provider", {})
        provider_config = provider.get("config")
        provider_parameters = provider.get("with", {})
        parsed_provider_parameters = Parser.parse_provider_parameters(
            provider_parameters
        )
        provider_type = provider.get("type")
        provider_id, provider_config = self._parse_provider_config(
            context_manager, provider_type, provider_config
        )
        provider = ProvidersFactory.get_provider(
            context_manager,
            provider_id,
            provider_type,
            provider_config,
            **parsed_provider_parameters,
        )
        action = Step(
            context_manager=context_manager,
            step_id=name,
            provider=provider,
            config=action,
            provider_parameters=provider_parameters,
            step_type=StepType.ACTION,
        )
        return action

    def _parse_actions(
        self, context_manager: ContextManager, workflow: dict
    ) -> typing.List[Step]:
        self.logger.debug("Parsing actions")
        workflow_actions_raw = workflow.get("actions", [])
        workflow_actions = self._merge_action_by_use(
            workflow_actions=workflow_actions_raw,
            actions_context=context_manager.actions_context,
        )
        workflow_actions_parsed = []
        for _action in workflow_actions:
            parsed_action = self._get_action(context_manager, _action)
            workflow_actions_parsed.append(parsed_action)
        self.logger.debug("Actions parsed successfully")
        return workflow_actions_parsed

    def _load_actions_from_file(
        self, actions_file: typing.Optional[str]
    ) -> typing.Mapping[str, dict]:
        """load actions from file and convert results into a set of unique actions by id"""
        actions_set = {}
        if actions_file and os.path.isfile(actions_file):
            # load actions from a file
            actions = []
            with open(actions_file, "r") as file:
                try:
                    actions = cyaml.safe_load(file)
                except cyaml.YAMLError:
                    self.logger.exception(f"Error parsing actions file {actions_file}")
                    raise
            # convert actions into dictionary of unique object by id
            for action in actions:
                action_id = action.get("id") or action.get("name")
                if action_id or action_id not in actions_set:
                    actions_set[action_id] = action
                else:
                    self.logger.exception(
                        f"action defined in {actions_file} should have id as unique field"
                    )
        else:
            self.logger.warning(
                f"No action located at {actions_file}, skip loading reusable actions"
            )
        return actions_set

    def _merge_action_by_use(
        self,
        workflow_actions: typing.List[dict],
        actions_context: typing.Mapping[str, dict],
    ) -> typing.Iterable[dict]:
        """Merge actions from workflow and reusable actions file into one"""
        for action in workflow_actions:
            extended_action = actions_context.get(action.get("use"), {})
            yield ParserUtils.deep_merge(action, extended_action)

    def _get_on_failure_action(
        self, context_manager: ContextManager, workflow: dict
    ) -> Step | None:
        """
        Parse the on-failure action

        Args:
            context_manager (ContextManager): _description_
            workflow (dict): _description_

        Returns:
            Action | None: _description_
        """
        self.logger.debug("Parsing on-failure")
        workflow_on_failure = workflow.get("on-failure", {})
        if workflow_on_failure:
            parsed_action = self._get_action(
                context_manager=context_manager,
                action=workflow_on_failure,
                action_name="on-failure",
            )
            self.logger.debug("Parsed on-failure successfully")
            return parsed_action
        self.logger.debug("No on-failure action")

    def _extract_provider_id(self, context_manager: ContextManager, provider_type: str):
        """
        Translate {{ <provider_id>.<config_id> }} to a provider id

        Args:
            provider_type (str): _description_

        Raises:
            ValueError: _description_

        Returns:
            _type_: _description_
        """
        # TODO FIX THIS SHIT
        provider_type = provider_type.split(".")
        if len(provider_type) != 2:
            message = "Provider config is not valid, should be in the format: {{ <provider_id>.<config_id> }}."
            message += f" Current value is {provider_type}"
            if context_manager.workflow_id:
                message += f". Workflow id: {context_manager.workflow_id}"

            raise ValueError(message)

        provider_id = provider_type[1].replace("}}", "").strip()
        return provider_id

    def _parse_provider_config(
        self,
        context_manager: ContextManager,
        provider_type: str,
        provider_config: str | dict | None,
    ) -> tuple:
        """
        Parse provider config.
            If the provider config is a dict, return it as is.
            If the provider config is None, return an empty dict.
            If the provider config is a string, extract the config from the providers context.
            * When provider config is either dict or None, provider config id is the same as the provider type.

        Args:
            provider_type (str): The provider type
            provider_config (str | dict | None): The provider config

        Raises:
            ValueError: When the provider config is a string and the provider config id is not found in the providers context.

        Returns:
            tuple: provider id and provider parsed config
        """
        # Support providers without config such as logfile or mock
        if isinstance(provider_config, dict):
            return provider_type, provider_config
        elif provider_config is None:
            return provider_type, {"authentication": {}}
        # extract config when using {{ <provider_id>.<config_id> }}
        elif isinstance(provider_config, str):
            config_id = self._extract_provider_id(context_manager, provider_config)
            provider_config = context_manager.providers_context.get(config_id)
            if not provider_config:
                self.logger.warning(
                    "Provider not found in configuration, did you configure it?",
                    extra={
                        "provider_id": config_id,
                        "provider_type": provider_type,
                        "provider_config": provider_config,
                        "tenant_id": context_manager.tenant_id,
                    },
                )
                provider_config = {"authentication": {}}
            return config_id, provider_config

    def get_providers_from_workflow(self, workflow: dict):
        """extract the provider names from a worklow

        Args:
            workflow (dict): _description_
        """
        actions_providers = [
            action.get("provider") for action in workflow.get("actions", [])
        ]
        steps_providers = [step.get("provider") for step in workflow.get("steps", [])]
        providers = actions_providers + steps_providers
        try:
            providers = [
                {
                    "name": p.get("config", f"NAME.{p.get('type')}")
                    .split(".")[1]
                    .replace("}}", "")
                    .strip(),
                    "type": p.get("type"),
                }
                for p in providers
            ]
        except:
            self.logger.error(
                "Failed to extract providers from workflow",
                extra={"workflow": workflow},
            )
            raise
        return providers

    def get_triggers_from_workflow(self, workflow: dict):
        """extract the trigger names from a worklow

        Args:
            workflow (dict): _description_
        """
        # triggers:
        # - type: alert
        # filters:
        # - key: alert.source
        #   value: awscloudwatch
        triggers = workflow.get("triggers", [])
        return triggers


class ParserUtils:

    @staticmethod
    def deep_merge(source: dict, dest: dict) -> dict:
        """Perform deep merge on two objects.

        Example:
            source = {"deep1": {"deep2": 1}}
            dest = {"deep1", {"deep2": 2, "deep3": 3}}
            returns -> {"deep1": {"deep2": 1, "deep3": 3}}

        Returns:
            dict: The new object contains merged results
        """
        # make sure not to modify dest object by creating new one
        out = copy.deepcopy(dest)
        ParserUtils._merge(source, out)
        return out

    @staticmethod
    def _merge(ob1: dict, ob2: dict) -> dict:
        """Merge two objects, in case of duplicate key in two objects, take value of the first source"""
        for key, value in ob1.items():
            # encounter dict, merge into one
            if isinstance(value, dict) and key in ob2:
                next_node = ob2.get(key)
                ParserUtils._merge(value, next_node)
            # encounter list, merge by index and concat two lists
            elif isinstance(value, list) and key in ob2:
                next_nodes = ob2.get(key, [])
                for i in range(max(len(value), len(next_nodes))):
                    next_node = next_nodes[i] if i < len(next_nodes) else {}
                    value_node = value[i] if i < len(value) else {}
                    ParserUtils._merge(value_node, next_node)
            else:
                ob2[key] = value
