from custom_components.horticulture_assistant.utils.product_catalog import FertilizerProduct, ProductPackaging


def test_product_catalog_basic():
    pkg1 = ProductPackaging(volume=1.0, unit="L", distributor="A", price=10.0, sku="X")
    pkg2 = ProductPackaging(volume=5.0, unit="L", distributor="B", price=45.0, sku="Y")

    product = FertilizerProduct(
        name="Grow",
        manufacturer="FF",
        form="liquid",
        derived_from=["compost"],
        base_composition={"N": 3.0},
        density_kg_per_L=1.0,
        bio_based=True,
    )
    product.add_packaging(pkg1)
    product.add_packaging(pkg2)

    assert pkg1.cost_per_unit() == 10.0
    assert product.get_best_price_per_unit("L") == 9.0

    desc = product.describe()
    assert desc["name"] == "Grow"
    assert desc["best_price_per_unit"] is None  # default unit is kg
    assert len(desc["packaging_options"]) == 2
