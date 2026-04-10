import pathlib

p = pathlib.Path('src/ats_backend/schemas/candidate.py')
c = p.read_text(encoding='utf-8')
c = c.replace('    remark: Optional[str] = Field(None, description="Candidate remarks or notes")\n    \n    @validator(\'phone\')', '    remark: Optional[str] = Field(None, description="Candidate remarks or notes")\n    other_details: Optional[Dict[str, Any]] = Field(None, description="Other details parsed from resume in JSON format")\n    \n    @validator(\'phone\')')
c = c.replace('    remark: Optional[str] = None\n    \n    @validator(\'phone\')', '    remark: Optional[str] = None\n    other_details: Optional[Dict[str, Any]] = None\n    \n    @validator(\'phone\')')
p.write_text(c, encoding='utf-8')

p = pathlib.Path('src/ats_backend/resume/models.py')
c = p.read_text(encoding='utf-8')
c = c.replace('    key_skill: Optional[str] = Field(None, description="Key skill summary")', '    key_skill: Optional[str] = Field(None, description="Key skill summary")\n    other_details: Dict[str, Any] = Field(default_factory=dict, description="Other details parsed from resume")')
c = c.replace('            "status": "ACTIVE"\n        }', '            "status": "ACTIVE",\n            "other_details": self.other_details\n        }')
p.write_text(c, encoding='utf-8')
