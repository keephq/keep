import os

_TRUTHY = {"1", "true", "yes", "on"}


def is_ai_temperature_disabled() -> bool:
    """Whether the ``temperature`` parameter should be omitted from AI requests.

    Controlled by the ``KEEP_AI_DISABLE_TEMPERATURE`` environment variable. Some
    models (e.g. OpenAI reasoning models) only accept the default temperature and
    reject any explicit value with a 400 error, so this allows opting out.
    """
    return os.environ.get("KEEP_AI_DISABLE_TEMPERATURE", "false").strip().lower() in _TRUTHY


def get_ai_temperature_kwargs(temperature: float = 0.2) -> dict:
    """Return the ``temperature`` kwargs for an AI completion request.

    Returns an empty dict when temperature is disabled (see
    :func:`is_ai_temperature_disabled`), so the parameter is omitted entirely.
    """
    return {} if is_ai_temperature_disabled() else {"temperature": temperature}
