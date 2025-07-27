import json, sys

TEMPLATE = {
    "schema_version": "v6.0.0",
    "products": [
        {
            "product_id": None,
            "label_name": None,
            "brand": None,
            "manufacturer": None,
            "product_line": None,
            "country_of_label": None,
            "languages_on_label": [],
            "ids": {
                "gtin_upc": None,
                "cas": None,
                "cipac": None,
                "epa_reg_no": None,
                "pmra_reg_no": None
            },
            "registration_numbers": {
                "WSDA": None,
                "CDFA": None,
                "EU_FPR": None,
                "others": []
            },
            "regulatory_details": {
                "us_fifra_category": None,
                "eu_pc_number": None,
                "uk_hse_number": None,
                "global_product_identifier": None,
                "statuses": {}
            },
            "certifications": [],
            "biostimulant_categories": [],
            "claims": None,
            "manufacturing_info": {
                "manufacturer_name": None,
                "sites": [],
                "batch_format": None,
                "typical_shelf_life_months": None
            },
            "quality_assurance": {
                "qc_parameters": {},
                "iso_certifications": [],
                "last_qc_date": None
            },
            "density_kg_l": None,
            "viscosity_cP": None,
            "ph_at_20c": None,
            "colour": None,
            "odour": None,
            "physicochem": {
                "solubility_g_l": None,
                "logKow": None,
                "vapour_pressure_Pa": None,
                "henry_constant_Pa_m3_mol": None,
                "melting_point_c": None
            },
            "particle_size_distribution": {},
            "crush_strength_N": None,
            "hygroscopicity_pct": None,
            "nutrients": {
                "N_total": None, "N_ammoniacal": None, "N_nitrate": None, "N_urea": None,
                "P": None, "K": None, "Ca": None, "Mg": None, "S": None,
                "B": None, "Cl": None, "Cu": None, "Fe": None, "Mn": None,
                "Mo": None, "Ni": None, "Zn": None, "Si": None, "Na": None
            },
            "nutrients_verified": False,
            "heavy_metals": {
                "As": {"value": None, "detected": False, "detection_limit": None},
                "Cd": {"value": None, "detected": False, "detection_limit": None},
                "Co": {"value": None, "detected": False, "detection_limit": None},
                "Hg": {"value": None, "detected": False, "detection_limit": None},
                "Mo": {"value": None, "detected": False, "detection_limit": None},
                "Ni": {"value": None, "detected": False, "detection_limit": None},
                "Pb": {"value": None, "detected": False, "detection_limit": None},
                "Se": {"value": None, "detected": False, "detection_limit": None},
                "Zn": {"value": None, "detected": False, "detection_limit": None}
            },
            "heavy_metals_verified": False,
            "organic_contaminants": {},
            "pesticide_actives": [],
            "pesticide_actives_verified": False,
            "inert_ingredients": [],
            "microbial_strains": [],
            "microbial_strains_verified": False,
            "derived_from_raw": "",
            "derived_from_translations": {},
            "verified_label": False,
            "endocrine_disruptor": False,
            "contains_nanomaterials": False,
            "toxicology": {
                "ld50_oral_mgkg_rat": None,
                "ld50_dermal_mgkg_rabbit": None,
                "lc50_inhalation_mg_l_rat": None,
                "skin_irritation": None,
                "eye_irritation": None,
                "sensitisation": None
            },
            "toxicology_refvals": {},
            "ecotox": {},
            "environmental_fate": {},
            "ghs": {
                "classification": None,
                "pictograms": [],
                "signal_word": None,
                "hazard_statements": []
            },
            "transport": {
                "un_number": None,
                "dot_class": None,
                "adr_class": None,
                "imdg_class": None,
                "iata_class": None
            },
            "whmis_pictograms": [],
            "clp_precautionary_statements": [],
            "ehs_profile": {
                "ppe_recommendations": None,
                "ppe_details": {
                    "body": None,
                    "hand": None,
                    "eye": None,
                    "respiratory": None
                },
                "spill_response": None,
                "disposal_instructions": None,
                "environmental_statements": None
            },
            "packaging": [
                {
                    "volume_l": 0,
                    "weight_kg": None,
                    "container_type": "",
                    "sku": None,
                    "upc": None,
                    "pallet_qty": None,
                    "un_packing_group": None,
                    "dot_spec": None,
                    "deposit_scheme": None,
                    "returnable": False,
                    "recycled_content_pct": None,
                    "recyclability_code": None,
                    "reuse_program": False
                }
            ],
            "storage_conditions": None,
            "shelf_life_months": None,
            "stability_data": {},
            "tank_mix_data": {},
            "chelate_forms": [],
            "release_characteristics": None,
            "microplastic_content_mgkg": None,
            "polymer_types": [],
            "target_uses": [],
            "mode_of_action_detail": {},
            "maximum_residue_limits": {},
            "trial_summaries": [],
            "sale_restrictions": [],
            "market_status": "active",
            "recall_notice_url": None,
            "recall_date": None,
            "source_label_url": "",
            "sds_url": "",
            "sds_version": None,
            "sds_issue_date": None,
            "tech_sheet_url": None,
            "label_pdf_sha256": None,
            "label_image_urls": [],
            "digital_connectivity": {
                "gs1_digital_link": None,
                "smartlabel_url": None,
                "qr_payload": None
            },
            "gs1_digital_twin_id": None,
            "packaging_verified": False,
            "price_history": [],
            "avg_cost_per_unit_usd": None,
            "supply_chain_emissions_kgco2e_per_kg": None,
            "supply_chain_emissions_scope3": None,
            "carbon_footprint_kgco2e_per_kg": None,
            "water_footprint_l_per_kg": None,
            "water_footprint_blue_l_per_kg": None,
            "water_footprint_green_l_per_kg": None,
            "plastic_footprint_g_per_l": None,
            "esg_certifications": [],
            "application_guidance": {
                "doses": [],
                "tank_mix_compatibility": None,
                "mode_of_action": None,
                "general_notes": None
            },
            "ingredient_estimates_mgkg": {},
            "data_quality_score": None,
            "primary_source_citation": None,
            "change_history": [],
            "notes": "",
            "created_at": None,
            "updated_by": None,
            "last_updated": "2025-07-26T00:00:00Z"
        }
    ]
}


def parse_value(v):
    if isinstance(v, str):
        if v.startswith("<"):
            try:
                return None, float(v[1:])
            except ValueError:
                return None, None
        if v.startswith("="):
            try:
                return float(v[1:]), None
            except ValueError:
                return None, None
        try:
            return float(v), None
        except ValueError:
            return None, None
    return None, None


def convert(old):
    new = json.loads(json.dumps(TEMPLATE))
    prod = new["products"][0]
    prod["product_id"] = old.get("product_id")
    prod["label_name"] = old.get("metadata", {}).get("label_name")
    prod["brand"] = old.get("metadata", {}).get("registrant")
    prod["manufacturer"] = old.get("source_wsda_record", {}).get("company_info", {}).get("company")
    prod["registration_numbers"]["WSDA"] = old.get("source_wsda_record", {}).get("wsda_product_number")
    comp = old.get("composition", {})
    ga = comp.get("guaranteed_analysis", {})
    nutrients = prod["nutrients"]
    mapping = {
        "Total Nitrogen (N)": "N_total",
        "Available Phosphoric Acid (P2O5)": "P",
        "Soluble Potash (K2O)": "K",
        "Calcium (Ca)": "Ca",
        "Magnesium (Mg)": "Mg",
        "Sulfur (S)": "S",
        "Boron (B)": "B",
        "Chlorine (Cl)": "Cl",
        "Cobalt (Co)": "Co",
        "Copper (Cu)": "Cu",
        "Iron (Fe)": "Fe",
        "Manganese (Mn)": "Mn",
        "Molybdenum (Mo)": "Mo",
        "Sodium (Na)": "Na",
        "Zinc (Zn)": "Zn"
    }
    for k, v in ga.items():
        key = mapping.get(k)
        if key:
            nutrients[key] = v
    prod["derived_from_raw"] = comp.get("derived_from_raw") or ""
    hm = comp.get("heavy_metals", {})
    hm_map = {
        "Arsenic": "As",
        "Cadmium": "Cd",
        "Cobalt": "Co",
        "Mercury": "Hg",
        "Molybdenum": "Mo",
        "Nickel": "Ni",
        "Lead": "Pb",
        "Selenium": "Se",
        "Zinc": "Zn"
    }
    for k, v in hm.items():
        dest = hm_map.get(k)
        if dest and dest in prod["heavy_metals"]:
            val, limit = parse_value(v)
            if val is not None:
                prod["heavy_metals"][dest]["value"] = val
                prod["heavy_metals"][dest]["detected"] = True
            if limit is not None:
                prod["heavy_metals"][dest]["detection_limit"] = limit
    new["products"][0] = prod
    return new

if __name__ == "__main__":
    infile = sys.argv[1]
    data = json.load(open(infile))
    new = convert(data)
    json.dump(new, open(infile, 'w'), indent=2)
    print(f"Converted {infile}")
