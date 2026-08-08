import json

cache_path = r'C:\Users\hjg\.codebuddy\plugins\marketplaces\codebuddy-plugins-official\.plugins-cache.json'
with open(cache_path, 'r', encoding='utf-8') as f:
    cache = json.load(f)

plugins = cache['plugins']
for p in plugins:
    name = p.get('name', '')
    if name in ('taste-skills', 'agent-skills', 'hot-skills'):
        print(f'=== {name} ===')
        keys = {k: v for k, v in p.items() if k != 'skills'}
        print(json.dumps(keys, indent=2, ensure_ascii=False))
        if 'skills' in p:
            skill_count = len(p['skills'])
            print(f'  skills ({skill_count}):')
            for s in p['skills'][:3]:
                print(f'    {json.dumps(s, ensure_ascii=False)}')
        print()
