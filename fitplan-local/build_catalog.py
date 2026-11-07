"""Bundled transcription and illustrative nutrition assumptions for Mani90335/diet.
Numbers are generic recipe estimates, NOT values in the source repository or a verified analysis.
"""
import json
from pathlib import Path
# title, portion, kcal, protein, carbs, fat, fiber, calcium mg, iron mg, potassium mg, vitamin C mg, diet tags
breakfast=[
('Idli','3 medium idlis (150 g), no chutney',195,6,42,1,2,35,1,120,0,'vegan'),
('Dosa','1 medium plain dosa (120 g), 1 tsp oil',210,5,31,7,2,25,1.2,110,0,'vegan'),
('Egg boiled','2 large boiled eggs',156,13,1,11,0,55,1.8,126,0,'egg'),
('Poha','1 bowl cooked (200 g), peanuts and 1 tsp oil',300,7,49,9,4,25,2,180,8,'vegan peanuts'),
('Muesli','50 g plain muesli + 150 ml milk',285,11,43,8,5,205,2.5,330,2,'vegetarian dairy nuts'),
('Bread+milk','2 wheat bread slices + 200 ml milk',260,12,36,8,4,260,1.8,350,1,'vegetarian dairy wheat'),
('Bread omelette','2 bread slices + 2-egg omelette, 1 tsp oil',355,19,30,17,4,95,2.8,265,3,'egg wheat'),
('Carrot juice','250 ml unsweetened carrot juice',95,2,22,0.5,2,45,0.6,550,8,'vegan'),
('Boiled chicken','150 g cooked skinless chicken breast',248,46,0,5,0,20,1.2,390,0,'nonveg chicken'),
('Oats masala','50 g dry oats cooked with veg, 1 tsp oil',290,10,41,10,7,50,2.8,310,12,'vegan'),
('Sweet potato','200 g boiled sweet potato',172,3,40,0.3,6,60,1.2,460,25,'vegan'),
('Egg omelette','2 eggs, onion, 1 tsp oil',210,13,4,16,1,70,2,180,3,'egg'),
('Overnight soaked oats','50 g oats + 150 ml milk + 1 tsp chia',325,14,44,11,8,260,3,400,1,'vegetarian dairy'),
('Oats banana shake','40 g oats + 1 medium banana + 200 ml milk',355,14,62,7,7,260,2.3,680,10,'vegetarian dairy'),
('Ragi java','40 g ragi flour + 200 ml milk, no sugar',260,11,41,6,4,380,2.1,340,1,'vegetarian dairy'),
('Sprouts fry','150 g moong sprouts + 1 tsp oil + veg',175,11,23,5,7,50,2,370,20,'vegan'),
('Oats dosa','2 small oat dosas, 50 g dry oats, 1 tsp oil',270,9,39,9,6,48,2.6,220,2,'vegan'),
('Rice flour atlu','2 medium rice-flour atlu, 1 tsp oil',265,4,48,6,1,16,0.5,70,0,'vegan'),
('Roasted ground nuts','30 g roasted peanuts',175,8,5,15,3,28,1.3,200,0,'vegan peanuts'),
('Protein shake','1 scoop whey (30 g) + water; check product label',120,24,3,2,0,125,0.4,160,0,'dairy whey'),
('Banana protein shake','1 banana + 1 scoop whey + 200 ml milk',345,33,39,7,3,370,0.9,650,10,'dairy whey')]
curries=[
('Egg fry','2 eggs masala-fried with onion, 1 tsp oil',240,14,8,17,2,75,2.2,260,7,'egg'),
('Egg onion soup','1 bowl (250 ml), 1 egg and onion',125,8,10,6,1,42,0.9,185,4,'egg'),
('Tomato','1 bowl tomato curry (180 g), 1 tsp oil',125,3,18,5,4,38,1,410,22,'vegan'),
('Bottle guard','1 bowl bottle gourd curry (180 g), 1 tsp oil',105,2,13,5,3,45,0.6,300,10,'vegan'),
('Beerakaya','1 bowl ridge gourd curry (180 g), 1 tsp oil',110,3,13,5,3,52,0.8,300,10,'vegan'),
('Chicken','1 bowl chicken curry (200 g, ~100 g cooked meat)',310,29,10,17,2,42,1.8,420,8,'nonveg chicken'),
('Egg tomato','2 eggs with tomato gravy (200 g)',235,15,11,14,3,90,2.4,390,15,'egg'),
('Millmaker','1 bowl soya chunks curry (~45 g dry chunks)',235,25,19,7,7,120,5,480,8,'vegan soy'),
('Dall- 3 types','1 bowl cooked dal (180 g), mild tadka',205,11,29,5,8,55,2.5,420,4,'vegan'),
('Aloo','1 bowl potato curry (180 g), 1 tsp oil',195,4,33,6,4,35,1.1,650,15,'vegan')]
other=[
('egg fried rice','1 plate (250 g), 1 egg, 1 tsp oil',420,14,65,12,3,48,2.1,240,5,'egg'),
('Egg chapathi roll','2 chapatis + 2 eggs + vegetables',460,22,49,19,7,110,3.5,390,12,'egg wheat'),
('Curd rice ( overnight)','1 bowl (250 g), refrigerated safely',340,10,58,8,2,220,0.9,360,1,'vegetarian dairy'),
('Bread +milk','2 wheat bread slices + 200 ml milk',260,12,36,8,4,260,1.8,350,1,'vegetarian dairy wheat'),
('Fried rice','1 plate veg fried rice (250 g), 2 tsp oil',410,8,69,12,5,45,1.6,290,10,'vegan'),
('Air fryer chicken breast','150 g cooked chicken breast + 1 tsp oil',290,46,0,10,0,20,1.2,390,0,'nonveg chicken'),
('Coconut water','250 ml unsweetened coconut water',48,1,11,0,0,40,0.6,470,6,'vegan'),
('ABC juice','250 ml apple-beet-carrot juice, unsweetened',130,2,30,0.5,2,35,1.1,430,10,'vegan'),
('Tomato soup','250 ml homemade tomato soup, 1 tsp oil',125,3,19,4.5,3,42,1,470,18,'vegan'),
('Chicken soup','250 ml chicken vegetable soup',165,20,9,5,2,40,0.9,350,8,'nonveg chicken'),
('Millmaker roti','2 wheat rotis stuffed with 35 g dry soya chunks',365,24,53,7,10,120,4.5,420,4,'vegan soy wheat'),
('Oats roti','2 medium rotis, 55 g oats flour, 1 tsp oil',265,9,40,8,6,45,2.5,230,0,'vegan'),
('Veg pulao','1 plate (250 g) rice and vegetables, 1 tsp oil',370,8,66,8,5,55,1.7,310,15,'vegan'),
('Sprouts fry- dinner','200 g moong sprouts + 1 tsp oil + vegetables',220,14,29,6,9,65,2.8,470,24,'vegan'),
('Canbage carrot cucumber curd salad','200 g cabbage-carrot-cucumber salad + 100 g curd',180,8,22,7,5,190,0.8,510,35,'vegetarian dairy')]

def make(entries, category, collection, categories=None):
    out=[]
    for name, serving, kcal,protein,carbs,fat,fiber,calcium,iron,potassium,vit_c,tags in entries:
        for cat in (categories or [category]):
            out.append(dict(name=name,category=cat,source_file=collection,calories=kcal,protein=protein,carbs=carbs,fat=fat,
                fiber_g=fiber,calcium_mg=calcium,iron_mg=iron,potassium_mg=potassium,vitamin_c_mg=vit_c,
                serving=serving,tags=tags,estimate=True,
                estimate_note='Illustrative typical-portion estimate; not verified for your recipe. Oil, ingredients, and portion sizes change values.'))
    return out
catalog=make(breakfast,'breakfast','Breakfast')+make(curries,'lunch','Curries',['lunch','dinner'])
for tup in other:
    n=tup[0].lower()
    cats=['snack'] if any(k in n for k in ('water','juice')) else (['lunch','dinner'] if any(k in n for k in ('rice','roll','roti','pulao','breast','sprouts fry- dinner')) else ['snack','dinner'])
    catalog+=make([tup],cats[0],'Other food items',cats)
file=Path(__file__).parent/'data'/'github_diet_estimates.json'
file.write_text(json.dumps(catalog,indent=2,ensure_ascii=False)+'\n')
print('entries',len(catalog),'unique',len({x['name'].lower().replace(' ','') for x in catalog}))
