from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class DiceLoss(nn.Module):
    def __init__(self, smooth: float = 1.0):
        super().__init__()
        self.smooth = smooth

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        probs = torch.sigmoid(logits)
        probs = probs.contiguous().view(probs.size(0), -1)
        targets = targets.contiguous().view(targets.size(0), -1)
        intersection = (probs * targets).sum(dim=1)
        denom = probs.sum(dim=1) + targets.sum(dim=1)
        dice = (2.0 * intersection + self.smooth) / (denom + self.smooth)
        return 1.0 - dice.mean()


class FocalLoss(nn.Module):
    def __init__(self, alpha: float = 0.25, gamma: float = 2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        bce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
        pt = torch.exp(-bce)
        focal = self.alpha * (1.0 - pt).pow(self.gamma) * bce
        return focal.mean()


class TverskyLoss(nn.Module):
    def __init__(self, alpha: float = 0.7, beta: float = 0.3, smooth: float = 1.0):
        super().__init__()
        self.alpha = alpha
        self.beta = beta
        self.smooth = smooth

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        probs = torch.sigmoid(logits)
        probs = probs.contiguous().view(probs.size(0), -1)
        targets = targets.contiguous().view(targets.size(0), -1)

        tp = (probs * targets).sum(dim=1)
        fp = (probs * (1.0 - targets)).sum(dim=1)
        fn = ((1.0 - probs) * targets).sum(dim=1)

        tversky = (tp + self.smooth) / (tp + self.alpha * fp + self.beta * fn + self.smooth)
        return 1.0 - tversky.mean()


class CombinedLoss(nn.Module):
    def __init__(self, parts: list[tuple[nn.Module, float]]):
        super().__init__()
        self.losses = nn.ModuleList([loss for loss, _ in parts])
        self.weights = [weight for _, weight in parts]

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        loss = torch.zeros((), device=logits.device)
        for criterion, weight in zip(self.losses, self.weights):
            loss = loss + weight * criterion(logits, targets)
        return loss


def build_loss(loss_cfg: dict) -> nn.Module:
    mode = loss_cfg.get("name", "bce").lower()

    if mode == "bce":
        return nn.BCEWithLogitsLoss()
    if mode == "bce_dice":
        bce_weight = float(loss_cfg.get("bce_weight", 0.5))
        dice_weight = float(loss_cfg.get("dice_weight", 0.5))
        return CombinedLoss(
            [
                (nn.BCEWithLogitsLoss(), bce_weight),
                (DiceLoss(smooth=float(loss_cfg.get("dice_smooth", 1.0))), dice_weight),
            ]
        )
    if mode == "focal_dice":
        focal_weight = float(loss_cfg.get("focal_weight", 0.5))
        dice_weight = float(loss_cfg.get("dice_weight", 0.5))
        return CombinedLoss(
            [
                (
                    FocalLoss(
                        alpha=float(loss_cfg.get("focal_alpha", 0.25)),
                        gamma=float(loss_cfg.get("focal_gamma", 2.0)),
                    ),
                    focal_weight,
                ),
                (DiceLoss(smooth=float(loss_cfg.get("dice_smooth", 1.0))), dice_weight),
            ]
        )
    if mode == "tversky":
        return TverskyLoss(
            alpha=float(loss_cfg.get("tversky_alpha", 0.7)),
            beta=float(loss_cfg.get("tversky_beta", 0.3)),
            smooth=float(loss_cfg.get("tversky_smooth", 1.0)),
        )
    if mode == "focal_tversky":
        focal_weight = float(loss_cfg.get("focal_weight", 0.4))
        tversky_weight = float(loss_cfg.get("tversky_weight", 0.6))
        return CombinedLoss(
            [
                (
                    FocalLoss(
                        alpha=float(loss_cfg.get("focal_alpha", 0.25)),
                        gamma=float(loss_cfg.get("focal_gamma", 2.0)),
                    ),
                    focal_weight,
                ),
                (
                    TverskyLoss(
                        alpha=float(loss_cfg.get("tversky_alpha", 0.7)),
                        beta=float(loss_cfg.get("tversky_beta", 0.3)),
                        smooth=float(loss_cfg.get("tversky_smooth", 1.0)),
                    ),
                    tversky_weight,
                ),
            ]
        )
    raise ValueError(f"Unknown loss.name: {mode}")