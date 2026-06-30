"""数据库层模块 — 连接、表定义、数据仓库查询。

使用方法：
    from db import get_db, init_db, get_kpi_data, replace_rows
    from db import get_platform_data, get_org_kpi_data, get_product_structure
    from db import get_payment_period_structure
    from db import get_target_config, save_target_config

模块结构：
    db/connection.py   — DB_PATH, get_db()
    db/schema.py       — AGG_TABLES, init_db()
    db/repository.py   — replace_rows(), replace_rows_incremental(), clear_year_data()
    db/repositories/   — 各聚合表的查询函数
"""

# 基础设施
from db.connection import get_db, DB_PATH
from db.schema import init_db, AGG_TABLES
from db.repository import replace_rows, replace_rows_incremental, clear_year_data, clear_table_year_data

# 查询函数
from db.repositories.platform import get_platform_data
from db.repositories.kpi import get_kpi_data
from db.repositories.org import get_org_kpi_data
from db.repositories.payment import get_payment_period_structure
from db.repositories.product import (
    _split_csv,
    _query_product_structure_raw,
    get_jingdai_orgs,
    get_product_structure,
)
from db.repositories.target import (
    get_target_config,
    _flatten_target_payload,
    save_target_values,
    get_target_values,
    save_target_config,
)

__all__ = [
    # connection
    'get_db', 'DB_PATH',
    # schema
    'init_db', 'AGG_TABLES',
    # repository
    'replace_rows', 'replace_rows_incremental', 'clear_year_data', 'clear_table_year_data',
    # kpi
    'get_platform_data', 'get_kpi_data',
    # org
    'get_org_kpi_data',
    # payment
    'get_payment_period_structure',
    # product
    '_split_csv', '_query_product_structure_raw', 'get_jingdai_orgs', 'get_product_structure',
    # target
    'get_target_config', '_flatten_target_payload',
    'save_target_values', 'get_target_values', 'save_target_config',
]
