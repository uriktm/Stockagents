#!/usr/bin/env python3
"""Test script to verify confidence score extraction works correctly."""

import re
from typing import Optional


def extract_confidence_score(raw_response: str) -> Optional[float]:
    """Extract the numeric confidence score from the assistant's response."""
    if not raw_response:
        return None

    patterns = [
        r"confidence\s*score[^0-9]*([0-9]+(?:\.[0-9]+)?)",
        r"ציון\s*ביטחון[^0-9]*([0-9]+(?:\.[0-9]+)?)",
        r"([0-9]+(?:\.[0-9]+)?)\s*/\s*10",
    ]

    for i, pattern in enumerate(patterns):
        match = re.search(pattern, raw_response, re.IGNORECASE)
        if match:
            try:
                score = float(match.group(1))
                print(f"✅ Found score {score} using pattern #{i+1}: {pattern[:40]}")
                return score
            except (TypeError, ValueError) as e:
                print(f"❌ Failed to convert: {e}")
                continue
    
    print(f"❌ No pattern matched. First 200 chars: {raw_response[:200]}")
    return None


if __name__ == "__main__":
    print("Testing confidence extraction patterns...\n")
    print("=" * 60)
    
    test_cases = [
        # Hebrew formats
        ("ציון ביטחון: 9/10", 9.0),
        ("ציון ביטחון: 6 מתוך 10", 6.0),
        ("**ציון ביטחון:** 7.5/10", 7.5),
        ("2. ציון ביטחון: 8", 8.0),
        
        # English formats
        ("confidence score: 9/10", 9.0),
        ("Confidence Score: 7", 7.0),
        
        # Edge cases
        ("ברמת ביטחון של 6 מתוך 10", 6.0),
        ("5/10 confidence", 5.0),
        ("הציון שלי הוא 8 על 10", 8.0),
        
        # Should fail
        ("אין ציון כאן", None),
    ]
    
    passed = 0
    failed = 0
    
    for i, (test_input, expected) in enumerate(test_cases, 1):
        print(f"\nTest {i}: '{test_input}'")
        result = extract_confidence_score(test_input)
        
        if result == expected:
            print(f"  ✅ PASS - Got {result}")
            passed += 1
        else:
            print(f"  ❌ FAIL - Expected {expected}, got {result}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    
    if failed == 0:
        print("\n🎉 All tests passed! Extraction function works correctly.")
    else:
        print(f"\n⚠️ {failed} test(s) failed. Check the patterns.")
