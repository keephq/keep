import enum
import logging

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from keep.api.core.config import config

# TODO
# This is beta code. It will be changed in the future.

# Sending emails is currently done via SendGrid. It doesnt fit well with OSS, so we need to:
# 1. Add EmailManager that will support more than just SendGrid
# 2. Add support for templates/html
# 3. Add support for SMTP (how will it work with templates?)


# In the OSS - you can overwrite the template ids
class EmailTemplates(enum.Enum):
    WORKFLOW_RUN_FAILED = config(
        "WORKFLOW_FAILED_EMAIL_TEMPLATE_ID",
        default="d-bb1b3bb30ce8460cbe6ed008701affb1",
    )
    ALERT_ASSIGNED_TO_USER = config(
        "ALERT_ASSIGNED_TO_USER_EMAIL_TEMPLATE_ID",
        default="d-58ec64ed781e4c359e18da7ad97ac750",
    )


logger = logging.getLogger(__name__)

# CONSTS
FROM_EMAIL = config("SENDGRID_FROM_EMAIL", default="platform@keephq.dev")
API_KEY = config("SENDGRID_API_KEY", default=None)
CC = config("SENDGRID_CC", default="founders@keephq.dev")
KEEP_EMAILS_ENABLED = config("KEEP_EMAILS_ENABLED", default=False, cast=bool)


def send_email(
    to_email: str,
    template_id: EmailTemplates,
    **kwargs,
) -> bool:
    if not KEEP_EMAILS_ENABLED:
        logger.debug("Emails are disabled, skipping sending email")
        return False

    # that's ok on OSS
    if not API_KEY:
        logger.debug("No SendGrid API key, skipping sending email")
        return False

    message = Mail(from_email=FROM_EMAIL, to_emails=to_email)
    message.template_id = template_id.value
    # TODO: validate the kwargs and the template parameters are the same
    message.dynamic_template_data = kwargs
    # send the email
    try:
        logger.info(f"Sending email to {to_email} with template {template_id}")
        sg = SendGridAPIClient(API_KEY)
        sg.send(message)
        logger.info(f"Email sent to {to_email} with template {template_id}")
        return True
    except Exception as e:
        logger.error(
            f"Failed to send email to {to_email} with template {template_id}: {e}"
        )
        raise
