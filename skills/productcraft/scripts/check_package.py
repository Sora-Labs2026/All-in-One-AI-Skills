#!/usr/bin/env python3
"""Offline static integrity checker for the ProductCraft skill package. Requires Python standard library."""
import argparse, json, re, pathlib, sys

PATTERN_FIELDS = ('id', 'title', 'category', 'principle', 'rule', 'guardrail')

def check(root):
    root=pathlib.Path(root)
    failures=[]
    if not (root/'SKILL.md').exists(): failures.append('SKILL.md missing')
    else:
        sk=(root/'SKILL.md').read_text()
        if not re.search(r'^name:\s*productcraft\s*$',sk,re.M): failures.append('frontmatter skill name does not equal productcraft')
        if not sk.startswith('---\n'): failures.append('skill YAML frontmatter missing')
    nested=list(root.rglob('SKILL.md'))
    if len(nested)!=1: failures.append(f'expected exactly one SKILL.md, got {len(nested)}')
    index=root/'references'/'pattern-index.json'
    if not index.is_file(): failures.append('pattern-index.json missing'); patterns=[]
    else:
        try: patterns=json.loads(index.read_text())
        except Exception as e: failures.append('bad JSON '+str(e)); patterns=[]
    if not patterns: failures.append('no patterns indexed')
    if [p.get('id') for p in patterns]!=list(range(1,len(patterns)+1)): failures.append('pattern ids not consecutive from 1')
    titles=[p.get('title','') for p in patterns]
    if len(titles)!=len(set(titles)): failures.append('duplicate pattern title')
    for p in patterns:
        missing=[f for f in PATTERN_FIELDS if not p.get(f)]
        if missing: failures.append(f"pattern {p.get('id')} missing {', '.join(missing)}")
    if not (root/'references'/'pattern-library.md').is_file(): failures.append('pattern-library.md missing')
    else:
        lib=(root/'references'/'pattern-library.md').read_text()
        for p in patterns:
            if f"## {p.get('id',0):02d}. {p.get('title','')}" not in lib: failures.append(f"pattern {p.get('id')} not in pattern-library.md")
    for p in ['WORKSPACE-SETUP-PROMPT.txt','README.md','LICENSE','modules/product-design.md','modules/interaction-feedback.md','modules/forms-conversion.md','modules/data-and-product-surfaces.md','modules/responsive-accessibility.md','modules/ethical-persuasion.md','assets/review-template.md','modules/launchguard/references/security-baseline.md']:
        if not (root/p).is_file(): failures.append('missing '+p)
    for slug in ['ui-distiller','credential-shield','launchguard']:
        d=root/'modules'/slug
        if not (d/'GUIDE.md').is_file(): failures.append('missing module guide '+slug)
        if not (d/'references').is_dir(): failures.append('missing specialist references '+slug)
    for slug in ['credential-shield','launchguard']:
        d=root/'modules'/slug
        if not (d/'scripts').is_dir() or not (d/'tests').is_dir(): failures.append('missing executable/tests for '+slug)
    if failures:
        print('FAIL',len(failures))
        for x in failures: print('-',x)
        return 1
    print(f'PASS: one skill entry, {len(patterns)} patterns, 3 specialist modules, guides and tools present')
    return 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default=pathlib.Path(__file__).resolve().parents[1]);sys.exit(check(p.parse_args().root))
