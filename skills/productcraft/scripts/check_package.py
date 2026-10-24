#!/usr/bin/env python3
"""Offline static integrity checker for the ProductCraft skill package. Requires Python standard library."""
import argparse, json, re, pathlib, sys

PATTERN_FIELDS = ('id', 'title', 'category', 'principle', 'rule', 'guardrail')
UI_RULE_FIELDS = ('id', 'category', 'title', 'why', 'do', 'avoid')

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
    ui_rules=[]
    ui_index=root/'references'/'ui-rules-index.json'
    if not ui_index.is_file(): failures.append('ui-rules-index.json missing')
    else:
        try: ui=json.loads(ui_index.read_text())
        except Exception as e: failures.append('bad UI rules JSON '+str(e)); ui={}
        ui_rules=ui.get('rules',[])
        if not ui_rules: failures.append('no UI rules indexed')
        ids=[r.get('id','') for r in ui_rules]
        if len(ids)!=len(set(ids)): failures.append('duplicate UI rule id')
        for c in ui.get('categories',[]):
            f=root/c.get('file','')
            mine=[r for r in ui_rules if r.get('id','').startswith(c.get('prefix','?')+'-')]
            if [r['id'] for r in mine]!=[f"{c['prefix']}-{n:02d}" for n in range(1,len(mine)+1)] or len(mine)!=c.get('rules'): failures.append(f"UI rule ids not consecutive for {c.get('prefix')}")
            if not f.is_file(): failures.append(f"missing UI rules file {c.get('file')}"); continue
            text=f.read_text()
            for r in mine:
                if f"## {r['id']}. {r.get('title','')}" not in text: failures.append(f"UI rule {r['id']} not in {c['file']}")
        if sum(c.get('rules',0) for c in ui.get('categories',[]))!=len(ui_rules): failures.append('UI rules not all assigned to a category')
        for r in ui_rules:
            missing=[f for f in UI_RULE_FIELDS if not r.get(f)]
            if missing: failures.append(f"UI rule {r.get('id')} missing {', '.join(missing)}")
    for p in ['WORKSPACE-SETUP-PROMPT.txt','README.md','LICENSE','modules/product-design.md','modules/interaction-feedback.md','modules/forms-conversion.md','modules/data-and-product-surfaces.md','modules/responsive-accessibility.md','modules/ethical-persuasion.md','assets/review-template.md','modules/launchguard/references/security-baseline.md','modules/ui-rules.md','modules/language-choice.md']:
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
    print(f'PASS: one skill entry, {len(patterns)} patterns, {len(ui_rules)} UI rules, 3 specialist modules, guides and tools present')
    return 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default=pathlib.Path(__file__).resolve().parents[1]);sys.exit(check(p.parse_args().root))
