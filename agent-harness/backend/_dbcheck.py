from app.core.task_store import get_task_store
s = get_task_store()
suites, st = s.list_testsuites(page=1, page_size=10)
print('suites total', st, 'first', suites[0].to_dict() if suites else 'none')
cases, ct = s.list_testcases(page=1, page_size=10)
print('cases total', ct, 'first', cases[0].to_dict() if cases else 'none')
plans, pt = s.list_perf_plans(page=1, page_size=10)
print('perf total', pt, 'first', plans[0].to_dict() if plans else 'none')
