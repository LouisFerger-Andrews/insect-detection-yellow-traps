def build_optimizer(params, cfg: dict):
    try:
        import torch
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("PyTorch is required for optimizers") from exc

    name = cfg.get("optimizer", "adamw").lower()
    lr = cfg.get("lr", 1e-4)
    if name == "adamw":
        return torch.optim.AdamW(params, lr=lr)
    if name == "sgd":
        return torch.optim.SGD(params, lr=lr, momentum=0.9)
    raise ValueError(f"Unknown optimizer: {name}")
