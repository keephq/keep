# this file is for debugging purposes
# its code written to profile the SQL queries

import inspect
import logging

# it basically log the SQL queries and the time it took to execute them
# in a file called sqlalchemy_queries.log
import os
import threading
import time
from logging.handlers import RotatingFileHandler

from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


if os.environ.get("DEBUG_SQL", False):
    logger.setLevel(logging.DEBUG)
    # Configure logging
    logger = logging.getLogger("profiler")
    logger.setLevel(logging.INFO)
    file_handler = RotatingFileHandler(
        "sqlalchemy_queries.log", maxBytes=1024 * 1024 * 5, backupCount=5, mode="a"
    )
    file_handler.setLevel(logging.INFO)
    # Create a formatter and set it to the handler
    formatter = logging.Formatter("%(asctime)s - %(message)s")
    file_handler.setFormatter(formatter)
    # Add the handler to the logger
    logger.addHandler(file_handler)
    # Prevent the logger from propagating messages to the root logger
    logger.propagate = False

    def get_callee():
        try:
            # Inspect the stack and find the callee outside of this module
            stack = inspect.stack()
            for frame_info in stack:
                # Inspecting the stack frame to find the first caller outside of this script
                # You might need to adjust the conditions based on your project structure
                if (
                    frame_info.function
                    not in [
                        "get_callee",
                        "after_cursor_execute",
                        "before_cursor_execute",
                    ]
                    and __file__ in frame_info.filename
                ):
                    return f"{frame_info.function} in {frame_info.filename}:{frame_info.lineno}"
        except Exception:
            return "Unknown callee"
        return "Callee not found"

    # Function to track query start time
    @event.listens_for(Engine, "before_cursor_execute")
    def before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        context._query_start_time = time.time()

    # Function to log the query and execution time
    @event.listens_for(Engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total = time.time() - context._query_start_time
        callee = get_callee()
        thread_name = threading.current_thread().name
        logger.critical(
            f"Thread: {thread_name}, Callee: {callee}, Query: {statement}, Parameters: {parameters}, Time: {total:.5f} seconds"
        )
