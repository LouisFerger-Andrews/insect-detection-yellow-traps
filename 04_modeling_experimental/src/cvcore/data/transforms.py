from abc import ABC, abstractmethod
from typing import Dict, Any


class Transform(ABC):
    @abstractmethod
    def __call__(self, sample: Dict[str, Any]) -> Dict[str, Any]: ...
