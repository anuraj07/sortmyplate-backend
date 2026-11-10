from typing import List, Tuple, Set
from app.domain.recipes import Recipe, Ingredient, CustomFinish

class RecipeService:
    def __init__(self):
        self._recipes: List[Recipe] = self._init_recipes()

    def _init_recipes(self) -> List[Recipe]:
        return [
            Recipe(
                id="rcp_mediterranean_farro_lentil",
                title="Mediterranean Farro & Beluga Lentil Power Bowl",
                description="Earthy black lentils and whole farro with sun-dried tomatoes, cucumber, and fresh herbs in a light herb vinaigrette.",
                meal_slots=["LUNCH", "DINNER"],
                diet_types=["omnivore", "vegetarian", "vegan", "pescatarian"],
                prep_time_minutes=25,
                difficulty="EASY",
                calories=480,
                protein_g=22.0,
                net_carbs_g=48.0,
                fat_g=14.0,
                fiber_g=14.0,
                saturated_fat_g=1.8,
                glycemic_load=8.5, # Very low GL
                base_allergens=[], # Farro can be swapped for quinoa for gluten-free
                base_ingredients=[
                    Ingredient(name="Beluga Black Lentils (cooked)", amount="120", unit="g", tags=["high_soluble_fiber", "iron_rich"]),
                    Ingredient(name="Whole Grain Farro (or Quinoa)", amount="100", unit="g", tags=["resistant_starch", "low_glycemic"]),
                    Ingredient(name="Persian Cucumbers & Cherry Tomatoes", amount="100", unit="g"),
                    Ingredient(name="Kalamata Olives (sliced)", amount="20", unit="g", tags=["monounsaturated_fat"]),
                    Ingredient(name="Extra Virgin Olive Oil & Herb Dressing", amount="15", unit="mL", tags=["polyphenol_rich"])
                ],
                prep_instructions=[
                    "Warm the cooked black lentils and farro together in a skillet for 2 minutes.",
                    "Toss with diced cucumbers, cherry tomatoes, and kalamata olives.",
                    "Drizzle with cold-pressed olive oil vinaigrette and add your personalized member toppings."
                ],
                custom_finishes=[
                    CustomFinish(
                        for_biomarker="FERRITIN",
                        name="Iron Bioavailability Boost",
                        ingredients=[
                            Ingredient(name="Wilted Baby Spinach", amount="60", unit="g", tags=["iron_rich"]),
                            Ingredient(name="Fresh Squeezed Lemon Juice", amount="15", unit="mL", tags=["ascorbic_acid_enhancer"])
                        ],
                        mechanism_benefit="Ascorbic acid (Vitamin C) reduces ferric iron to ferrous iron, increasing intestinal absorption by over 250%."
                    ),
                    CustomFinish(
                        for_biomarker="APOB",
                        name="Atherogenic Lipid Neutralizer",
                        ingredients=[
                            Ingredient(name="Sliced Fresh Haas Avocado", amount="50", unit="g", tags=["phytosterols"]),
                            Ingredient(name="Raw Pumpkin Seeds", amount="15", unit="g", tags=["magnesium", "plant_sterols"])
                        ],
                        mechanism_benefit="Plant sterols compete with cholesterol for micellar incorporation, supporting hepatic ApoB particle clearance."
                    ),
                    CustomFinish(
                        for_biomarker="HBA1C",
                        name="Glycemic Pacing Finisher",
                        ingredients=[
                            Ingredient(name="Ceylon Cinnamon & Crushed Walnuts", amount="15", unit="g", tags=["alpha_linolenic_acid", "insulin_sensitizer"])
                        ],
                        mechanism_benefit="Polyphenols in Ceylon cinnamon enhance GLUT4 transporter activity and slow gastric emptying."
                    ),
                    CustomFinish(
                        for_biomarker="HS_CRP",
                        name="Anti-Inflammatory Gold Drizzle",
                        ingredients=[
                            Ingredient(name="Cold-Pressed Turmeric & Black Pepper Infusion", amount="10", unit="mL", tags=["curcumin", "piperine"])
                        ],
                        mechanism_benefit="Curcumin downregulates NF-kB inflammatory cascades, significantly lowering circulating hs-CRP."
                    )
                ],
                is_low_saturated_fat=True,
                is_low_glycemic=True,
                is_high_soluble_fiber=True,
                is_rich_iron=True,
                is_high_omega3=True,
                is_anti_inflammatory=True,
                is_low_purine=True
            ),
            Recipe(
                id="rcp_wild_salmon_sweet_potato",
                title="Pan-Seared Wild Alaskan Salmon & Roasted Kabocha Squash",
                description="Crispy skin wild salmon over roasted low-GI squash cubes with wilted garlicky greens.",
                meal_slots=["DINNER"],
                diet_types=["omnivore", "pescatarian"],
                prep_time_minutes=30,
                difficulty="MEDIUM",
                calories=520,
                protein_g=36.0,
                net_carbs_g=32.0,
                fat_g=24.0,
                fiber_g=8.0,
                saturated_fat_g=3.1,
                glycemic_load=7.0,
                base_allergens=["fish"],
                base_ingredients=[
                    Ingredient(name="Wild Alaskan Sockeye Salmon", amount="150", unit="g", allergens=["fish"], tags=["epa_dha_omega3"]),
                    Ingredient(name="Roasted Kabocha / Sweet Potato Cubes", amount="120", unit="g", tags=["carotenoids", "low_glycemic"]),
                    Ingredient(name="Wilted Steamed Bok Choy", amount="80", unit="g", tags=["calcium", "polyphenols"])
                ],
                prep_instructions=[
                    "Roast squash cubes with olive oil at 200°C for 20 minutes.",
                    "Sear salmon in a hot stainless steel skillet 3-4 minutes per side until skin is crisp.",
                    "Plate with steamed bok choy and finish with individual seasonings."
                ],
                custom_finishes=[
                    CustomFinish(
                        for_biomarker="APOB",
                        name="Omega Purity Finish",
                        ingredients=[Ingredient(name="Toasted Chia Seed Dusting", amount="10", unit="g")],
                        mechanism_benefit="Amplifies EPA/DHA ratio to inhibit hepatic triglyceride-rich VLDL assembly."
                    ),
                    CustomFinish(
                        for_biomarker="FERRITIN",
                        name="Citrus Sesame Glaze",
                        ingredients=[Ingredient(name="Orange-Ginger Dressing", amount="15", unit="mL")],
                        mechanism_benefit="Citrus flavonoids and citric acid synergize with fish protein factor to boost iron retention."
                    )
                ],
                is_low_saturated_fat=True,
                is_low_glycemic=True,
                is_high_soluble_fiber=False,
                is_rich_iron=True,
                is_high_omega3=True,
                is_anti_inflammatory=True,
                is_low_purine=False # Salmon has moderate purines
            ),
            Recipe(
                id="rcp_golden_chickpea_coconut_curry",
                title="Golden Coconut Turmeric Chickpea Stew with Riced Greens",
                description="Creamy, aromatic coconut stew loaded with chickpeas, ginger, baby kale, and warm Indian digestive spices.",
                meal_slots=["LUNCH", "DINNER"],
                diet_types=["omnivore", "vegetarian", "vegan", "pescatarian"],
                prep_time_minutes=25,
                difficulty="EASY",
                calories=440,
                protein_g=18.0,
                net_carbs_g=38.0,
                fat_g=18.0,
                fiber_g=12.0,
                saturated_fat_g=3.8,
                glycemic_load=6.8,
                base_allergens=[],
                base_ingredients=[
                    Ingredient(name="Organic Chickpeas (rinsed)", amount="130", unit="g", tags=["soluble_fiber", "resistant_starch"]),
                    Ingredient(name="Light Coconut Milk & Turmeric Broth", amount="100", unit="mL", tags=["anti_inflammatory"]),
                    Ingredient(name="Tuscan Baby Kale", amount="60", unit="g", tags=["iron_rich", "lutein"]),
                    Ingredient(name="Steamed Cauliflower & Brown Basmati Base", amount="100", unit="g", tags=["low_glycemic"])
                ],
                prep_instructions=[
                    "Simmer chickpeas and light coconut milk with grated ginger and turmeric for 10 minutes.",
                    "Fold in baby kale until tender.",
                    "Serve over steamed cauliflower-rice blend."
                ],
                custom_finishes=[
                    CustomFinish(
                        for_biomarker="FERRITIN",
                        name="Lime & Chopped Coriander",
                        ingredients=[Ingredient(name="Fresh Lime Juice", amount="15", unit="mL")],
                        mechanism_benefit="Ascorbic acid from lime enhances absorption of non-heme iron in chickpeas."
                    ),
                    CustomFinish(
                        for_biomarker="HBA1C",
                        name="Fenugreek & Cumin Seed Tempering",
                        ingredients=[Ingredient(name="Toasted Fenugreek Seeds", amount="5", unit="g")],
                        mechanism_benefit="4-hydroxyisoleucine in fenugreek stimulates glucose-dependent insulin secretion."
                    )
                ],
                is_low_saturated_fat=True,
                is_low_glycemic=True,
                is_high_soluble_fiber=True,
                is_rich_iron=True,
                is_high_omega3=False,
                is_anti_inflammatory=True,
                is_low_purine=True
            )
        ]

    def get_all_recipes(self) -> List[Recipe]:
        return self._recipes

    def find_eligible_recipes(
        self,
        banned_allergens: Set[str],
        required_diet_types: Set[str],
        meal_slot: str,
        max_prep_time: int
    ) -> List[Recipe]:
        eligible = []
        banned_clean = {a.lower().strip() for a in banned_allergens}

        for recipe in self._recipes:
            # 1. Hard check: Allergens
            recipe_allergens = {a.lower().strip() for a in recipe.base_allergens}
            if banned_clean.intersection(recipe_allergens):
                continue # Contains banned allergen, strictly eliminate

            # 2. Hard check: Dietary preferences (vegan, vegetarian, pescatarian, omnivore)
            # If all required diets must be satisfied by the shared base
            if required_diet_types:
                compatible = all(diet in recipe.diet_types for diet in required_diet_types)
                if not compatible:
                    continue

            # 3. Meal slot compatibility
            if meal_slot.upper() not in recipe.meal_slots:
                continue

            # 4. Prep time
            if recipe.prep_time_minutes > max_prep_time:
                continue

            eligible.append(recipe)

        return eligible

recipe_service = RecipeService()
