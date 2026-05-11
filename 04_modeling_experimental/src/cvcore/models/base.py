from abc import ABC, abstractmethod
from typing import Any, Dict, List


class Model(ABC):
    @abstractmethod
    def train(self, train_loader, val_loader=None) -> Dict[str, Any]: ...

    @abstractmethod
    def predict(self, batch) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def save(self, path: str) -> None: ...

    @abstractmethod
    def load(self, path: str) -> "Model": ...
