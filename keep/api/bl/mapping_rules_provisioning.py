import datetime
import logging
import os

from sqlmodel import Session, select

import keep.api.core.db as db
from keep.api.models.db.mapping import MappingRule, MappingRuleDtoIn
from keep.functions import cyaml

logger = logging.getLogger(__name__)

KEEP_MAPPINGS_DIRECTORY_ENV_VAR = "KEEP_MAPPINGS_DIRECTORY"
SYSTEM_ACTOR = "system"


def provision_mapping_rules_from_env(tenant_id: str):
    """Provision mapping rules from `KEEP_MAPPINGS_DIRECTORY` for a given tenant.

    Mirrors `WorkflowStore.provision_workflows` (directory-based, per-file YAML).
    Each YAML manifest in the directory describes one mapping rule:

        name: example-prometheus-mapping
        description: optional
        priority: 0
        type: csv
        matchers:
          - [namespace]
        rows:
          - { namespace: monitoring, team: platform }

    Behavior on every backend startup:
      - For each `.yaml`/`.yml` file in the directory: upsert by `name`. An
        existing rule with the same name (whether UI-created or previously
        provisioned) is adopted: `is_provisioned=True`, `provisioned_file=<path>`,
        contents overwritten from the manifest (including a reset of
        `disabled`/`override`/`condition` to their model defaults, since the
        manifest is the source of truth).
      - For DB rows with `is_provisioned=True` whose `provisioned_file` no
        longer exists or is outside the directory: delete (deprovision).
      - UI-created mapping rules (`is_provisioned=False`) whose name does not
        appear in any manifest are untouched.

    If `KEEP_MAPPINGS_DIRECTORY` is unset and any provisioned mapping rules
    exist in DB, they are deprovisioned (deleted).

    Per-manifest failures (malformed YAML, validation errors) are logged and
    the offending manifest is skipped; other manifests in the directory still
    process. Each manifest is committed in its own transaction.
    """
    mappings_dir = os.environ.get(KEEP_MAPPINGS_DIRECTORY_ENV_VAR)

    with Session(db.engine) as session:
        existing_provisioned = session.exec(
            select(MappingRule).where(
                MappingRule.tenant_id == tenant_id,
                MappingRule.is_provisioned == True,  # noqa: E712
            )
        ).all()

        if not mappings_dir:
            if existing_provisioned:
                logger.info(
                    "KEEP_MAPPINGS_DIRECTORY unset; deprovisioning %d existing rule(s)",
                    len(existing_provisioned),
                )
                for rule in existing_provisioned:
                    _delete_rule(session, rule)
                session.commit()
            else:
                logger.info("No mapping rules to provision and none currently provisioned")
            return

        if not os.path.isdir(mappings_dir):
            raise FileNotFoundError(
                f"KEEP_MAPPINGS_DIRECTORY '{mappings_dir}' does not exist or is not a directory"
            )

        manifest_paths = _collect_manifest_paths(mappings_dir)
        logger.info(
            "Provisioning %d mapping manifest(s) from %s", len(manifest_paths), mappings_dir
        )

        # Deprovision rules whose source file is missing or outside the directory
        manifest_paths_set = set(manifest_paths)
        for rule in existing_provisioned:
            if (
                rule.provisioned_file is None
                or not os.path.exists(rule.provisioned_file)
                or rule.provisioned_file not in manifest_paths_set
            ):
                logger.info(
                    "Deprovisioning mapping rule '%s' (file %s no longer present)",
                    rule.name,
                    rule.provisioned_file,
                )
                _delete_rule(session, rule)
        session.commit()

        # Provision (create or update) each manifest. Commit per-manifest so a
        # failure of manifest N does not roll back manifests 1..N-1.
        for path in manifest_paths:
            try:
                _provision_one(session, tenant_id, path)
                session.commit()
            except Exception:
                logger.exception("Failed to provision mapping rule from %s", path)
                session.rollback()


def _collect_manifest_paths(mappings_dir: str) -> list[str]:
    """Return sorted absolute paths of YAML manifests in the directory.

    Paths are normalized via os.path.abspath so set-membership comparison
    against MappingRule.provisioned_file (also stored as abspath) stays stable
    across runs even if cwd or KEEP_MAPPINGS_DIRECTORY shape (relative vs
    absolute) changes between restarts.
    """
    abs_dir = os.path.abspath(mappings_dir)
    paths = []
    for filename in sorted(os.listdir(abs_dir)):
        if filename.endswith((".yaml", ".yml")):
            paths.append(os.path.join(abs_dir, filename))
        else:
            logger.info("Skipping non-YAML file %s in mappings directory", filename)
    return paths


def _provision_one(session: Session, tenant_id: str, manifest_path: str) -> None:
    """Provision a single mapping rule from a YAML manifest file.

    Looks up an existing rule by name (across all rules, regardless of
    `is_provisioned`). If found, updates it and marks it provisioned. Otherwise
    creates a new provisioned rule.
    """
    with open(manifest_path, "r", encoding="utf-8") as fh:
        raw = cyaml.safe_load(fh.read())

    if not isinstance(raw, dict):
        raise ValueError(
            f"Manifest {manifest_path} must be a YAML mapping (got {type(raw).__name__})"
        )

    # Validate against the same DTO used by the REST POST endpoint
    dto = MappingRuleDtoIn(**raw)

    existing = session.exec(
        select(MappingRule).where(
            MappingRule.tenant_id == tenant_id,
            MappingRule.name == dto.name,
        )
    ).first()

    now = datetime.datetime.now(tz=datetime.timezone.utc)

    if existing is not None:
        logger.info(
            "Adopting mapping rule '%s' from %s (provisioned=%s -> True)",
            dto.name,
            manifest_path,
            existing.is_provisioned,
        )
        existing.name = dto.name
        existing.description = dto.description
        existing.file_name = dto.file_name
        existing.priority = dto.priority
        existing.matchers = dto.matchers
        existing.type = dto.type
        existing.is_multi_level = dto.is_multi_level
        existing.new_property_name = dto.new_property_name
        existing.prefix_to_remove = dto.prefix_to_remove
        existing.rows = dto.rows
        # Fields not present in MappingRuleDtoIn are reset to model defaults
        # — the manifest is the source of truth, so a UI rule that was e.g.
        # disabled via the UI should NOT remain disabled after adoption.
        existing.disabled = False
        existing.override = True
        existing.condition = None
        existing.is_provisioned = True
        existing.provisioned_file = manifest_path
        existing.updated_by = SYSTEM_ACTOR
        existing.last_updated_at = now
        # SQLAlchemy auto-tracks attribute mutations on attached instances;
        # no explicit session.add() needed for the existing-rule branch.
        return

    logger.info("Provisioning new mapping rule '%s' from %s", dto.name, manifest_path)
    rule = MappingRule(
        tenant_id=tenant_id,
        name=dto.name,
        description=dto.description,
        file_name=dto.file_name,
        priority=dto.priority,
        matchers=dto.matchers,
        type=dto.type,
        is_multi_level=dto.is_multi_level,
        new_property_name=dto.new_property_name,
        prefix_to_remove=dto.prefix_to_remove,
        rows=dto.rows,
        is_provisioned=True,
        provisioned_file=manifest_path,
        created_by=SYSTEM_ACTOR,
        created_at=now,
        last_updated_at=now,
    )
    session.add(rule)
    # Flush so a subsequent same-name manifest in the same batch sees this
    # row via lookup-by-name (matters when sessions disable autoflush, e.g.
    # in some test fixtures).
    session.flush()


def _delete_rule(session: Session, rule: MappingRule) -> None:
    """Delete a mapping rule from the DB. Caller is responsible for committing."""
    session.delete(rule)
