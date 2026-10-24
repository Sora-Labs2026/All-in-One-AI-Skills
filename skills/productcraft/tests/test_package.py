from pathlib import Path
import importlib.util,unittest,json
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('checker',ROOT/'scripts'/'check_package.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class ProductCraftTest(unittest.TestCase):
 def test_package(self): self.assertEqual(mod.check(ROOT),0)
 def test_pattern_index(self):
  v=json.loads((ROOT/'references'/'pattern-index.json').read_text())
  self.assertGreater(len(v),0)
  self.assertEqual([x['id'] for x in v],list(range(1,len(v)+1)))
  self.assertEqual(len({x['title'] for x in v}),len(v))
  self.assertTrue(all(x['rule'] and x['guardrail'] for x in v))
 def test_ui_rules_index(self):
  ui=json.loads((ROOT/'references'/'ui-rules-index.json').read_text())
  ids=[r['id'] for r in ui['rules']]
  self.assertGreater(len(ids),0)
  self.assertEqual(len(ids),len(set(ids)))
  self.assertEqual(sum(c['rules'] for c in ui['categories']),len(ids))
  self.assertTrue(all(r['why'] and r['do'] and r['avoid'] for r in ui['rules']))
  self.assertTrue(all((ROOT/c['file']).is_file() for c in ui['categories']))
 def test_reference_screens(self):
  pages=sorted((ROOT/'examples').glob('*.html'))
  self.assertGreater(len(pages),0)
  index=(ROOT/'examples'/'README.md').read_text()
  self.assertTrue(all(f'`{p.name}`' in index for p in pages))
  self.assertFalse(any('://' in p.read_text().replace('http://www.w3.org/2000/svg','') for p in pages))
 def test_exactly_one_skill(self):
  self.assertEqual([p.relative_to(ROOT).as_posix() for p in ROOT.rglob('SKILL.md')],['SKILL.md'])
if __name__=='__main__':unittest.main()
