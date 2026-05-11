def build_scheduler(optimizer, cfg: dict):
    try:
        import torch
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("PyTorch is required for schedulers") from exc

    name = cfg.get("scheduler", "none").lower()
    if name == "cosine":
        return torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=cfg.get("epochs", 1))
    return None
