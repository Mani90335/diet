# FitPlan — Local Python Diet & Fitness Planner

A working personal diet/workout dashboard, with no Python package dependencies. Uses the Python standard library, SQLite, and a responsive HTML/CSS/JavaScript frontend.

## Run on your Mac or Windows computer

Requires **Python 3.10 or newer** (Python 3.11+ recommended for built-in `zoneinfo` timezone data, with your operating system's IANA timezone database).

```bash
cd fitplan-local
python3 server.py
```

Open **http://127.0.0.1:8000**. On Windows, run `py server.py` instead. On a Mac you can also double-click `start.command` if macOS permits it.

Keep the terminal open: **the website and reminder scheduler only run while the computer is on, awake, and the Python process is running.** Sleep or shutdown pauses scheduling; when the server restarts after your configured daily time, it sends the day's enabled reminder if it wasn't sent yet.

## Get started

1. Open **My profile & alerts** and save age, height, current weight, target, duration, metabolic-equation selection, activity, and diet preference.
2. Review the Dashboard and Weekly Plan. The app includes clearly illustrative sample recipes with approximate values only.
3. Open **Meal library** and either paste a public GitHub repository URL, import a local CSV/JSON/Markdown file, or add recipes manually.
4. Remove sample foods after importing your own foods (button in Meal library). Regenerate the plan after updating your library.
5. In **Progress**, log your weight.
6. Configure email SMTP to enable daily delivery.

## Built-in diet repository integration (November 2026)

The application now includes a **bundled, offline nutrition catalog** based on the exact three public plain-text lists at [Mani90335/diet](https://github.com/Mani90335/diet): `Breakfast`, `Curries`, and `Other food items` (no filename extensions).

- There are **45 distinct food names** (one duplicate Dosa in Breakfast, and Bread+milk appears in two files). Some items have both lunch and dinner slots, yielding **69 category-specific entries** in the meal library.
- Every entry has an assumed portion, estimated calories, protein, carbs, fat, fiber, calcium, iron, potassium and vitamin C. These are **illustrative assumptions**, not values found in the repository and not USDA/ICMR-verified per-recipe analyses. Cooking oil, ingredient quantities, brand, water content and yields can produce large variation. Do not interpret the displayed precision as evidence of measurement.
- The `Curries` file contains side dishes and ingredients rather than complete meals. The planner pairs curry entries with an assumed serving of rice or chapati for lunch/dinner, and labels the assumption in the generated plan.
- The `Other food items` list includes rice dishes, breads, beverages and snacks, assigned to plausible meal slots; these classifications are editable in the catalog JSON.
- `data/github_diet_estimates.json` stores estimates. Edit it to reflect your precise recipes, then restart the app to synchronize changed estimates into SQLite. The app preserves manually entered recipes.
- The public GitHub sync can import **extensionless numbered text lists** using the bundled catalog to match known food names. New unmatched foods are explicitly listed; their nutritional values are **not fabricated**. If the repository is offline or inaccessible, the bundled estimates still work without an internet connection.

**Goal calculation:** BMI = weight (kg) / height (m)², reported for adult screening only. Daily calorie estimates use Mifflin–St Jeor BMR, an activity multiplier, and a bounded goal deficit/surplus with warnings for questionable deadlines. BMI **does not directly determine** a calorie target. These calculations are broad population heuristics and should not be used as medical prescriptions.

## Importing GitHub meals

Enter a URL like `https://github.com/OWNER/REPOSITORY`. The import scans for file names containing **breakfast**, **lunch**, **dinner**, or **snack** with `.json`, `.csv`, `.md`, or `.txt` extensions, in folders or at the repository root. The files must include **name, calories, protein, carbs and fat per serving**. A meal's category comes from its filename if the row doesn't include `category`. GitHub import needs internet access, and unauthenticated GitHub API requests are rate-limited.

Import formats:

**CSV** (e.g., `breakfast.csv`):
```csv
name,calories,protein,carbs,fat,serving,tags
Idli with sambar,340,12,62,5,3 idlis + 1 cup sambar,vegetarian
Oats,310,11,48,8,1 bowl,vegan
```

**Markdown** (e.g., `lunch.md`):
```md
| name | calories | protein | carbs | fat | serving | tags |
| --- | --- | --- | --- | --- | --- | --- |
| Dal and rice | 620 | 22 | 99 | 14 | 1 plate | vegetarian |
```

**JSON** (e.g., `dinner.json`):
```json
[{"name":"Chapati and dal","category":"dinner","calories":530,"protein":19,"carbs":83,"fat":13,"serving":"1 plate","tags":"vegetarian"}]
```

Plain text lists without nutrient fields can be matched to **existing bundled estimates** for this particular repository; unfamiliar items are reported as unmatched instead of having nutrition invented. You may add nutrition fields to the files or import accurate recipes manually. Calories and macros depend on ingredients, quantity and cooking method. 

**Current importer limitations:** YAML is not supported; only simple Markdown tables with the documented columns are parsed; nested recipe JSON schemas must be flattened first. `tags` and comma-separated exclusion are keyword filters, not medical-grade allergen safety checks.

## Email reminders

Copy `.env.example` to `.env`, edit the SMTP values, restart the server, then in Profile enter your destination email, choose `Email`, enable daily reminders and set your time (Asia/Kolkata). For Gmail SMTP, use a suitable app password, not your normal account password. You can test with **Send test email**. The server delivers at most one automatic email per local calendar day, recording successful deliveries in SQLite. Test email explicitly forces a resend.

The server needs internet access for GitHub imports and sending notifications. Credentials stay on the server and should never be committed to Git.

## WhatsApp

An optional integration uses Meta's official WhatsApp Cloud API to send a **preapproved template**. You must configure `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TEMPLATE`, and a valid recipient phone number; that recipient must have opted in. Template payloads are sent without variables in this starter. To include the dynamic meal/workout text inside a WhatsApp template, you need to customize the template components, have them approved, and update `send_whatsapp()` accordingly. Choosing WhatsApp does **not** make the free-text preview available as a template message.

## How planning works

The server estimates BMR using the Mifflin-St Jeor equation and activity multipliers, then limits a requested daily energy deficit to 500 kcal or a surplus to 450 kcal, with baseline screening floors of 1500 kcal for the male equation or 1200 for the female equation. **These are generic guardrails, not individualized medical standards.** Changes in weight over time won't match a simple static energy calculation exactly. Protein uses a starter heuristic of 1.2 g/kg and is not a clinical prescription. The engine searches the imported meals for each category, choosing among approximate portions (0.5x, 1x, 1.5x, 2x), then reports discrepancies. The weekly workouts are general illustrative templates and are not adapted to injuries or training level.

The app does not promise to perfectly satisfy calorie or macro goals when your food library is incomplete, nor does it adjust intake automatically based on logged weight. You should review your plans and consult a clinician or dietitian when there are medical conditions, an eating disorder, pregnancy, or other specialized nutrition needs. This starter supports adult users only.

## Security and local access

It binds to `127.0.0.1` by default, so only your own computer can access it. It deliberately **does not implement login/authentication**. Do not expose it directly to the public internet or change its bind address to `0.0.0.0` without adding authentication, HTTPS, CSRF protection, rate limiting, secret management, and other hardening.

SQLite lives at `data/fitplan.db`. Back up that file to preserve your profile, records and recipes. The app requires no third-party Python dependencies and does not transmit health data to external services except information included in notifications you enable. GitHub fetching retrieves the public recipe files you request.

## Development tests

```bash
python3 -m unittest discover -s tests -v
```
