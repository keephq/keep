import enum
from typing import Any
import celpy.celparser
from lark import Token, Tree, Visitor
import lark
from sqlalchemy.orm import Query
import celpy
from typing import List, cast

from keep.api.core.cel_to_sql.cel_ast_converter import CelToAstConverter
from keep.api.core.cel_to_sql.sql_providers.sqlite import CelToSqliteProvider

instance = CelToSqliteProvider()

sql = instance.convert_to_sql_str("status == 'firing' || status == 'critical'", 'SELECT * FROM alert')

print('')