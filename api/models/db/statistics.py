from sqlmodel import Field, SQLModel


class PMIMatrix(SQLModel, table=True):
    tenant_id: str = Field(foreign_key="tenant.id")
    fingerprint_i: str = Field(primary_key=True)
    fingerprint_j: str = Field(primary_key=True)
    pmi: float
    