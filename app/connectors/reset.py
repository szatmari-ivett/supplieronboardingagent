def reset_connector_state() -> None:
    from app.connectors import cloud, erp, procurement

    erp._erp_suppliers.clear()
    procurement._packages.clear()
    cloud._workflows.clear()
