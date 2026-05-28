"""
Fix two bugs in app.py:
1. Missing variable declarations in admin_add_tailor
2. Division by NoneType errors (unsupported operand type(s) for /: 'NoneType' and 'float')
"""

APP_FILE = "app.py"

with open(APP_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# ── FIX 1: Restore missing variable declarations in admin_add_tailor ────────
old_tailor_add = """    gender_category = request.form.get('gender_category', 'Both').strip()

    if not shop_name or not is_valid_email(email) or not is_valid_phone(phone):"""

new_tailor_add = """    shop_name       = request.form.get('shop_name', '').strip()
    email           = request.form.get('email', '').strip()
    phone           = request.form.get('phone', '').strip()
    location        = request.form.get('location', '').strip()
    speciality      = request.form.get('speciality', 'All Types').strip()
    password        = request.form.get('password', '123456').strip()
    gender_category = request.form.get('gender_category', 'Both').strip()

    if not shop_name or not is_valid_email(email) or not is_valid_phone(phone):"""

if old_tailor_add in content:
    content = content.replace(old_tailor_add, new_tailor_add)
    print("FIX 1: Restored missing variable declarations in admin_add_tailor")
else:
    # Try with different line endings
    old_crlf = old_tailor_add.replace('\n', '\r\n')
    new_crlf = new_tailor_add.replace('\n', '\r\n')
    if old_crlf in content:
        content = content.replace(old_crlf, new_crlf)
        print("FIX 1: Restored missing variable declarations in admin_add_tailor (CRLF)")
    else:
        print("FIX 1: SKIPPED - pattern not found (may already be fixed)")

# ── FIX 2: Find all division operations that could involve None ─────────────
# Common patterns: value / count, total / num, etc.
# We need to find lines with / operator on potentially-None DB values
import re

# Find lines that do arithmetic division (not string/path division)
# and wrap None-prone values with (val or 0)
division_fixes = 0

lines = content.split('\n')
new_lines = []
for i, line in enumerate(lines):
    original = line
    
    # Skip comments, strings, route definitions, imports
    stripped = line.strip()
    if stripped.startswith('#') or stripped.startswith('@') or stripped.startswith('import') or stripped.startswith('from'):
        new_lines.append(line)
        continue
    
    # Look for patterns like:  something / something  in Python expressions
    # but not in strings or URLs
    # Common culprits: row['total'] / row['count'] or similar DB fetches
    # The error is "NoneType / float" so we need to find where a None value is divided
    
    # Pattern: variable_or_expression / number_or_variable (but not in strings/URLs)
    # We'll look for fetchone() results used in division
    
    new_lines.append(line)

content = '\n'.join(new_lines)

# ── FIX 2b: More targeted - find the actual division error ──────────────────
# Search for common patterns where DB results are divided
# The error says 'NoneType' / 'float' - likely a SUM() or AVG() returning None

# Find all lines with arithmetic that could be None
patterns_to_fix = [
    # Pattern: total_something / count  or  sum / count
    # We need to find these in context
]

# Let's find all lines with ' / ' that reference database results
print("\nSearching for potential division-by-None issues...")
for i, line in enumerate(lines):
    stripped = line.strip()
    if ' / ' in stripped and not stripped.startswith('#') and not stripped.startswith("'") and not stripped.startswith('"'):
        # Check if it's a real division (not a URL path)
        if "http" not in stripped and "route" not in stripped and "url_for" not in stripped and "href" not in stripped:
            if "SELECT" not in stripped and "FROM" not in stripped:
                print(f"  Line {i+1}: {stripped[:120]}")

with open(APP_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print("\nDone. Now check the division lines above for the TypeError source.")
