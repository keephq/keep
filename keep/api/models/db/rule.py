from datetime import datetime
from uuid import uuid4

from sqlmodel import JSON, Column, Field, SQLModel

# Currently a rule_definition is a list of SQL expressions
# We use querybuilder for that


# TODOs/Pitfalls down the road which we hopefully need to address in the future:
# 1. nested attibtues (event.foo.bar = 1)
# 2. scale - when event arrives, we need to check if the rule is applicable to the event
#            the naive approach is to iterate over all rules and check if the rule is applicable
#            which won't scale.
# 3. action - currently support create alert, down the road should support workflows
# 4. timeframe - should be per definition group
class Rule(SQLModel, table=True):
    id: str = Field(
        default_factory=lambda: str(uuid4()), primary_key=True, max_length=36
    )
    tenant_id: str = Field(foreign_key="tenant.id", max_length=36)
    name: str
    definition: dict = Field(sa_column=Column(JSON))  # sql / params
    definition_cel: str  # cel
    timeframe: int  # time in seconds
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
