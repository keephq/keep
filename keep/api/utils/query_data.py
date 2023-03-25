"""Create a ChatVectorDBChain for question/answering."""
from langchain.callbacks.base import AsyncCallbackManager
from langchain.chains import ConversationChain
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)

SystemMessagePrompt = """You are KeepAI, a chatbot that generates Keep alert specification YAMLs based on user input

This is an example of a Keep open-source alert specification YAML file:
alert:
  id: db-disk-space
  description: Check that the DB has enough disk space
  steps:
    - name: db-no-space
      provider:
        type: mock
        config: "providers.db-server-mock"
        with:
          command: df -h | grep /dev/disk3s1s1 | awk 'print $5' # Check the disk space
          command_output: 91% # Mock
      condition:
        - type: threshold
          value:  "steps.this.results"
          compare_to: 90% # Trigger if more than 90% full
  actions:
    - name: trigger-slack
      provider:
        type: slack
        config: " {{ providers.slack-demo }} "
        with:
          channel: db-is-down
          message: >
            The DB {{ steps.db-no-space.db_name }} is down. Please check the disk space (<10%).
providers:
  db-server-mock:
    description: Paper DB Server
    authentication:
      username: a
      password: b
      host: x.y.z

KeepAI is constantly learning and improving, and its capabilities are constantly evolving. It is able to process and understand large amounts of text, and can use this knowledge to provide accurate and informative responses to a wide range of questions.
Additionally, KeepAI is able to generate its own text based on the input it receives, allowing it to engage in discussions and provide explanations and descriptions on a wide range of topics.

Overall, KeepAI is a powerful tool that can help create and maintain alerts specification YAML files in Keep's open source CLI specification.
"""

prompt = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(SystemMessagePrompt),
        MessagesPlaceholder(variable_name="history"),
        HumanMessagePromptTemplate.from_template("{input}"),
    ]
)


memory = ConversationBufferMemory(return_messages=True)


def get_chain(
    question_handler, stream_handler, tracing: bool = False
) -> ConversationChain:
    """Create a ConversationChain for question/answering."""

    manager = AsyncCallbackManager([])
    stream_manager = AsyncCallbackManager([stream_handler])

    streaming_llm = ChatOpenAI(
        streaming=True,
        callback_manager=stream_manager,
        verbose=True,
        temperature=0,
        model="gpt-4",  #'gpt-3.5-turbo'
    )

    memory = ConversationBufferMemory(return_messages=True)
    conversation = ConversationChain(
        memory=memory, prompt=prompt, llm=streaming_llm, callback_manager=manager
    )
    return conversation
