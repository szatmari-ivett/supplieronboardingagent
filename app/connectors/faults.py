from app.config import settings


def is_fault_enabled(system: str) -> bool:
    mapping = {
        "erp": settings.fault_erp,
        "procurement": settings.fault_procurement,
        "cloud": settings.fault_cloud,
    }
    return mapping.get(system, False)
