import pathlib

p = pathlib.Path('alembic/versions/1297a549e631_add_other_details_to_candidates.py')
c = p.read_text(encoding='utf-8')

header = c.split('def upgrade() -> None:')[0]

new_content = header + """def upgrade() -> None:
    op.add_column('candidates', sa.Column('other_details', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('candidates', 'other_details')
"""

p.write_text(new_content, encoding='utf-8')
