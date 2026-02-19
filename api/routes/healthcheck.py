from fastapi import APIRouter

router = APIRouter()


@router.get("", description="simple healthcheck endpoint")
def healthcheck() -> dict:
    """
    Does nothing but return 200 response code

    Returns:
        dict: empty JSON object
    """
    return {}
