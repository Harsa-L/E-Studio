"""Regression checks for the pure-Python E-Studio domain services."""

import unittest

from article_models import PricingInfo, ProductIdent
from article_types import BulkCaseArticle
from template_model import LabelTemplate, Margins
from tier_engine import TierResolver, TierTargetSpec


class TemplateModelTests(unittest.TestCase):
    def test_json_round_trip_preserves_template(self) -> None:
        template = LabelTemplate(
            name="Shelf label",
            width_mm=100.0,
            height_mm=50.0,
            inner_margins_mm=Margins(2.0, 2.0, 2.0, 2.0),
            outer_margins_mm=Margins(1.0, 1.0, 1.0, 1.0),
        )

        restored = LabelTemplate.from_json(template.to_json())

        self.assertEqual(restored, template)


class PricingTests(unittest.TestCase):
    def test_case_article_exposes_binding_context(self) -> None:
        article = BulkCaseArticle(
            ident=ProductIdent("A-1", "123456789012", "Coffee"),
            pricing=PricingInfo(12.0),
        )

        self.assertEqual(article.unit_price_inside_case(), 12.0)
        self.assertEqual(article.to_binding_context()["EFFECTIVE_PRICE"], 12.0)


class TierResolverTests(unittest.TestCase):
    def test_missing_tier_falls_back_to_base_price(self) -> None:
        result = TierResolver.resolve(
            TierTargetSpec(primary_index=1),
            {"TIERS": [], "SELLING_PRICE": 12.0, "CURRENCY": "EUR"},
        )

        self.assertEqual(result["unit_price"], 12.0)
        self.assertTrue(result["is_fallback"])


if __name__ == "__main__":
    unittest.main()
