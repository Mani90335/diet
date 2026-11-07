import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import parse_food_text,calculations,validate_profile,normalize_category,make_day_plan,conn,init_db

PROFILE={'age':27,'height':175,'weight':78,'target':70,'days':120,'sex':'male','activity':'light','diet':'all','avoid':''}
class CoreTests(unittest.TestCase):
 def test_calories(self):
  m=validate_profile(PROFILE)
  self.assertGreater(m['calories'],1500)
  self.assertGreater(m['tdee'],m['bmr'])
 def test_unsafe_goal_is_limited(self):
  p={**PROFILE,'days':7,'target':40}
  m=calculations(p)
  self.assertGreater(len(m['warnings']),0)
  self.assertGreaterEqual(m['calories'],1500)
 def test_csv_import(self):
  data='name,calories,protein,carbs,fat\nIdli,200,8,35,4\n'
  self.assertEqual(parse_food_text(data,'breakfast.csv')[0]['name'],'Idli')
 def test_markdown_import(self):
  data='| name | calories | protein | carbs | fat |\n| --- | --- | --- | --- | --- |\n| Dosa | 300 | 8 | 40 | 9 |'
  self.assertEqual(len(parse_food_text(data,'breakfast.md')),1)
 def test_no_fake_nutrition(self):
  self.assertEqual(parse_food_text('Idli\nDosa\nEggs','breakfast.txt'),[])
 def test_json_import(self):
  data='[{"name":"Dal","calories":200,"protein":12,"carbs":20,"fat":6}]'
  self.assertEqual(len(parse_food_text(data,'lunch.json')),1)
 def test_invalid_profile(self):
  with self.assertRaises(ValueError):validate_profile({**PROFILE,'age':12})
 def test_category(self):self.assertEqual(normalize_category('snacks'),'snack')

if __name__=='__main__':unittest.main()

class RepositoryIntegrationTests(unittest.TestCase):
 def test_bundled_repository_entries(self):
  items=json.loads((Path(__file__).resolve().parents[1]/'data'/'github_diet_estimates.json').read_text())
  self.assertEqual(len(items),69)
  self.assertEqual(len(set(i['name'].lower().replace(' ','') for i in items)),45)
  for item in items:
   for field in ('calories','protein','carbs','fat','fiber_g','calcium_mg','iron_mg','potassium_mg','vitamin_c_mg','serving','estimate_note'):
    self.assertIn(field,item)
 def test_numbered_extensionless_repository_text(self):
  from server import parse_numbered_items
  self.assertEqual(parse_numbered_items('1. Idli\n2. Dosa\n3. Dosa\n4. Egg boiled\n5. '),['Idli','Dosa','Egg boiled'])
 def test_bmi_and_goal(self):
  metrics=calculations(PROFILE)
  self.assertAlmostEqual(metrics['bmi'],25.5,places=1)
  self.assertGreater(metrics['calories'],0)
