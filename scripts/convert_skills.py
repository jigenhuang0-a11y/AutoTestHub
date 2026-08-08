"""Convert plugin sub-skills to CodeBuddy native .codebuddy/skills/ format."""
import os
import shutil
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

PLUGIN_BASE = r"C:\Users\hjg\.codebuddy\plugins\marketplaces\codebuddy-plugins-official\plugins"
WORKSPACE = r"d:\AI_Project\ai-test-platform"
TARGET_BASE = os.path.join(WORKSPACE, ".codebuddy", "skills")

def extract_frontmatter(md_path):
    """Extract name and description from SKILL.md frontmatter."""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    result = {}
    in_front = False
    lines = content.split('\n')
    for i, line in enumerate(lines):
        s = line.strip()
        if s == '---':
            if not in_front:
                in_front = True
                continue
            else:
                break
        if in_front:
            if ':' in s:
                key, _, val = s.partition(':')
                result[key.strip()] = val.strip()
    return result, content

def convert_plugin(plugin_name):
    skills_dir = os.path.join(PLUGIN_BASE, plugin_name, "skills")
    if not os.path.isdir(skills_dir):
        print(f"  SKIP: {skills_dir} not found")
        return []
    
    results = []
    for folder in os.listdir(skills_dir):
        src_path = os.path.join(skills_dir, folder)
        if not os.path.isdir(src_path):
            continue
        
        md_file = os.path.join(src_path, "SKILL.md")
        if not os.path.exists(md_file):
            print(f"  SKIP: no SKILL.md in {folder}")
            continue
        
        meta, content = extract_frontmatter(md_file)
        name = meta.get('name', folder)
        desc = meta.get('description', '')
        
        # Create target directory
        target_dir = os.path.join(TARGET_BASE, name)
        os.makedirs(target_dir, exist_ok=True)
        
        # Copy SKILL.md
        target_md = os.path.join(target_dir, "SKILL.md")
        shutil.copy2(md_file, target_md)
        
        results.append((name, desc))
        print(f"  [OK] {name}")
    
    return results

def main():
    os.makedirs(TARGET_BASE, exist_ok=True)
    
    total = 0
    for plugin in ["taste-skills", "agent-skills"]:
        print(f"\n{'='*50}")
        print(f"Converting: {plugin}")
        print(f"{'='*50}")
        skills = convert_plugin(plugin)
        total += len(skills)
    
    print(f"\n{'='*50}")
    print(f"Done! {total} skills converted to .codebuddy/skills/")
    print(f"Target: {TARGET_BASE}")

if __name__ == "__main__":
    main()
