"""
Unit tests for classifier/base.py

Covers:
- build_result() rejects invalid severities
- BaseClassifier can't be instantiated directly (it's abstract)
- Output shape from build_result() is consistent regardless of caller
"""

import pytest
from classifier.base import BaseClassifier, SEVERITY_SW, DISCLAIMER


class DummyClassifier(BaseClassifier):
    """Minimal concrete subclass used only for testing the base class."""
    name = "dummy"

    def classify(self, symptom_text: str) -> dict:
        return self.build_result("LOW", [], "test")


class TestBaseClassifierIsAbstract:
    def test_cannot_instantiate_base_classifier_directly(self):
        """BaseClassifier defines classify() as abstract, so it must
        raise TypeError if instantiated without a subclass implementing it."""
        with pytest.raises(TypeError):
            BaseClassifier()

    def test_subclass_without_classify_cannot_be_instantiated(self):
        """A subclass that doesn't implement classify() is still abstract."""
        class IncompleteClassifier(BaseClassifier):
            name = "incomplete"

        with pytest.raises(TypeError):
            IncompleteClassifier()

    def test_subclass_with_classify_can_be_instantiated(self):
        """Sanity check: a properly implemented subclass works fine."""
        instance = DummyClassifier()
        assert instance is not None


class TestBuildResultRejectsInvalidSeverities:
    def test_invalid_severity_raises_value_error(self):
        c = DummyClassifier()
        with pytest.raises(ValueError):
            c.build_result("URGENT", [], "not a real severity tier")

    def test_lowercase_severity_raises_value_error(self):
        """Severities must be uppercase exactly as defined - 'low' should
        not silently pass just because it's the right word."""
        c = DummyClassifier()
        with pytest.raises(ValueError):
            c.build_result("low", [], "wrong case")

    def test_empty_string_severity_raises_value_error(self):
        c = DummyClassifier()
        with pytest.raises(ValueError):
            c.build_result("", [], "empty severity")

    @pytest.mark.parametrize("severity", ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
    def test_all_valid_severities_are_accepted(self, severity):
        """The four real severity tiers should never raise."""
        c = DummyClassifier()
        result = c.build_result(severity, [], "valid case")
        assert result["severity"] == severity


class TestBuildResultOutputShape:
    def test_output_contains_all_required_keys(self):
        c = DummyClassifier()
        result = c.build_result("HIGH", ["fever", "cough"], "test reason")
        expected_keys = {"severity", "severity_sw", "symptoms", "reason", "disclaimer", "classifier"}
        assert set(result.keys()) == expected_keys

    def test_severity_sw_matches_severity_mapping(self):
        c = DummyClassifier()
        for severity, expected_sw in SEVERITY_SW.items():
            result = c.build_result(severity, [], "test")
            assert result["severity_sw"] == expected_sw

    def test_symptoms_list_is_preserved_exactly(self):
        c = DummyClassifier()
        symptoms = ["fever", "headache", "stiff_neck"]
        result = c.build_result("HIGH", symptoms, "test")
        assert result["symptoms"] == symptoms

    def test_disclaimer_is_always_the_standard_text(self):
        """The disclaimer must never vary between classifiers - it's a
        safety-critical piece of text that every result must carry."""
        c = DummyClassifier()
        result = c.build_result("LOW", [], "test")
        assert result["disclaimer"] == DISCLAIMER

    def test_classifier_field_matches_subclass_name(self):
        """This is what lets downstream code know which of the five
        approaches produced a given result."""
        c = DummyClassifier()
        result = c.build_result("LOW", [], "test")
        assert result["classifier"] == "dummy"

    def test_empty_symptoms_list_is_valid(self):
        c = DummyClassifier()
        result = c.build_result("LOW", [], "no symptoms found")
        assert result["symptoms"] == []