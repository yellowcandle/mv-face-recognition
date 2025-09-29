"""
Contract tests for compliance checking functionality.
Tests the ComplianceChecker class against defined contracts.
"""

import pytest
from src.compliance import ComplianceChecker, ComplianceStandard


class TestComplianceChecker:
    """Test suite for ComplianceChecker contract compliance."""

    def setup_method(self):
        """Set up test fixtures."""
        self.checker = ComplianceChecker()

    def test_check_owasp_compliance_structure(self):
        """Test OWASP compliance check returns proper structure."""
        result = self.checker.check_owasp_compliance()

        assert "standard" in result
        assert result["standard"] == "OWASP Top 10"
        assert "checks" in result
        assert "score" in result
        assert "compliant" in result
        assert "timestamp" in result

        # Should have 10 checks
        assert len(result["checks"]) == 10

        # Each check should have status and details
        for check_name, check_result in result["checks"].items():
            assert "status" in check_result
            assert "details" in check_result

    def test_check_gdpr_compliance_structure(self):
        """Test GDPR compliance check returns proper structure."""
        result = self.checker.check_gdpr_compliance()

        assert result["standard"] == "GDPR"
        assert "checks" in result
        assert len(result["checks"]) == 6  # GDPR checks

        for check_name, check_result in result["checks"].items():
            assert "status" in check_result
            assert "details" in check_result

    def test_run_full_audit_all_standards(self):
        """Test full audit with all standards."""
        result = self.checker.run_full_audit()

        assert "audit_timestamp" in result
        assert "standards_checked" in result
        assert "results" in result
        assert "overall_compliant" in result

        # Should check both standards
        assert len(result["standards_checked"]) == 2
        assert "owasp_top_10" in result["results"]
        assert "gdpr" in result["results"]

    def test_run_full_audit_specific_standards(self):
        """Test full audit with specific standards."""
        result = self.checker.run_full_audit([ComplianceStandard.OWASP_TOP_10])

        assert len(result["standards_checked"]) == 1
        assert "owasp_top_10" in result["results"]
        assert "gdpr" not in result["results"]

    def test_get_audit_history_empty(self):
        """Test audit history when no audits performed."""
        history = self.checker.get_audit_history()
        assert history == []

    def test_get_audit_history_after_audit(self):
        """Test audit history after performing audit."""
        self.checker.run_full_audit([ComplianceStandard.OWASP_TOP_10])
        history = self.checker.get_audit_history()

        assert len(history) == 1
        assert "timestamp" in history[0]
        assert "results" in history[0]

    def test_owasp_checks_content(self):
        """Test that OWASP checks contain expected content."""
        result = self.checker.check_owasp_compliance()

        checks = result["checks"]

        # Check some specific OWASP checks
        assert "injection" in checks
        assert checks["injection"]["status"] == "pass"
        assert "Input validation" in checks["injection"]["details"]

        assert "broken_auth" in checks
        assert "authentication" in checks["broken_auth"]["details"]

        assert "sensitive_data" in checks
        assert "encryption" in checks["sensitive_data"]["details"]

    def test_gdpr_checks_content(self):
        """Test that GDPR checks contain expected content."""
        result = self.checker.check_gdpr_compliance()

        checks = result["checks"]

        # Check GDPR principles
        assert "data_minimization" in checks
        assert "consent_management" in checks
        assert "data_portability" in checks
        assert "right_to_erasure" in checks

    def test_compliance_scoring(self):
        """Test compliance scoring logic."""
        # OWASP - all pass should be compliant
        owasp = self.checker.check_owasp_compliance()
        assert owasp["compliant"] == True
        assert owasp["score"] == "10/10"

        # GDPR - should be compliant with 80% threshold
        gdpr = self.checker.check_gdpr_compliance()
        passed = sum(1 for c in gdpr["checks"].values() if c["status"] == "pass")
        total = len(gdpr["checks"])
        expected_compliant = passed >= total * 0.8
        assert gdpr["compliant"] == expected_compliant

    def test_unknown_component_vulnerabilities(self):
        """Test that component vulnerability check returns unknown status."""
        result = self.checker.check_owasp_compliance()
        vuln_check = result["checks"]["vulnerable_components"]

        assert vuln_check["status"] == "unknown"
        assert "dependency scanning" in vuln_check["details"]