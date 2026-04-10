import re
import os

files = [
    'frontend/hr-dashboard/src/components/candidates/CandidateTable.tsx',
    'frontend/hr-dashboard/src/components/candidates/CandidateDetailModal.tsx',
    'frontend/hr-dashboard/src/components/candidates/CandidateCreateModal.tsx'
]

for path in files:
    if not os.path.exists(path):
        continue
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # CandidateTable.tsx
    content = re.sub(r'\s*<th>Present Address</th>\n', '\n', content)
    content = re.sub(r'\s*<th>Permanent Address</th>\n', '\n', content)
    content = re.sub(r'\s*<td.*?\{candidate\.presentAddress \|\| "-"\}.*?</td>\n', '\n', content, flags=re.DOTALL)
    content = re.sub(r'\s*<td.*?\{candidate\.permanentAddress \|\| "-"\}.*?</td>\n', '\n', content, flags=re.DOTALL)
    
    # CandidateDetailModal.tsx
    content = re.sub(r'\s*<div>\s*<div className="text-sm font-medium text-muted-foreground">Present Address</div>\s*<div className="mt-1 text-sm whitespace-pre-wrap">\{candidate\.presentAddress \|\| \'Not specified\'\}</div>\s*</div>\n', '\n', content, flags=re.DOTALL)
    content = re.sub(r'\s*<div>\s*<div className="text-sm font-medium text-muted-foreground">Permanent Address</div>\s*<div className="mt-1 text-sm whitespace-pre-wrap">\{candidate\.permanentAddress \|\| \'Not specified\'\}</div>\s*</div>\n', '\n', content, flags=re.DOTALL)

    # CandidateCreateModal.tsx schema
    content = re.sub(r'\s*presentAddress:\s*z\.string\(\)\.trim\(\)\.optional\(\)\.or\(z\.literal\(""\)\),\n', '\n', content)
    content = re.sub(r'\s*permanentAddress:\s*z\.string\(\)\.trim\(\)\.optional\(\)\.or\(z\.literal\(""\)\),\n', '\n', content)
    
    # default values
    content = re.sub(r'\s*presentAddress:\s*"",\n', '\n', content)
    content = re.sub(r'\s*permanentAddress:\s*"",\n', '\n', content)
    
    # candidate?. values
    content = re.sub(r'\s*presentAddress:\s*candidate\?\.presentAddress\s*\|\|\s*"",\n', '\n', content)
    content = re.sub(r'\s*permanentAddress:\s*candidate\?\.permanentAddress\s*\|\|\s*"",\n', '\n', content)
    
    # trim() || undefined
    content = re.sub(r'\s*presentAddress:\s*values\.presentAddress\?\.trim\(\)\s*\|\|\s*undefined,\n', '\n', content)
    content = re.sub(r'\s*permanentAddress:\s*values\.permanentAddress\?\.trim\(\)\s*\|\|\s*undefined,\n', '\n', content)
    
    # form fields code
    pattern_present = r'\s*<FormField\s*control=\{form\.control\}\s*name="presentAddress"\s*render=\{[^}]*\s*[^}]*\s*</FormItem>\s*\)\}\s*/>\n'
    content = re.sub(pattern_present, '\n', content, flags=re.DOTALL)
    
    pattern_permanent = r'\s*<FormField\s*control=\{form\.control\}\s*name="permanentAddress"\s*render=\{[^}]*\s*[^}]*\s*</FormItem>\s*\)\}\s*/>\n'
    content = re.sub(pattern_permanent, '\n', content, flags=re.DOTALL)
    
    # Sometimes regex isn't enough for nested blocks, let's just do simple replacements
    if 'name="presentAddress"' in content:
        # manual delete for form fields if regex failed
        pass

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
        
