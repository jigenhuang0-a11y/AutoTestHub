#!/usr/bin/env python
"""Replace the prompt in views.py with a stricter version"""
import re

# Read file
with open('data_factory/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Define new prompt (using English to avoid JSON parsing issues)
new_prompt = '''            # 构建 Prompt (严格版,确保返回有效JSON)
            language_text = '中文' if 'zh' in languages else '英文'
            prompt = f"""# Role
You are a professional test data generation expert for LLM applications.

# Task
Generate mock test data based on the business scenario provided by the user.

# Business Scenario
{scenario}

# Instructions

## Step 1: Extract Business Fields
Analyze the scenario and extract 3-8 key business fields. For example:
- If scenario mentions "cross-border logistics, customs clearance delay, last-mile delivery, tariff inquiry", extract fields like: order_id, tracking_number, first_leg_status, customs_status, last_leg_status, tariff_amount, estimated_arrival, customer_note
- Use English snake_case for field names (e.g., order_id, not Chinese)
- Field values can be in Chinese or appropriate format

## Step 2: Generate Test Data
Generate {positive_count + negative_count + boundary_count} test items:
- Positive ({positive_count} items): Normal business flow with reasonable values
- Negative ({negative_count} items): Missing fields, format errors, contradictory states  
- Boundary ({boundary_count} items): Long text, special characters, extreme values

# CRITICAL RULES - MUST FOLLOW

1. Return ONLY valid JSON array - no markdown, no comments, no explanations
2. NO programming syntax - Do NOT use .repeat(), concatenation, or any code
3. All strings must be properly quoted with double quotes
4. No trailing commas in arrays or objects
5. Escape special characters properly
6. Each item must have: case_id, type, label, language, plus extracted business fields

# Output Format Example

For scenario "cross-border logistics consultation":

[
  {{"case_id":"POS0001","type":"positive","label":1,"language":"zh","order_id":"ORD20240603001","tracking_number":"SF1234567890","first_leg_status":"已签收","customs_status":"清关中","last_leg_status":"运输中","tariff_amount":"156.80","estimated_arrival":"2024-06-10","customer_note":"请尽快送达"}},
  {{"case_id":"NEG0001","type":"negative","label":0,"language":"zh","order_id":"","tracking_number":"INVALID_FORMAT","first_leg_status":"","customs_status":"未知状态","last_leg_status":"","tariff_amount":"-100.00","estimated_arrival":"","customer_note":""}},
  {{"case_id":"BND0001","type":"boundary","label":-1,"language":"zh","order_id":"ORD_TEST_SPECIAL_CHARS","tracking_number":"VERY_LONG_TRACKING_NUMBER_HERE_WITH_MANY_CHARACTERS","first_leg_status":"emoji_here","customs_status":"Processing...maybe slow?","last_leg_status":"??","tariff_amount":"999999999.99","estimated_arrival":"9999-12-31","customer_note":"Long note with emoji"}}
]

# NOW EXECUTE

Scenario to analyze: "{scenario}"

Required output: {positive_count + negative_count + boundary_count} test items

IMPORTANT: Return ONLY the JSON array. Nothing before, nothing after. The response must be parseable by json.loads().
"""'''

# Find and replace old prompt
pattern = r'# 构建 Prompt \(详细版,引导AI深度思考\).*?记住: 这是模拟数据,可以是虚构的,但要贴切实际业务场景!"""'
content = re.sub(pattern, new_prompt.strip(), content, flags=re.DOTALL)

# Write back
with open('data_factory/views.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Prompt replaced successfully!')
