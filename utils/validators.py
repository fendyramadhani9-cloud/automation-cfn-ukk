"""
Utility validators for comparing expected and actual AWS configuration values.
"""
from typing import Any, Dict, List, Optional, Tuple


def get_tag(tags: Optional[List[Dict[str, str]]], key: str = "Name") -> Optional[str]:
    """Extract tag value safely from AWS Tags list."""
    if not tags:
        return None
    for t in tags:
        if t.get("Key") == key:
            return t.get("Value")
    return None


def make_result(
    check_id: str,
    category: str,
    component: str,
    requirement: str,
    expected: str,
    actual: str,
    score: float,
    max_score: float,
    status: str,
    error_code: str = "",
    error_message: str = "",
    evidence: str = "",
) -> Dict[str, Any]:
    """Helper to build consistent result dictionary."""
    return {
        "check_id": check_id,
        "category": category,
        "component": component,
        "requirement": requirement,
        "expected": str(expected),
        "actual": str(actual),
        "score": score,
        "max_score": max_score,
        "status": status,
        "error_code": error_code,
        "error_message": error_message,
        "evidence": evidence,
    }


def compare_equal(
    check_id: str,
    category: str,
    component: str,
    requirement: str,
    expected: Any,
    actual: Any,
    max_score: float,
    err_code_mismatch: str,
    err_msg_mismatch: str,
    evidence: str = "",
) -> Dict[str, Any]:
    """Compare exact equality of two values."""
    if expected == actual:
        return make_result(
            check_id=check_id,
            category=category,
            component=component,
            requirement=requirement,
            expected=str(expected),
            actual=str(actual),
            score=max_score,
            status="PASS",
            evidence=evidence or f"Match: {actual}",
        )
    return make_result(
        check_id=check_id,
        category=category,
        component=component,
        requirement=requirement,
        expected=str(expected),
        actual=str(actual),
        score=0.0,
        status="FAIL",
        error_code=err_code_mismatch,
        error_message=err_msg_mismatch,
        evidence=evidence or f"Expected '{expected}' but got '{actual}'",
    )
