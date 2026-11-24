"""
fsd_table.py — Caractéristiques des réacteurs FSD et des boosters FSD gardiens, pour le calcul de la
portée de saut et le tracé de route de Spansh (module/externe/spansh.py).

Source : EDCD/coriolis-data (modules/standard/frame_shift_drive.json et
modules/internal/guardian_fsd_booster.json, relus le 24/11/2026). Vérifié sur les journaux du
commandant : portée = masse optimale / (masse à vide + carburant d'un saut)
                      × (carburant d'un saut / multiplicateur) ^ (1 / puissance) + booster
redonne la MaxJumpRange de ses Loadout.

FSD[objet en minuscules] = (masse optimale t, puissance, multiplicateur, carburant max d'un saut t)
"""

FSD = {
    "int_hyperdrive_overcharge_size2_class1": (60, 2.0, 0.008, 0.6),
    "int_hyperdrive_overcharge_size2_class2": (90, 2.0, 0.012, 0.9),
    "int_hyperdrive_overcharge_size2_class3": (90, 2.0, 0.012, 0.9),
    "int_hyperdrive_overcharge_size2_class4": (90, 2.0, 0.012, 0.9),
    "int_hyperdrive_overcharge_size2_class5": (100, 2.0, 0.013, 1),
    "int_hyperdrive_overcharge_size3_class1": (100, 2.15, 0.008, 1.2),
    "int_hyperdrive_overcharge_size3_class2": (150, 2.15, 0.012, 1.8),
    "int_hyperdrive_overcharge_size3_class3": (150, 2.15, 0.012, 1.8),
    "int_hyperdrive_overcharge_size3_class4": (150, 2.15, 0.012, 1.8),
    "int_hyperdrive_overcharge_size3_class5": (167, 2.15, 0.013, 1.9),
    "int_hyperdrive_overcharge_size4_class1": (350, 2.3, 0.008, 2),
    "int_hyperdrive_overcharge_size4_class2": (525, 2.3, 0.012, 3),
    "int_hyperdrive_overcharge_size4_class3": (525, 2.3, 0.012, 3),
    "int_hyperdrive_overcharge_size4_class4": (525, 2.3, 0.012, 3),
    "int_hyperdrive_overcharge_size4_class5": (585, 2.3, 0.013, 3.2),
    "int_hyperdrive_overcharge_size5_class1": (700, 2.45, 0.008, 3.3),
    "int_hyperdrive_overcharge_size5_class2": (1050, 2.45, 0.012, 5),
    "int_hyperdrive_overcharge_size5_class3": (1050, 2.45, 0.012, 5),
    "int_hyperdrive_overcharge_size5_class4": (1050, 2.45, 0.012, 5),
    "int_hyperdrive_overcharge_size5_class5": (1175, 2.45, 0.013, 5.2),
    "int_hyperdrive_overcharge_size6_class1": (1200, 2.6, 0.008, 5.3),
    "int_hyperdrive_overcharge_size6_class2": (1800, 2.6, 0.012, 8),
    "int_hyperdrive_overcharge_size6_class3": (1800, 2.6, 0.012, 8),
    "int_hyperdrive_overcharge_size6_class4": (1800, 2.6, 0.012, 8),
    "int_hyperdrive_overcharge_size6_class5": (2000, 2.6, 0.013, 8.3),
    "int_hyperdrive_overcharge_size7_class1": (1800, 2.75, 0.008, 8.5),
    "int_hyperdrive_overcharge_size7_class2": (2700, 2.75, 0.012, 12.8),
    "int_hyperdrive_overcharge_size7_class3": (2700, 2.75, 0.012, 12.8),
    "int_hyperdrive_overcharge_size7_class4": (2700, 2.75, 0.012, 12.8),
    "int_hyperdrive_overcharge_size7_class5": (3000, 2.75, 0.013, 13.1),
    "int_hyperdrive_overcharge_size8_class1": (2800, 2.9, 0.008, 13.6),
    "int_hyperdrive_overcharge_size8_class2": (4200, 2.9, 0.012, 20.4),
    "int_hyperdrive_overcharge_size8_class3": (4200, 2.9, 0.012, 20.4),
    "int_hyperdrive_overcharge_size8_class4": (4200, 2.9, 0.012, 20.4),
    "int_hyperdrive_overcharge_size8_class5": (4670, 2.9, 0.013, 20.7),
    "int_hyperdrive_overcharge_size8_class5_overchargebooster_mkii": (4670, 2.5025, 0.011, 6.8),
    "int_hyperdrive_size2_class1": (48, 2, 0.011, 0.6),
    "int_hyperdrive_size2_class2": (54, 2, 0.01, 0.6),
    "int_hyperdrive_size2_class3": (60, 2, 0.008, 0.6),
    "int_hyperdrive_size2_class4": (75, 2, 0.01, 0.8),
    "int_hyperdrive_size2_class5": (90, 2, 0.012, 0.9),
    "int_hyperdrive_size3_class1": (80, 2.15, 0.011, 1.2),
    "int_hyperdrive_size3_class2": (90, 2.15, 0.01, 1.2),
    "int_hyperdrive_size3_class3": (100, 2.15, 0.008, 1.2),
    "int_hyperdrive_size3_class4": (125, 2.15, 0.01, 1.5),
    "int_hyperdrive_size3_class5": (150, 2.15, 0.012, 1.8),
    "int_hyperdrive_size4_class1": (280, 2.3, 0.011, 2),
    "int_hyperdrive_size4_class2": (315, 2.3, 0.01, 2),
    "int_hyperdrive_size4_class3": (350, 2.3, 0.008, 2),
    "int_hyperdrive_size4_class4": (437.5, 2.3, 0.01, 2.5),
    "int_hyperdrive_size4_class5": (525, 2.3, 0.012, 3),
    "int_hyperdrive_size5_class1": (560, 2.45, 0.011, 3.3),
    "int_hyperdrive_size5_class2": (630, 2.45, 0.01, 3.3),
    "int_hyperdrive_size5_class3": (700, 2.45, 0.008, 3.3),
    "int_hyperdrive_size5_class4": (875, 2.45, 0.01, 4.1),
    "int_hyperdrive_size5_class5": (1050, 2.45, 0.012, 5),
    "int_hyperdrive_size6_class1": (960, 2.6, 0.011, 5.3),
    "int_hyperdrive_size6_class2": (1080, 2.6, 0.01, 5.3),
    "int_hyperdrive_size6_class3": (1200, 2.6, 0.008, 5.3),
    "int_hyperdrive_size6_class4": (1500, 2.6, 0.01, 6.6),
    "int_hyperdrive_size6_class5": (1800, 2.6, 0.012, 8),
    "int_hyperdrive_size7_class1": (1440, 2.75, 0.011, 8.5),
    "int_hyperdrive_size7_class2": (1620, 2.75, 0.01, 8.5),
    "int_hyperdrive_size7_class3": (1800, 2.75, 0.008, 8.5),
    "int_hyperdrive_size7_class4": (2250, 2.75, 0.01, 10.6),
    "int_hyperdrive_size7_class5": (2700, 2.75, 0.012, 12.8),
}

# Booster FSD gardien : années-lumière ajoutées à la portée
BOOSTERS = {
    "int_guardianfsdbooster_size1": 4,
    "int_guardianfsdbooster_size2": 6,
    "int_guardianfsdbooster_size3": 7.75,
    "int_guardianfsdbooster_size4": 9.25,
    "int_guardianfsdbooster_size5": 10.5,
}
