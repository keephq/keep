from fastapi import HTTPException

class ActionsCRUDException(HTTPException):
    """An exception class that depicts any error comming from Action"""