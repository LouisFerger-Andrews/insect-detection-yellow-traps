from typing import Any, Dict


class Trainer:
    def __init__(self, model: Any):
        self.model = model

    def fit(self, train_loader, val_loader=None) -> Dict[str, Any]:
        return self.model.train(train_loader, val_loader)
