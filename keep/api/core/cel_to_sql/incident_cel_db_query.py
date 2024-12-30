import enum
from typing import Any
import celpy.celparser
from lark import Token, Tree, Visitor
import lark
from sqlalchemy.orm import Query
import celpy
from typing import List, cast

from sqlmodel import Session

from keep.api.core.cel_to_sql.cel_ast_converter import CelToAstConverter
from keep.api.core.cel_to_sql.sql_providers.sqlite import CelToSqliteProvider
import keep.api.core.db as db

# instance = CelToSqliteProvider()

# sql = instance.convert_to_sql_str("status == 'firing' || status == 'critical'", 'SELECT * FROM alert')




# print('')