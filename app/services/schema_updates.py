from sqlalchemy import inspect, text


_ITEM_COLUMNS = {
    "private_details": "TEXT",
    "serial_number": "VARCHAR(120)",
    "estimated_value": "NUMERIC(10, 2)",
    "additional_notes": "TEXT",
    "storage_info": "TEXT",
    "verification_question_1": "VARCHAR(180)",
    "verification_question_2": "VARCHAR(180)",
    "verification_question_3": "VARCHAR(180)",
    "recovery_token": "VARCHAR(64)",
    "share_exact_location": "BOOLEAN NOT NULL DEFAULT FALSE",
}

_TABLE_COLUMNS = {
    "item_matches": {"image_score": "FLOAT"},
    "reports": {"admin_note": "TEXT", "action_taken": "VARCHAR(32)"},
}


def add_missing_item_columns(engine):
    """Apply safe, additive schema updates for item, match, and moderation tables."""
    inspector = inspect(engine)
    if "items" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("items")}
    with engine.begin() as connection:
        quote_identifier = connection.dialect.identifier_preparer.quote
        items_table = quote_identifier("items")
        for name, sql_type in _ITEM_COLUMNS.items():
            if name not in existing:
                connection.execute(text(
                    f"ALTER TABLE {items_table} ADD COLUMN {quote_identifier(name)} {sql_type}"
                ))
        for table_name, columns in _TABLE_COLUMNS.items():
            if table_name not in inspector.get_table_names():
                continue
            existing_columns = {column["name"] for column in inspect(connection).get_columns(table_name)}
            for name, sql_type in columns.items():
                if name not in existing_columns:
                    quoted_table = quote_identifier(table_name)
                    connection.execute(text(
                        f"ALTER TABLE {quoted_table} ADD COLUMN {quote_identifier(name)} {sql_type}"
                    ))
        if engine.dialect.name in {"sqlite", "postgresql"}:
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_items_recovery_token ON items (recovery_token)"))
