from ..utils.derived_from_decomposer import decompose_derived_from


def test_single_ingredient_exact_match():
    analysis = {"N": 0.33}
    result = decompose_derived_from(analysis, ["Ammonium Nitrate"])
    assert result == [("Ammonium Nitrate", 1.0)]


def test_multiple_ingredients():
    analysis = {"N": 0.33, "K": 0.28, "P": 0.22}
    result = decompose_derived_from(
        analysis,
        ["Ammonium Nitrate", "Monopotassium Phosphate"],
    )
    # Ammonium Nitrate limited by N leaving K and P for the second ingredient
    assert result[0][0] == "Ammonium Nitrate"
    assert result[1][0] == "Monopotassium Phosphate"
    assert result[0][1] == 1.0
    assert result[1][1] > 0


def test_unknown_ingredient_ignored():
    analysis = {"N": 0.33}
    result = decompose_derived_from(analysis, ["Unknown", "Ammonium Nitrate"])
    assert result == [("Ammonium Nitrate", 1.0)]
