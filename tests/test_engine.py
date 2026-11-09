import unittest

from engine import ALERT_MESSAGES, alert_priority, evaluate_case


def sample_case(**changes):
    data = {
        "business_name": "Negocio de prueba",
        "ruc": "20123456786",
        "person_type": "natural",
        "activity": "Venta minorista",
        "projected_annual_income": 84000,
        "projected_annual_purchases": 36000,
        "monthly_income": 7000,
        "monthly_purchases": 3000,
        "annual_costs": 24000,
        "annual_expenses": 12000,
        "fixed_assets": 10000,
        "taxable_share": 1,
        "workers": 2,
        "excluded_activity": False,
        "plans": {},
    }
    data.update(changes)
    return data


class RegimeEngineTests(unittest.TestCase):
    def test_company_is_not_eligible_for_nrus(self):
        result = evaluate_case(sample_case(person_type="juridica"), uit=5500)
        self.assertFalse(result["regimes"]["NRUS"]["applicable"])
        self.assertTrue(any("personas naturales" in reason for reason in result["regimes"]["NRUS"]["reasons"]))

    def test_over_limit_case_flags_nrus_and_rer(self):
        result = evaluate_case(sample_case(projected_annual_income=600000, monthly_income=50000), uit=5500)
        self.assertFalse(result["regimes"]["NRUS"]["applicable"])
        self.assertFalse(result["regimes"]["RER"]["applicable"])
        self.assertTrue(result["regimes"]["RMT"]["applicable"])

    def test_rmt_tax_uses_taxable_income_not_gross_revenue(self):
        data = sample_case(
            person_type="juridica", projected_annual_income=100000,
            projected_annual_purchases=30000, annual_costs=40000,
            annual_expenses=10000, monthly_income=8333.33,
        )
        result = evaluate_case(data, uit=5500)
        self.assertEqual(result["regimes"]["RMT"]["estimated_annual_income_tax"], 5000)

    def test_recommends_a_regime_without_uit_and_marks_rmt_unverified(self):
        result = evaluate_case(sample_case(), uit=None)
        self.assertIn(result["recommendation"], ("NRUS", "RER", "RG"))
        self.assertEqual(result["regimes"]["RMT"]["eligibility_status"], "unknown")
        self.assertTrue(result["missing_or_caveats"])
        self.assertTrue(result["recommendation_benefits"])
        self.assertTrue(result["recommendation_obligations"])

    def test_incomplete_data_still_returns_a_concrete_prudent_recommendation(self):
        data = sample_case()
        data.pop("projected_annual_income")
        result = evaluate_case(data, uit=5500)
        self.assertEqual(result["recommendation"], "RG")
        self.assertIn("Información incompleta", " ".join(result["missing_or_caveats"]))

    def test_rmt_and_general_monthly_payments_are_not_guessed(self):
        result = evaluate_case(sample_case(person_type="juridica"), uit=5500)
        self.assertIsNone(result["regimes"]["RMT"]["estimated_monthly_income_tax"])
        self.assertIsNone(result["regimes"]["RG"]["estimated_monthly_income_tax"])

    def test_future_growth_creates_alert(self):
        result = evaluate_case(sample_case(plans={"increase_income": True}), uit=5500)
        self.assertTrue(any("crecimiento" in alert.lower() for alert in result["alerts"]))

    def test_alert_priorities_put_exclusions_and_limits_before_growth(self):
        self.assertLess(alert_priority(ALERT_MESSAGES["declared_exclusion"]), alert_priority(ALERT_MESSAGES["planned_exclusion"]))
        self.assertLess(alert_priority(ALERT_MESSAGES["exceed_limits"]), alert_priority(ALERT_MESSAGES["income_rer"]))
        self.assertLess(alert_priority(ALERT_MESSAGES["planned_exclusion"]), alert_priority(ALERT_MESSAGES["income_nrus"]))
        self.assertLess(alert_priority(ALERT_MESSAGES["purchases_rer"]), alert_priority(ALERT_MESSAGES["increase_income"]))
        self.assertEqual(alert_priority("Alerta histórica desconocida"), alert_priority(ALERT_MESSAGES["expansion"]))


if __name__ == "__main__":
    unittest.main()
