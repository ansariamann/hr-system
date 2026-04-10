import os

path = 'src/ats_backend/api/candidates.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open(path, 'w', encoding='utf-8') as f:
    for line in lines:
        if 'present_address=candidate_data_dict.get(' in line:
            continue
        if 'permanent_address=candidate_data_dict.get(' in line:
            continue
        f.write(line)
