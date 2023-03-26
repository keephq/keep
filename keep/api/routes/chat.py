import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from keep.api.models.chat_response import ChatResponse
from keep.api.utils.callback import (
    QuestionGenCallbackHandler,
    StreamingLLMCallbackHandler,
)
from keep.api.utils.query_data import get_chain

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    if not os.environ.get("OPENAI_API_KEY"):
        resp = ChatResponse(
            sender="bot",
            message="openai api key not found",
            type="error",
        )
        await websocket.send_json(resp.dict())
        return
    question_handler = QuestionGenCallbackHandler(websocket)
    stream_handler = StreamingLLMCallbackHandler(websocket)
    qa_chain = get_chain(question_handler, stream_handler)

    while True:
        try:
            # Receive and send back the client message
            question = await websocket.receive_text()
            resp = ChatResponse(sender="you", message=question, type="stream")
            await websocket.send_json(resp.dict())

            # Construct a response
            start_resp = ChatResponse(sender="bot", message="", type="start")
            await websocket.send_json(start_resp.dict())

            await qa_chain.acall({"input": question})

            end_resp = ChatResponse(sender="bot", message="", type="end")
            await websocket.send_json(end_resp.dict())
        except WebSocketDisconnect:
            logger.info("websocket disconnect")
            break
        except Exception as e:
            logger.error(e)
            resp = ChatResponse(
                sender="bot",
                message="",
                type="error",
            )
            await websocket.send_json(resp.dict())
