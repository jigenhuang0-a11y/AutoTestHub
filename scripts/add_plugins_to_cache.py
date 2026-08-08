import json, os

cache_path = r'C:\Users\hjg\.codebuddy\plugins\marketplaces\codebuddy-plugins-official\.plugins-cache.json'
base = r'C:\Users\hjg\.codebuddy\plugins\marketplaces\codebuddy-plugins-official\plugins'

with open(cache_path, 'r', encoding='utf-8') as f:
    cache = json.load(f)


def read_skill_meta(skill_dir):
    md_path = os.path.join(skill_dir, 'SKILL.md')
    if not os.path.exists(md_path):
        return None, None
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    name = None
    desc = None
    in_front = False
    for line in content.split('\n'):
        s = line.strip()
        if s == '---':
            if not in_front:
                in_front = True
                continue
            else:
                break
        if in_front:
            if s.startswith('name:'):
                name = s.split(':', 1)[1].strip()
            elif s.startswith('description:'):
                desc = s.split(':', 1)[1].strip()
    return name, desc


def build_skills_array(plugin_name):
    plugin_dir = os.path.join(base, plugin_name, 'skills')
    skills = []
    for folder in os.listdir(plugin_dir):
        skill_path = os.path.join(plugin_dir, folder)
        if not os.path.isdir(skill_path):
            continue
        sname, sdesc = read_skill_meta(skill_path)
        if sname:
            skills.append({
                'name': sname,
                'description': sdesc or '',
                'path': 'skills/' + folder
            })
    return skills


installed_base = r'C:\Users\hjg\.codebuddy\plugins\marketplaces\codebuddy-plugins-official\plugins'

# Taste-skills entry
taste_entry = {
    'name': 'taste-skills',
    'description': '前端审美规范技能合集 - 反平庸前端，自动推断设计方向，拒绝模板化UI',
    'source': './plugins/taste-skills',
    'author': {'name': 'Leonxlnx'},
    'repository': 'https://github.com/Leonxlnx/taste-skill',
    'license': 'MIT',
    'keywords': ['design', 'frontend', 'ui', 'css', 'taste'],
    'category': 'design',
    'marketplaceName': 'codebuddy-plugins-official',
    'installedPath': installed_base + '\\taste-skills',
    'sourcePath': './plugins/taste-skills',
    'configPath': installed_base + '\\taste-skills\\.codebuddy-plugin\\plugin.json',
    'skills': build_skills_array('taste-skills')
}

# Agent-skills entry
agent_entry = {
    'name': 'agent-skills',
    'description': '软件工程规范合集 - TDD、代码审查、CI/CD、安全等28个最佳实践',
    'source': './plugins/agent-skills',
    'author': {'name': 'addyosmani'},
    'repository': 'https://github.com/addyosmani/agent-skills',
    'license': 'MIT',
    'keywords': ['engineering', 'tdd', 'code-review', 'ci-cd', 'security'],
    'category': 'engineering',
    'marketplaceName': 'codebuddy-plugins-official',
    'installedPath': installed_base + '\\agent-skills',
    'sourcePath': './plugins/agent-skills',
    'configPath': installed_base + '\\agent-skills\\.codebuddy-plugin\\plugin.json',
    'skills': build_skills_array('agent-skills')
}

# Insert into plugins array (before hot-skills to keep alphabetical-ish order)
plugins = cache['plugins']
insert_idx = 0
for i, p in enumerate(plugins):
    if p.get('name') == 'hot-skills':
        insert_idx = i
        break

plugins.insert(insert_idx, taste_entry)
plugins.insert(insert_idx + 1, agent_entry)

print(f'Inserted at index: {insert_idx}')
print(f'Taste skills count: {len(taste_entry["skills"])}')
print(f'Agent skills count: {len(agent_entry["skills"])}')

# Write back
with open(cache_path, 'w', encoding='utf-8') as f:
    json.dump(cache, f, ensure_ascii=False, indent=2)

print(f'Cache written successfully! New total plugins: {len(plugins)}')
