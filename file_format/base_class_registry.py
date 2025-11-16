from typing import Optional


class BaseService:
    """Base class that auto-registers subclasses"""

    _registry: dict[str, type] = {}

    def __init_subclass__(cls, service_name: Optional[str] = None, **kwargs):
        super().__init_subclass__(**kwargs)
        name = service_name or cls.__name__.lower()
        cls._registry[name] = cls

    @classmethod
    def get_service(cls, name: str) -> Optional[type]:
        return cls._registry.get(name)

    @classmethod
    def list_services(cls):
        return list(cls._registry.keys())

# Auto-registration happens on class definition


class EmailService(BaseService, service_name="email"):
    def send(self, message):
        return f"Sending email: {message}"


class SMSService(BaseService, service_name="sms"):
    def send(self, message):
        return f"Sending SMS: {message}"


# Usage
print(BaseService.list_services())  # ['email', 'sms']
service_class = BaseService.get_service('email')
if service_class:
    service = service_class()
    print(service.send("Hello"))  # Sending email: Hello
