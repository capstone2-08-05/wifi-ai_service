MATERIAL_LOSS_DB = {
    "concrete": 12.0,
    "glass": 6.0,
    "drywall": 4.0,
    "wood": 5.0,
}


def get_material_loss(material: str) -> float:
    return MATERIAL_LOSS_DB.get(material, 0.0)
