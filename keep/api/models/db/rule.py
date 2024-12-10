from collections import defaultdict
from datetime import datetime
from enum import Enum
from itertools import chain
from typing import List, Dict
from uuid import UUID, uuid4

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import JSON, Column, Field, SQLModel

# Currently a rule_definition is a list of SQL expressions
# We use querybuilder for that

class ResolveOn(Enum):
    # the alert was triggered
    FIRST = "first_resolved"
    LAST = "last_resolved"
    ALL = "all_resolved"
    NEVER = "never"


class CreateIncidentOn(Enum):
    # the alert was triggered
    ANY = "any"
    ALL = "all"

# TODOs/Pitfalls down the road which we hopefully need to address in the future:
# 1. nested attibtues (event.foo.bar = 1)
# 2. scale - when event arrives, we need to check if the rule is applicable to the event
#            the naive approach is to iterate over all rules and check if the rule is applicable
#            which won't scale.
# 3. action - currently support create alert, down the road should support workflows
# 4. timeframe - should be per definition group
class Rule(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    name: str
    definition: dict = Field(sa_column=Column(JSON))  # sql / params
    definition_cel: str  # cel
    timeframe: int  # time in seconds
    timeunit: str = Field(default="seconds")
    created_by: str
    creation_time: datetime
    updated_by: str = None
    update_time: datetime = None
    # list of "group_by" attributes - when to break the rule into groups
    grouping_criteria: list = Field(sa_column=Column(JSON), default=[])
    # e.g.  The {{ labels.queue }} is more than third full on {{ num_of_alerts }} queue managers | {{ start_time }} || {{ last_update_time }}
    group_description: str = None
    # e.g. The {{ labels.queue }} is more than third full on {{ num_of_alerts }} queue managers
    item_description: str = None
    require_approve: bool = False
    resolve_on: str = ResolveOn.NEVER.value
    create_on: str = CreateIncidentOn.ANY.value
