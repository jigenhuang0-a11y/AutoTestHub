@echo off
cd /d d:\AI_Project\ai-test-platform\backend

echo [1/3] makemigrations agent_gateway...
python manage.py makemigrations agent_gateway --name add_prompt_config

echo [2/3] migrate...
python manage.py migrate

echo [3/3] seed_agent_prompts...
python manage.py seed_agent_prompts

echo.
echo Done! Check results above.
pause
