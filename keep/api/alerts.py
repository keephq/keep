"""
Alert API endpoints with Redis connection reuse
"""
from flask import Blueprint, request, jsonify, current_app
from flask.httpauth import HTTPBasicAuth
from sqlalchemy.exc import SQLAlchemyError
import redis
from typing import Dict, Any, Optional
from datetime import datetime
import json
import traceback

from keep.models import Alert, AlertStatus, AlertPriority, db, User
from werkzeug.security import check_password_hash
from keep.services.alert_processor import AlertProcessor
from keep.utils.circuit_breaker import CircuitBreaker, CircuitBreakerError
from keep.utils.retry import retry_with_backoff
from keep.celery_tasks.alert_tasks import process_alert_async

alerts_bp = Blueprint('alerts', __name__)
auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    """Verify username and password against User model."""
    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        return user
    return False

def get_redis_client():
    """
    Get Redis client from app context (singleton pattern).
    Returns the same Redis client instance for all requests.
    """
    return current_app.redis_client

def get_alert_processor():
    """Get an instance of AlertProcessor with dependencies."""
    redis_client = get_redis_client()
    return AlertProcessor(redis_client=redis_client)

@alerts_bp.route('/', methods=['POST'])
@auth.login_required
def create_alert():
    """
    Create a new alert.
    """
    try:
        # Get JSON data
        data = request.get_json()
        if data is None:
            return jsonify({'error': 'Request must be JSON'}), 400

        # Validate required fields (basic)
        if 'name' not in data or 'source' not in data:
            return jsonify({'error': 'Missing required fields: name, source'}), 400

        # Process the alert
        processor = get_alert_processor()
        alert = processor.process_alert(data)

        # Return the created alert
        return jsonify(alert.to_dict()), 201

    except ValueError as e:
        # Validation error from processor or model
        return jsonify({'error': str(e)}), 400
    except redis.RedisError as e:
        current_app.logger.error(f'Redis error: {str(e)}')
        return jsonify({'error': 'Service unavailable'}), 503
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f'Database error: {str(e)}')
        return jsonify({'error': 'Database error'}), 500
    except Exception as e:
        current_app.logger.error(f'Unexpected error: {str(e)}\n{traceback.format_exc()}')
        return jsonify({'error': 'Internal server error'}), 500