from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import selectinload
from sqlmodel import Session

from keep.api.core.db import (
    engine,
    get_previous_execution_id,
    delete_workflow,
    delete_workflow_by_provisioned_file,
    get_workflow_by_id,
    get_workflow_execution,
    get_workflow_execution_with_logs,
    create_workflow_execution,
    get_interval_workflows,
    add_workflow,
)
from keep.api.models.db.workflow import (
    Workflow,
    WorkflowExecution,
    WorkflowExecutionLog,
    WorkflowVersion,
)
from keep.workflowmanager.dal.exceptions import ConflictError
from keep.workflowmanager.dal.models.workflowstatsdalmodel import WorkflowStatsDalModel
from keep.workflowmanager.dal.sql.workflows import (
    get_workflows_with_last_executions_v2,
)

from keep.workflowmanager.dal.sql.mappers import (
    workflow_from_db_to_dto,
    workflow_execution_from_db_to_dto,
    workflow_execution_log_from_db_to_dto,
    workflow_execution_from_dto_to_db_partial,
    workflow_version_from_db_to_dto,
)
from keep.workflowmanager.dal.abstractworkflowrepository import WorkflowRepository
from keep.workflowmanager.dal.models.workflowdalmodel import (
    WorkflowDalModel,
    WorkflowVersionDalModel,
    WorkflowWithLastExecutionsDalModel,
    WorkflowStatus,
)
from keep.workflowmanager.dal.models.workflowexecutiondalmodel import (
    WorkflowExecutionDalModel,
)
from keep.workflowmanager.dal.models.workflowexecutionlogdalmodel import (
    WorkflowExecutioLogDalModel,
)
from sqlalchemy.exc import NoResultFound, IntegrityError

class SqlWorkflowRepository(WorkflowRepository):

    # region Workflow
    def add_workflow(
        self,
        workflow: WorkflowDalModel,
    ) -> WorkflowDalModel:
        db_workflow = add_workflow(
            id=workflow.id,
            name=workflow.name,
            tenant_id=workflow.tenant_id,
            description=workflow.description,
            created_by=workflow.created_by,
            interval=workflow.interval,
            workflow_raw=workflow.workflow_raw,
            is_disabled=workflow.is_disabled,
            updated_by=workflow.updated_by,
            provisioned=workflow.provisioned,
            provisioned_file=workflow.provisioned_file,
            is_test=workflow.is_test,
        )
        return workflow_from_db_to_dto(db_workflow)

    def update_workflow(self, workflow: WorkflowDalModel):
        workflow_patch = {}

        for key, value in workflow.dict(exclude_unset=True).items():
            if hasattr(Workflow, key):
                workflow_patch[key] = value

        with Session(engine) as session:
            stmt = (
                update(Workflow)
                .where(Workflow.id == workflow.id)
                .values(
                    **workflow_patch,
                )  # only update fields that are explicitly set in model
            )
            session.exec(stmt)
            session.commit()

    def delete_workflow(self, tenant_id, workflow_id):
        delete_workflow(tenant_id=tenant_id, workflow_id=workflow_id)

    def delete_workflow_by_provisioned_file(self, tenant_id, provisioned_file):
        delete_workflow_by_provisioned_file(
            tenant_id=tenant_id, provisioned_file=provisioned_file
        )

    def get_all_interval_workflows(self) -> List[WorkflowDalModel]:
        return [
            workflow_from_db_to_dto(db_workflow)
            for db_workflow in get_interval_workflows()
        ]

    def get_workflow_by_id(
        self, tenant_id: str, workflow_id: str
    ) -> WorkflowDalModel | None:
        db_workflow = get_workflow_by_id(tenant_id=tenant_id, workflow_id=workflow_id)

        if db_workflow is not None:
            return workflow_from_db_to_dto(db_workflow)

        return None

    def get_workflow_stats(
        self,
        tenant_id: str,
        workflow_id: str,
        time_delta: timedelta = None,
        triggers: List[str] | None = None,
        statuses: List[str] | None = None,
    ) -> WorkflowStatsDalModel | None:
        with Session(engine) as session:
            status_count_query = self._compose_base_workflow_executions_query(
                selects=[WorkflowExecution.status, func.count().label("count")],
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                is_test_run=False,
                time_delta=time_delta,
                triggers=triggers,
                statuses=statuses,
            ).group_by(WorkflowExecution.status)
            status_counts = session.exec(status_count_query).all()
            statusGroupbyMap = {status: count for status, count in status_counts}
            pass_count = statusGroupbyMap.get("success", 0)
            fail_count = statusGroupbyMap.get("error", 0) + statusGroupbyMap.get(
                "timeout", 0
            )
            avg_duration_query = self._compose_base_workflow_executions_query(
                selects=[func.avg(WorkflowExecution.execution_time)],
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                is_test_run=False,
                time_delta=time_delta,
                triggers=triggers,
                statuses=statuses,
            )
            avg_duration = session.exec(avg_duration_query).one()[0]

            return WorkflowStatsDalModel(
                pass_count=pass_count or 0,
                fail_count=fail_count or 0,
                avg_duration=avg_duration or 0,
            )

    def get_workflows(
        self,
        tenant_id: str,
        name_filter: str | None = None,
        is_disabled_filter: bool = None,
        is_provisioned_filter: bool = None,
        provisioned_file_filter: str | None = None,
    ):
        with Session(engine) as session:
            query = (
                select(Workflow)
                .where(Workflow.tenant_id == tenant_id)
                .where(Workflow.is_deleted is False)
                .where(Workflow.is_test is False)
            )

            if name_filter:
                query = query.where(Workflow.name == name_filter)

            if is_disabled_filter is not None:
                query = query.where(Workflow.is_disabled == is_disabled_filter)

            if is_provisioned_filter is not None:
                query = query.where(Workflow.provisioned == is_provisioned_filter)

            if provisioned_file_filter:
                query = query.where(
                    Workflow.provisioned_file.like(f"%{provisioned_file_filter}%")
                )

            return [
                workflow_from_db_to_dto(db_workflow)
                for db_workflow in session.exec(query).all()
            ]

    def get_workflows_with_last_executions(
        self,
        tenant_id: str,
        cel: str = "",
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        fetch_last_executions: int = 0,
    ) -> Tuple[list[WorkflowWithLastExecutionsDalModel], int]:
        return get_workflows_with_last_executions_v2(
            tenant_id=tenant_id,
            cel=cel,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir,
            fetch_last_executions=fetch_last_executions,
        )

    # endregion

    # region Workflow Version
    def add_workflow_version(self, workflow_version: WorkflowVersionDalModel):
        with Session(engine) as session:
            version = WorkflowVersion(
                workflow_id=workflow_version.workflow_id,
                revision=workflow_version.revision,
                workflow_raw=workflow_version.workflow_raw,
                updated_by=workflow_version.updated_by,
                comment=workflow_version.comment,
                is_valid=workflow_version.is_valid,
                is_current=workflow_version.is_current,
                updated_at=datetime.now(tz=timezone.utc),
            )
            session.add(version)
            session.commit()

    def get_workflow_version(
        self, tenant_id: str, workflow_id: str, revision: int
    ) -> WorkflowVersionDalModel | None:
        with Session(engine) as session:
            workflow_version_db = session.exec(
                select(WorkflowVersion)
                # starting from the 'workflow' table since it's smaller
                .select_from(Workflow)
                .where(Workflow.tenant_id == tenant_id)
                .where(Workflow.id == workflow_id)
                .where(Workflow.is_deleted == False)
                .where(Workflow.is_test == False)
                .join(WorkflowVersion, WorkflowVersion.workflow_id == Workflow.id)
                .where(WorkflowVersion.revision == revision)
            ).first()

        if workflow_version_db is None:
            return None

        return workflow_version_from_db_to_dto(workflow_version_db[0])

    def get_workflow_versions(
        self, tenant_id: str, workflow_id: str
    ) -> List[WorkflowVersionDalModel]:
        with Session(engine) as session:
            versions = session.exec(
                select(WorkflowVersion)
                # starting from the 'workflow' table since it's smaller
                .select_from(Workflow)
                .where(Workflow.tenant_id == tenant_id)
                .where(Workflow.id == workflow_id)
                .where(Workflow.is_deleted == False)
                .where(Workflow.is_test == False)
                .join(WorkflowVersion, WorkflowVersion.workflow_id == Workflow.id)
                .order_by(WorkflowVersion.revision.desc())
            ).all()

            return [
                workflow_version_from_db_to_dto(db_workflow_version[0])
                for db_workflow_version in versions
            ]

    # endregion

    # region Workflow Execution
    def add_workflow_execution(
        self,
        workflow_execution: WorkflowExecutionDalModel,
    ) -> str:
        try:
            return create_workflow_execution(
                execution_id=workflow_execution.id,
                workflow_id=workflow_execution.workflow_id,
                workflow_revision=workflow_execution.workflow_revision,
                tenant_id=workflow_execution.tenant_id,
                triggered_by=workflow_execution.triggered_by,
                execution_number=workflow_execution.execution_number,
                event_id=workflow_execution.event_id,
                event_type=workflow_execution.event_type,
                test_run=workflow_execution.is_test_run,
                status=workflow_execution.status,
            )
        except IntegrityError as e:
            raise ConflictError(
                f"Workflow execution for workflow {workflow_execution.workflow_id} with revision {workflow_execution.workflow_revision} already exists."
            ) from e

    def update_workflow_execution(self, workflow_execution: WorkflowExecutionDalModel):
        if workflow_execution.id is None:
            raise ValueError("Workflow execution ID must not be None")
        workflow_execution_patch = workflow_execution_from_dto_to_db_partial(
            workflow_execution_dto=workflow_execution
        )
        with Session(engine) as session:
            stmt = (
                update(WorkflowExecution)
                .where(WorkflowExecution.id == workflow_execution_patch.get("id"))
                .values(
                    **workflow_execution_patch
                )  # only update fields that are explicitly set in model
            )
            session.exec(stmt)
            session.commit()

    def get_last_completed_workflow_execution(
        self,
        workflow_id: str,
    ) -> WorkflowExecutionDalModel | None:
        with Session(engine) as session:
            query_result = session.exec(
                select(WorkflowExecution)
                .options(
                    selectinload(WorkflowExecution.workflow_to_alert_execution),
                    selectinload(WorkflowExecution.workflow_to_incident_execution),
                )
                .where(WorkflowExecution.workflow_id == workflow_id)
                .where(WorkflowExecution.is_test_run == False)
                .where(
                    WorkflowExecution.status.in_(
                        [
                            WorkflowStatus.SUCCESS.value,
                            WorkflowStatus.ERROR.value,
                            WorkflowStatus.PROVIDERS_NOT_CONFIGURED.value,
                        ]
                    )
                )
                .order_by(WorkflowExecution.execution_number.desc())
                .limit(1)
            ).first()
            db_workflow_execution = query_result[0] if query_result else None

            if db_workflow_execution is None:
                return None

            return workflow_execution_from_db_to_dto(db_workflow_execution)

    def get_workflow_execution(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ) -> WorkflowExecutionDalModel | None:
        try:
            db_workflow_execution = get_workflow_execution(
                tenant_id=tenant_id,
                workflow_execution_id=workflow_execution_id,
                is_test_run=is_test_run,
            )
            return workflow_execution_from_db_to_dto(db_workflow_execution)
        except NoResultFound:
            return None

    def get_workflow_executions(
        self,
        tenant_id: str | None,
        workflow_id: str | None,
        time_delta: timedelta = None,
        triggers: List[str] | None = None,
        statuses: List[str] | None = None,
        is_test_run: bool = False,
        limit: int = None,
        offset: int = None,
    ) -> Tuple[list[WorkflowExecutioLogDalModel], int]:
        with Session(engine) as session:
            is_test_run = is_test_run if is_test_run is not None else False
            limit = limit if limit is not None else 100
            offset = offset if offset is not None else 0

            total_count = session.exec(
                self._compose_base_workflow_executions_query(
                    selects=[func.count()],
                    tenant_id=tenant_id,
                    workflow_id=workflow_id,
                    is_test_run=is_test_run,
                    time_delta=time_delta,
                    triggers=triggers,
                    statuses=statuses,
                )
            ).one()[0]
            data_query = (
                self._compose_base_workflow_executions_query(
                    selects=[WorkflowExecution],
                    tenant_id=tenant_id,
                    workflow_id=workflow_id,
                    is_test_run=is_test_run,
                    time_delta=time_delta,
                    triggers=triggers,
                    statuses=statuses,
                )
                .order_by(WorkflowExecution.started.desc())
                .limit(limit)
                .offset(offset)
            )
            db_workflow_executions = session.exec(data_query).all()

            return [
                workflow_execution_from_db_to_dto(item[0])
                for item in db_workflow_executions
            ], total_count

    def get_previous_workflow_execution(
        self, tenant_id: str, workflow_id: str, workflow_execution_id: str
    ) -> WorkflowExecutioLogDalModel | None:
        db_workflow_execution = get_previous_execution_id(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            workflow_execution_id=workflow_execution_id,
        )

        if db_workflow_execution is None:
            return None

        return workflow_execution_log_from_db_to_dto(db_workflow_execution)

    def get_workflow_execution_with_logs(
        self,
        tenant_id: str,
        workflow_execution_id: str,
        is_test_run: bool | None = None,
    ) -> tuple[WorkflowExecutionDalModel, List[WorkflowExecutioLogDalModel]] | None:
        try:
            db_workflow_execution, db_workflow_execution_logs = (
                get_workflow_execution_with_logs(
                    tenant_id=tenant_id,
                    workflow_execution_id=workflow_execution_id,
                    is_test_run=is_test_run,
                )
            )
        except NoResultFound:
            return None

        mapped_execution_logs = [
            workflow_execution_log_from_db_to_dto(item)
            for item in db_workflow_execution_logs
        ]

        return (
            workflow_execution_from_db_to_dto(db_workflow_execution),
            mapped_execution_logs,
        )

    def get_workflow_execution_by_execution_number(
        self, workflow_id: str, execution_number: int
    ) -> WorkflowExecutionDalModel | None:
        with Session(engine) as session:
            query_result = session.exec(
                select(WorkflowExecution)
                .where(WorkflowExecution.workflow_id == workflow_id)
                .where(WorkflowExecution.execution_number == execution_number)
            ).first()
            db_workflow_execution = query_result[0] if query_result else None

            if db_workflow_execution is None:
                return None

            return workflow_execution_from_db_to_dto(db_workflow_execution)
    # endregion

    def _compose_base_workflow_executions_query(
        self,
        selects,
        tenant_id: str | None,
        workflow_id: str | None,
        is_test_run: bool = False,
        time_delta: timedelta = None,
        triggers: List[str] | None = None,
        statuses: List[str] | None = None,
    ):
        query = (
            select(*selects)
            .filter(
                WorkflowExecution.is_test_run == is_test_run,
            )
            .select_from(WorkflowExecution)
        )

        if tenant_id is not None:
            query = query.filter(WorkflowExecution.tenant_id == tenant_id)

        if workflow_id is not None:
            query = query.filter(WorkflowExecution.workflow_id == workflow_id)

        if time_delta is not None:
            query = query.filter(
                WorkflowExecution.started >= datetime.now(timezone.utc) - time_delta
            )

        if triggers is not None:
            conditions = [
                WorkflowExecution.triggered_by.like(f"{trig}%") for trig in triggers
            ]
            query = query.filter(or_(*conditions))

        if statuses is not None:
            query = query.filter(WorkflowExecution.status.in_(statuses))
        return query

    # region Workflow Execution Log
    def add_workflow_execution_logs(
        self, workflow_execution_log: list[WorkflowExecutioLogDalModel]
    ):
        db_log_entries = [
            WorkflowExecutionLog(**item.dict()) for item in workflow_execution_log
        ]
        with Session(engine) as session:
            session.add_all(db_log_entries)
            session.commit()

    # endregion
