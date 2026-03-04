import enum

class UserRole(enum.Enum):
    ADMIN = 'admin'
    USER = 'user'
    MANAGER = 'manager'
    SUPERVISOR = 'supervisor'
    PLATFORM_ADMIN = 'platform_admin'
    AUDITOR = 'auditor'