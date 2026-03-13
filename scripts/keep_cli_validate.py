import argparse
import logging
import sys
import os
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("keep-validator")

# Add the Keep package path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

def setup_mocks():
    """
    Mock database dependencies to allow offline validation.
    """
    logger.info("🔧 Setting up offline mocks...")
    
    # Mock DB modules BEFORE imports
    sys.modules["keep.api.core.db"] = MagicMock()
    sys.modules["keep.actions.actions_factory"] = MagicMock()
    sys.modules["keep.api.models.db.workflow"] = MagicMock()
    sys.modules["keep.providers.providers_factory"] = MagicMock()
    
    # Mock specific functions that might be called during import or init
    sys.modules["keep.api.core.db"].get_workflow_id.return_value = None
    sys.modules["keep.providers.providers_factory"].ProvidersFactory.get_all_providers.return_value = []

def validate_file(parser_instance, file_path):
    """
    Validate a single workflow file.
    """
    from keep.functions import cyaml
    
    try:
        with open(file_path, "r") as f:
            content = cyaml.safe_load(f)
        
        # Handle "workflow" or "alert" root keys
        if "workflow" in content:
            workflow_data = content["workflow"]
        elif "alert" in content:
            workflow_data = content["alert"]
        else:
            # Assume raw dict is the workflow if no root key found (or fail?)
            # Keep usually expects a root key for CLI parsing, but let's be flexible
            workflow_data = content

        # Set a dummy ID if missing, to pass basic validation
        if not workflow_data.get("id"):
            workflow_data["id"] = "dry-run-id"

        # The core validation step: Parse it!
        # We use a dummy tenant_id "dry-run"
        workflows = parser_instance.parse("dry-run", workflow_data)
        
        if workflows:
            logger.info(f"✅ Valid: {file_path} (ID: {workflows[0].workflow_id})")
            return True
        else:
            logger.error(f"❌ Invalid: {file_path} (Parser returned no workflows)")
            return False

    except Exception as e:
        logger.error(f"❌ Error validating {file_path}: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Validate Keep workflows offline (CI mode).")
    parser.add_argument("path", help="Path to a workflow file or directory")
    args = parser.parse_args()

    # 1. Setup Mocks
    setup_mocks()

    # 2. Import Parser AFTER mocks
    from keep.parser.parser import Parser
    
    # 3. Initialize Parser with mocked methods
    keep_parser = Parser()
    # Mock internal DB calls of the parser instance
    keep_parser._get_workflow_id = MagicMock(side_effect=lambda tenant_id, w: w.get("id", "dry-run-id"))
    keep_parser._load_providers_from_db = MagicMock(return_value=[])
    keep_parser._load_actions_from_db = MagicMock(return_value=[])

    # 4. Run Validation
    success_count = 0
    fail_count = 0

    if os.path.isfile(args.path):
        if validate_file(keep_parser, args.path):
            success_count += 1
        else:
            fail_count += 1
    elif os.path.isdir(args.path):
        for root, _, files in os.walk(args.path):
            for file in files:
                if file.endswith((".yaml", ".yml")):
                    full_path = os.path.join(root, file)
                    if validate_file(keep_parser, full_path):
                        success_count += 1
                    else:
                        fail_count += 1
    else:
        logger.error(f"Path not found: {args.path}")
        sys.exit(1)

    # 5. Summary
    logger.info("-" * 30)
    logger.info(f"Summary: {success_count} passed, {fail_count} failed")
    
    if fail_count > 0:
        sys.exit(1)
    
    sys.exit(0)

if __name__ == "__main__":
    main()
