# -*- coding: utf-8 -*-
"""
Recettes de cuisine Palworld -- source communautaire (switchbladegaming.com, pas le
DataTable brut du jeu comme le reste du dashboard) : a traiter avec un cran de confiance
en moins que les donnees Pals/travail, mais la seule source structuree trouvee pour les
recettes/ingredients/effets exacts.
"""

RECIPES = [
    # (nom, station, {ingredient: qty}, san, effet)
    ("Bread", "Campfire", {"Flour": 1}, 4, None),
    ("Broncherry Rib Roast", "Campfire", {"Broncherry Meat": 1}, 23, None),
    ("Fried Egg", "Campfire", {"Egg": 1}, 1, None),
    ("Grilled Chikipi", "Campfire", {"Chikipi Poultry": 1}, 11, None),
    ("Grilled Galeclaw", "Campfire", {"Galeclaw Poultry": 1}, 11, None),
    ("Herb Roasted Caprity", "Campfire", {"Caprity Meat": 1}, 11, None),
    ("Hot Milk", "Campfire", {"Milk": 1}, 1, None),
    ("Lamball Kebab", "Campfire", {"Lamball Mutton": 1}, 11, None),
    ("Mammorest Steak", "Campfire", {"Mammorest Meat": 1}, 23, None),
    ("Roast Reindrix", "Campfire", {"Reindrix Venison": 1}, 21, None),
    ("Roast Rushoar", "Campfire", {"Rushoar Pork": 1}, 11, None),

    ("Cake", "Cooking Pot", {"Flour": 2, "Honey": 2, "Milk": 7, "Egg": 8, "Red Berries": 8}, 8, "Elevage uniquement"),
    ("Chikipi Saute", "Cooking Pot", {"Chikipi Poultry": 1, "Red Berries": 2}, 12, "+30% vitesse de travail"),
    ("Grilled Lamball", "Cooking Pot", {"Lamball Mutton": 1}, 18, "+30% vitesse de travail, faim ralentie"),
    ("Herb Roasted Lamball", "Cooking Pot", {"Lamball Mutton": 1, "Red Berries": 2}, 11, "+10% defense"),
    ("Jam-filled Bun", "Cooking Pot", {"Flour": 1, "Red Berries": 2}, 6, None),
    ("Marinated Mushrooms", "Cooking Pot", {"Mushroom": 1, "Red Berries": 2}, 7, "+10% defense"),
    ("Omelet", "Cooking Pot", {"Tomato": 1, "Egg": 2}, 7, "+10% attaque"),
    ("Pancake", "Cooking Pot", {"Flour": 1, "Milk": 1}, 5, "sanite ralentie"),
    ("Reindrix Stew", "Cooking Pot", {"Reindrix Venison": 1, "Tomato": 2}, 17, "faim ralentie"),
    ("Salad", "Cooking Pot", {"Lettuce": 2, "Tomato": 2}, 11, "+30% vitesse de travail"),
    ("Stewed Galeclaw", "Cooking Pot", {"Galeclaw Poultry": 1, "Red Berries": 2}, 12, "sanite ralentie"),

    ("Carbonara", "Electric Kitchen", {"Flour": 1, "Egg": 2, "Milk": 2}, 16, "+20% defense"),
    ("Dumud Chowder", "Electric Kitchen", {"Raw Dumud": 1, "Lettuce": 2, "Tomato": 2}, 21, "+50% vitesse de travail, faim ralentie"),
    ("Eikthyrdeer Loco Moco", "Electric Kitchen", {"Eikthyrdeer Venison": 1, "Red Berries": 2, "Egg": 2}, 22, "+20% attaque"),
    ("Eikthyrdeer Stew", "Electric Kitchen", {"Eikthyrdeer Venison": 1, "Mushroom": 1, "Milk": 2}, 27, "+20% defense"),
    ("Fried Chikipi", "Electric Kitchen", {"Chikipi Poultry": 1, "Flour": 1, "Egg": 1, "High Quality Pal Oil": 1}, 14, "+30% vitesse de travail, sanite ralentie"),
    ("Mozzarina Cheeseburger", "Electric Kitchen", {"Mozzarina Meat": 1, "Flour": 1, "Tomato": 2, "Milk": 2}, 36, "+20% attaque, faim ralentie"),
    ("Mozzarina Hamburger", "Electric Kitchen", {"Mozzarina Meat": 1, "Flour": 1, "Lettuce": 2}, 20, "+50% vitesse de travail, sanite ralentie"),
    ("Pizza", "Electric Kitchen", {"Flour": 1, "Red Berries": 2, "Tomato": 2, "Milk": 2}, 23, "+30% vitesse de travail, faim ralentie"),
    ("Rushoar Hot Dog", "Electric Kitchen", {"Rushoar Pork": 1, "Flour": 1, "Lettuce": 2}, 18, "+20% defense"),

    ("Mammorest Curry", "Grand Four", {"Mammorest Meat": 1, "Onion": 2, "Carrot": 2, "Potato": 2, "Red Berries": 2}, 52, "qualite Epique"),

    # Verifiees directement sur paldb.cc (source primaire par plat, pas juste le guide
    # switchbladegaming.com) suite a une demande utilisateur de verification -- 2026-09.
    ("Minestrone", "Electric Kitchen", {"Tomato": 3, "Carrot": 2, "Onion": 2, "Potato": 1}, 18, "+40% vitesse de travail (10 min)"),
    ("Galeclaw Nikujaga", "Grand Four", {"Galeclaw Poultry": 1, "Onion": 2, "Carrot": 2, "Potato": 2}, 19, "+25% defense (10 min)"),
]

# Cultures de la ferme -> ingredient produit directement (mapping direct, pas d'ambiguite)
CROP_TO_INGREDIENT = {
    "FarmBlockV2_Berries": "Red Berries",
    "FarmBlockV2_tomato": "Tomato",
    "FarmBlockV2_Lettuce": "Lettuce",
    "FarmBlockV2_Potato": "Potato",
    "FarmBlockV2_wheet": "Flour",  # necessite aussi un Moulin (FlourMill) pour transformer le ble
    "FarmBlockV2_Onion": "Onion",
    "FarmBlockV2_Carrot": "Carrot",
}

# Batiments -> station de cuisine (noms exacts confirmes dans le jeu ; les stations
# intermediaires "Cooking Pot" et "Grand Four" n'ont pas ete observees dans cette
# sauvegarde -- noms internes non confirmes, donc non recherchees pour l'instant)
STATION_BUILDINGS = {
    "Campfire": ["CampFire"],
    "Electric Kitchen": ["ElectricKitchen"],
}
