import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
django.setup()

from testsuites.models import TestSuite
from testcases.models import TestCase
from accounts.models import User

def main():
    print("\nTesting simplified suite functionality...\n")
    
    user = User.objects.first()
    if not user:
        print("Error: No user found")
        return
    
    # Get some test cases
    test_cases = TestCase.objects.all()[:3]
    if not test_cases:
        print("Warning: No test cases found")
        case_ids = []
    else:
        case_ids = [tc.id for tc in test_cases]
        print(f"Found {len(case_ids)} test cases: {case_ids}")
    
    # Create a simple suite
    suite = TestSuite.objects.create(
        name="Simple Test Suite",
        description="A simple collection of test cases",
        test_cases=case_ids,
        created_by=user
    )
    print(f"[OK] Created suite: {suite.name} (ID: {suite.id})")
    print(f"[OK] Contains {suite.get_cases_count()} test cases")
    
    # List cases in suite
    cases_in_suite = suite.get_test_cases_queryset()
    print(f"\nTest cases in suite:")
    for case in cases_in_suite:
        print(f"  - ID {case.id}: {case.title} ({case.method} {case.api_endpoint})")
    
    print("\n" + "=" * 60)
    print("Simplified suite model works correctly!")
    print("=" * 60)

if __name__ == '__main__':
    main()
