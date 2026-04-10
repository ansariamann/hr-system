import re

path = 'frontend/hr-dashboard/src/lib/api.ts'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

c = re.sub(r'\s*present_address\?:\s*string\s*\|\s*null;\n', '\n', c)
c = re.sub(r'\s*permanent_address\?:\s*string\s*\|\s*null;\n', '\n', c)
c = re.sub(r'\s*presentAddress:\s*backend\.present_address\s*\|\|\s*undefined,\n', '\n', c)
c = re.sub(r'\s*permanentAddress:\s*backend\.permanent_address\s*\|\|\s*undefined,\n', '\n', c)
c = re.sub(r'\s*if\s*\(frontend\.presentAddress\s*!==\s*undefined\)\s*result\.present_address\s*=\s*frontend\.presentAddress;\n', '\n', c)
c = re.sub(r'\s*if\s*\(frontend\.permanentAddress\s*!==\s*undefined\)\s*result\.permanent_address\s*=\s*frontend\.permanentAddress;\n', '\n', c)

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)
