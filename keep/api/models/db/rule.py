from datetime import datetime
from uuid import UUID, uuid4

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
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id")
    name: str
    definition: dict = Field(sa_column=Column(JSON))  # sql / params
    definition_cel: str  # cel
    timeframe: int  # time in seconds
    created_by: str
    creation_time: datetime
    updated_by: str = None
    update_time: datetime = None
