import sqlite3

db_path = r'd:\AI_Project\ai-test-platform\backend\db.sqlite3'
conn = sqlite3.connect(db_path)
c = conn.cursor()

print("=== 处理数据库... ===")

# 删除已存在的表（让迁移重新创建）
for table in ['agent_tasks', 'agent_prompt_configs']:
    c.execute(f"DROP TABLE IF EXISTS {table}")
    print(f"  DROP TABLE {table}")

# 删除迁移记录
c.execute("DELETE FROM django_migrations WHERE app='agent_gateway'")
print("  DELETE django_migrations for agent_gateway")

conn.commit()
conn.close()
print("✅ 完成，请重新运行：python manage.py migrate")
