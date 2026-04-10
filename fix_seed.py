import re

path = 'seed_sqlite.py'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

c = re.sub(r'\s*"present_address":\s*".*?",\n', '\n', c)
c = re.sub(r'\s*"permanent_address":\s*".*?",\n', '\n', c)
c = c.replace('            "present_address": entry["present_address"],\n', '')
c = c.replace('            "permanent_address": entry["permanent_address"],\n', '')
c = re.sub(r'\s*present_address\s*=\s*:present_address,\n', '\n', c)
c = re.sub(r'\s*permanent_address\s*=\s*:permanent_address,\n', '\n', c)

c = c.replace('                    present_address, permanent_address, date_of_birth,\n', '                    date_of_birth,\n')
c = c.replace('                    :present_address, :permanent_address, :date_of_birth,\n', '                    :date_of_birth,\n')

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)
