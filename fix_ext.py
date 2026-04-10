import re

path = 'src/ats_backend/resume/extractor.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# remove patterns
text = re.sub(r'        self\.present_address_pattern = re\.compile\(r"\\b\(\?:present\|current\)\\s\+address\\s\*\\[:\\-\]\?\\s\*\(\.\+\)", re\.IGNORECASE\)\n', '', text)
text = re.sub(r'        self\.permanent_address_pattern = re\.compile\(r"\\bpermanent\\s\+address\\s\*\\[:\\-\]\?\\s\*\(\.\+\)", re\.IGNORECASE\)\n', '', text)

# remove extract_data calls
text = text.replace(
"""        present_address, permanent_address = self._extract_addresses(text)
        previous_employment = self._extract_previous_employment(text)
        key_skill = ", ".join([skill.name for skill in skills[:8]]) if skills else None
        if present_address and not contact_info.location:
            contact_info.location = present_address.split(",")[0].strip()""",
"""        previous_employment = self._extract_previous_employment(text)
        key_skill = ", ".join([skill.name for skill in skills[:8]]) if skills else None"""
)

# remove result dict keys
text = text.replace("'present_address': present_address,", "")
text = text.replace("'permanent_address': permanent_address,", "")

# remove _extract_addresses method
text = re.sub(r'    def _extract_addresses\(self, text: str\):.*?(?=\n    def _extract_salary_info)', '', text, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
