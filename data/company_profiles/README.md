# company_profiles/

One YAML file per company analyzed. Auto-created by hiring-manager-agent and kigyou-bunseki.

## Naming Convention

`{company-name-slug}.yml` — lowercase, hyphens, no special chars.

Examples:
- `bloom-tech.yml`
- `rakuten-group.yml`
- `mercari.yml`

## Schema

See `../../_shared/schemas.yml` → `company_profile` for the full field list.

## Usage

matching-simulator and company-battlecard read these files automatically.
When starting a session, paste the company name and the skill will look up the file.
