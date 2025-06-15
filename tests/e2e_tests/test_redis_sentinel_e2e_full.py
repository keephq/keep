#!/usr/bin/env python3
"""
Full E2E test for Redis Sentinel integration with Keep.

This test:
1. Starts Docker Compose with Redis Sentinel + Keep API
2. Waits for Keep API to be healthy
3. Simulates an alert using Keep CLI
4. Checks Redis for expected keys (basic_processing and arq:result)
"""

import asyncio
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import List, Tuple

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
TEST_DIR = Path(__file__).parent
COMPOSE_FILE = TEST_DIR / "tests/e2e_tests/docker-compose-e2e-redis-sentinel-noauth.yml"
PROJECT_NAME = "keep-sentinel-e2e-test"
KEEP_API_URL = "http://localhost:8080"
HEALTH_CHECK_TIMEOUT = 120  # seconds
REDIS_CHECK_TIMEOUT = 30    # seconds


class SentinelE2ETest:
    """Full E2E test for Redis Sentinel with Keep."""
    
    def __init__(self):
        self.compose_file = COMPOSE_FILE
        self.project_name = PROJECT_NAME
        
    def run_command(self, cmd: List[str], timeout: int = 60, capture_output: bool = True) -> Tuple[int, str, str]:
        """Run a shell command and return (returncode, stdout, stderr)."""
        logger.info(f"Running command: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd, 
                capture_output=capture_output, 
                text=True, 
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after {timeout} seconds: {' '.join(cmd)}")
            return -1, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            logger.error(f"Command failed with exception: {e}")
            return -1, "", str(e)
    
    def start_infrastructure(self):
        """Start the Docker Compose infrastructure."""
        logger.info("Starting Redis Sentinel + Keep infrastructure...")
        
        # Stop any existing containers first
        self.stop_infrastructure()
        
        # Start the infrastructure
        cmd = [
            "docker", "compose",
            "-f", str(self.compose_file),
            "-p", self.project_name,
            "up", "-d", "--build"
        ]
        
        returncode, stdout, stderr = self.run_command(cmd, timeout=300)  # 5 minutes for build
        if returncode != 0:
            raise RuntimeError(f"Failed to start infrastructure: {stderr}")
        
        logger.info("Infrastructure started successfully")
        
    def stop_infrastructure(self):
        """Stop and clean up the Docker Compose infrastructure."""
        logger.info("Stopping infrastructure...")
        
        cmd = [
            "docker", "compose",
            "-f", str(self.compose_file),
            "-p", self.project_name,
            "down", "-v", "--remove-orphans"
        ]
        
        self.run_command(cmd, timeout=60)
        logger.info("Infrastructure stopped")
    
    def wait_for_keep_api_healthy(self) -> bool:
        """Wait for Keep API to be healthy and responding."""
        logger.info(f"Waiting for Keep API to be healthy at {KEEP_API_URL}...")
        
        start_time = time.time()
        while time.time() - start_time < HEALTH_CHECK_TIMEOUT:
            try:
                response = requests.get(f"{KEEP_API_URL}/", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if "message" in data and "version" in data:
                        logger.info(f"✓ Keep API is healthy: {data}")
                        return True
                        
            except Exception as e:
                logger.debug(f"Keep API not ready yet: {e}")
            
            time.sleep(5)
        
        logger.error(f"Keep API did not become healthy within {HEALTH_CHECK_TIMEOUT} seconds")
        return False
    
    def simulate_alert(self) -> bool:
        """Simulate an alert using Keep CLI."""
        logger.info("Simulating alert using Keep CLI...")
        
        # Use docker exec to run keep CLI inside the keep-backend container
        cmd = [
            "docker", "exec", "-e", "KEEP_API_KEY=none", "-e", "KEEP_API_URL=http://localhost:8080", "keep-backend-sentinel-test",
            "keep", "-c", "/dev/null", "alert", "simulate", "-p", "prometheus",
            "title=\"Simulated Alert 1\"",
            "alert_transition=Triggered"
        ]
        
        returncode, stdout, stderr = self.run_command(cmd, timeout=30)
        if returncode != 0:
            logger.error(f"Failed to simulate alert: {stderr}")
            return False
        
        logger.info(f"✓ Alert simulated successfully: {stdout}")
        return True
    
    def check_redis_keys(self) -> bool:
        """Check Redis for expected keys using redis-cli."""
        logger.info("Checking Redis keys...")
        
        # Use docker run to execute redis-cli against the Redis master
        cmd = [
            "docker", "run", "--rm", "--network", f"{self.project_name}_keep-test",
            "redis:7-alpine", "redis-cli", "-h", "redis-master", "KEYS", "*"
        ]
        
        returncode, stdout, stderr = self.run_command(cmd, timeout=30)
        if returncode != 0:
            logger.error(f"Failed to check Redis keys: {stderr}")
            return False
        
        keys = stdout.strip().split('\n') if stdout.strip() else []
        logger.info(f"Found Redis keys: {keys}")
        
        # Check for expected key patterns
        basic_processing_keys = [k for k in keys if 'basic_processing' in k]
        arq_result_keys = [k for k in keys if 'arq:result' in k]
        
        logger.info(f"Basic processing keys: {basic_processing_keys}")
        logger.info(f"ARQ result keys: {arq_result_keys}")
        
        if not basic_processing_keys:
            logger.error("✗ No 'basic_processing' keys found")
            return False
        
        if not arq_result_keys:
            logger.error("✗ No 'arq:result' keys found")
            return False
        
        logger.info("✓ Expected Redis keys found")
        return True
    
    def run_full_test(self) -> bool:
        """Run the complete E2E test."""
        logger.info("Starting full Redis Sentinel E2E test...")
        logger.info("=" * 60)
        
        try:
            # Step 1: Start infrastructure
            logger.info("\n1. Starting infrastructure...")
            self.start_infrastructure()
            
            # Step 2: Wait for Keep API to be healthy
            logger.info("\n2. Waiting for Keep API to be healthy...")
            if not self.wait_for_keep_api_healthy():
                return False
            
            # Step 3: Simulate alert
            logger.info("\n3. Simulating alert...")
            if not self.simulate_alert():
                return False
            
            # Wait a bit for the alert to be processed
            logger.info("Waiting for alert processing...")
            time.sleep(10)
            
            # Step 4: Check Redis keys
            logger.info("\n4. Checking Redis keys...")
            if not self.check_redis_keys():
                return False
            
            logger.info("\n" + "=" * 60)
            logger.info("🎉 ALL TESTS PASSED!")
            logger.info("Redis Sentinel integration with Keep is working correctly!")
            return True
            
        except Exception as e:
            logger.error(f"Test failed with exception: {e}")
            return False
        
        finally:
            # Always clean up
            logger.info("\nCleaning up...")
            self.stop_infrastructure()


def main():
    """Main function to run the E2E test."""
    test = SentinelE2ETest()
    
    success = test.run_full_test()
    
    if success:
        logger.info("E2E test completed successfully!")
        exit(0)
    else:
        logger.error("E2E test failed!")
        exit(1)


if __name__ == "__main__":
    main()
