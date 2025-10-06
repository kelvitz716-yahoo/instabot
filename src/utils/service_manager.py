"""Service Manager for dependency injection and lifecycle management"""
from typing import Dict, Any, Optional, Type, TypeVar

T = TypeVar('T')

class ServiceManager:
    """
    Manages service instances and dependencies.
    Provides dependency injection and singleton management.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ServiceManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self):
        if self._initialized:
            return
            
        self._services: Dict[str, Any] = {}
        self._initialized = True
        
    def register(self, service_class: Type[T], instance: Optional[T] = None) -> None:
        """Register a service class or instance"""
        service_name = service_class.__name__
        if instance:
            self._services[service_name] = instance
        else:
            self._services[service_name] = service_class()
            
    def get(self, service_class: Type[T]) -> T:
        """Get a service instance by its class"""
        service_name = service_class.__name__
        if service_name not in self._services:
            self._services[service_name] = service_class()
        return self._services[service_name]
        
    def clear(self) -> None:
        """Clear all registered services"""
        self._services.clear()

# Global service manager instance
service_manager = ServiceManager()