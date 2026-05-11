from typing import Any, Dict


class Evaluator:
    def evaluate(self, model: Any, dataloader) -> Dict[str, Any]:
        raise NotImplementedError("Implement evaluation loop for your task")

    def report(self, metrics: Dict[str, Any], out_path: str | None = None) -> None:
        if out_path is None:
            print(metrics)
            return
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(str(metrics))
