# This should not be here, but it is for now
import json
import logging
import time

from langchain import LLMChain, PromptTemplate
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferWindowMemory


class GptUtils:
    TEMPLATE = "You are KeepAI, a GitHub GitOps bot installed in repositories, that generates alerts specifications based on user input.\n {human_input}"

    def __init__(self, tenant_id: str):
        # TODO: in the future, load openai key according to tenant_id
        self.tenant_id = tenant_id

        prompt = PromptTemplate(
            input_variables=["human_input"],
            template=self.TEMPLATE,
            validate_template=False,
        )

        # TODO: understand how does memory work, this should probably be generated for every tenant?
        self.chain = LLMChain(
            llm=ChatOpenAI(request_timeout=300, model_name="gpt-4"),
            prompt=prompt,
            verbose=False,
            memory=ConversationBufferWindowMemory(k=2),
        )

        self.logger = logging.getLogger(__name__)

    def generate_alert(
        self,
        alert_prompt: str,
        repository_context: dict,
        alerts_context: list,
        schema: dict,
        provider_type: str,
        provider_logs: list = [],
    ) -> dict:
        """Generates an alert based on the prompt and context

        Args:
            alert_prompt (str): The alert prompt received from the user
            repository_context (dict): A dictionary containing the repository context
            alerts_context (list): A list of alerts that were already generated for this repository
            schema (dict): The API schema that can be used to create the alert in the provider
            provider_type (str): The provider type (E.g. grafana, prometheus, etc)

        Returns:
            str: The generated alert in the provider's API schema
        """
        self.logger.info("Creating alert from specification")
        start_time = time.time()
        human_prompt = (
            'Create the following: "{prompt}" alert specification. Only output the generated alert in a format that is importable by the API of {provider_type}.\n'
            "Do not write any additional text. The output is expected to be a single AI generated alert specification, indented properly, and ready to be imported into the {provider_type} API.\n"
            "The alert is coming from this repository: {repo}.\n"
            "Create the alert based on these existing alerts imported from {provider_type}: {alerts}.\n"
        ).format(
            prompt=alert_prompt,
            repo=json.dumps(repository_context),
            alerts=json.dumps(alerts_context),
            provider_type=provider_type,
        )

        if schema:
            human_prompt += (
                "This is {provider_type}'s OpenAPI schema for alert creation: \n```{schema}```\n The generated alert MUST adhere this OpenAPI schema.\n"
            ).format(schema=json.dumps(schema), provider_type=provider_type)
        if provider_logs:
            human_prompt += (
                "Here is a list of logs from {provider_type} to help with the alert generation: \n```{logs}```\n"
            ).format(
                logs=json.dumps(provider_logs, default=str), provider_type=provider_type
            )

        completion = self.chain.predict(human_input=human_prompt)
        end_time = time.time()
        self.logger.info(f"Time to create alert: {end_time - start_time} seconds")
        return json.loads(completion)

    def repair_alert(
        self, previous_alert: dict, error: str, provider_type: str, schema: dict
    ) -> dict:
        """Repairs an alert based on the previous alert and the error

        Args:
            previous_alert (dict): The previous alert that was generated
            error (str): The error that was received from the provider
            provider_type (str): The provider type (E.g. grafana, prometheus, etc)
            schema (dict): The API schema that can be used to create the alert in the provider

        Returns:
            dict: The fixed alert in the provider's API schema
        """
        self.logger.info("Repairing alert")
        start_time = time.time()
        human_prompt = (
            "This alert: ```{bad_alert}``` that you generated does not conform the {provider_type} API schema, Please provide the alert specification in the valid API schema.\n"
            'This is the error: "{error}" that the {provider_type} API returned.\n'
            "Do not write any additional text, only output the fixed alert specification JSON in the acceptable schema of {provider_type} API.\n"
            "This is {provider_type} API scehma for alert creation: {schema}. Your response MUST match this schema\n"
        ).format(
            error=error,
            bad_alert=json.dumps(previous_alert),
            provider_type=provider_type,
            schema=json.dumps(schema),
        )
        completion = self.chain.predict(human_input=human_prompt)
        end_time = time.time()
        self.logger.info(f"Time to repair alert: {end_time - start_time} seconds")
        return json.loads(completion.replace("AI: ", ""))
