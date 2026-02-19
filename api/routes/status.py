from fastapi import APIRouter

from keep.event_subscriber.event_subscriber import EventSubscriber

router = APIRouter()


@router.get("", description="simple status endpoint")
def status() -> dict:
    """
    Does nothing but return 200 response code

    Returns:
        dict: empty JSON object
    """
    event_subscriber = EventSubscriber.get_instance()
    return {
        "status": "OK",
        "consumer": event_subscriber.status(),
    }
