import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_test_platform.settings')
django.setup()

from testsuites.models import TestSuite, TestStep, StepParameter
from testcases.models import TestCase
from accounts.models import User

def main():
    print("\nStart testing suite functionality...\n")
    
    user = User.objects.first()
    if not user:
        print("Error: No user found")
        return
    
    suite = TestSuite.objects.create(
        name="Login Business Flow Test",
        description="Test complete login flow: get token -> call user info API",
        created_by=user
    )
    print(f"[OK] Created suite: {suite.name} (ID: {suite.id})")
    
    test_cases = TestCase.objects.all()[:3]
    for i, tc in enumerate(test_cases, 1):
        step = TestStep.objects.create(
            suite=suite,
            test_case=tc,
            order=i,
            parameter_mapping={},
            skip_on_failure=(i == 1),
            enabled=True
        )
        print(f"[OK] Added step {i}: {tc.title}")
    
    step = suite.steps.first()
    if step:
        param = StepParameter.objects.create(
            step=step,
            param_name="auth_token",
            json_path="$.data.token",
            description="Extract token from login response"
        )
        print(f"[OK] Added output param: {param.param_name} = {param.json_path}")
    
    from execution.scenario_engine import ScenarioExecutionEngine
    
    try:
        engine = ScenarioExecutionEngine(suite.id, suite.created_by.id)
        result = engine.execute()
        
        print(f"\n[OK] Execution completed")
        print(f"  - Status: {result['status']}")
        print(f"  - Total steps: {result['total_steps']}")
        print(f"  - Passed: {result['passed_steps']}")
        print(f"  - Failed: {result['failed_steps']}")
        print(f"  - Skipped: {result['skipped_steps']}")
    except Exception as e:
        print(f"[ERROR] Execution failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)
    print(f"\nSuite ID: {suite.id}")
    print(f"Access via frontend: /testsuites/{suite.id}/edit")

if __name__ == '__main__':
    main()
