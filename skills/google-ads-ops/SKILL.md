---
name: google-ads-ops
description: Use when an agent manages a Google Ads account through an MCP server or the Google Ads API v23: creating or editing campaigns, budgets, ads and conversions, pulling GAQL reports, or doing keyword research and forecasts. Covers the v23 breaking changes, the Android-installs reporting trap, working mutation templates, and spend guardrails that keep an agent from burning money.
---

# Google Ads ops for agents (API v23)

Hard-won notes from running a real Google Ads account with an agent over MCP.
Every gotcha below cost a live debugging cycle. Written for the
[google-ads-mcp](https://github.com/edgar-durand/google-ads-mcp) server (API
v23), but the API facts hold for any client.

## 0. Before anything: fill in your account

Ask the user for these and keep them in the conversation. Never guess an ID.

- **Operating customer ID** (the client account, 10 digits, no hyphens). With a
  manager account (MCC), set `GOOGLE_ADS_LOGIN_CUSTOMER_ID` to the MCC and
  operate on the client ID.
- **API access level of the Google Cloud project** behind the service account
  or OAuth client: *Test*, *Explorer* (2,880 ops/day, **no** Keyword
  Planner), *Basic* (15,000 ops/day, Keyword Planner works) or *Standard*.
  It is shown and requested on the Google Ads API page of the Cloud Console.
- **No developer token.** Google retired them on 2026-09-09: the API ignores
  the header and a future version will reject it. Don't ask the user for one.
  Prefer a **service account** added as a user of the Ads account; an OAuth
  refresh token also works.
- **Which conversion actions are primary** (query them, section 4).
- **Campaigns the agent must never touch** (brand campaigns, anything the user
  manages by hand).

## 1. Spend guardrails (non-negotiable)

An agent with Ads write access can spend real money in one call. Follow these
every time:

1. **Never create or modify anything that spends money without an explicit
   instruction that names a budget AND a duration.** State the worst case
   (`daily_budget × days`) before acting and keep it within what was approved.
2. **Create campaigns `PAUSED`**, read the created settings back with a query,
   then enable.
3. **Run atomic mutations with `validate_only: true` first.** Execute only
   after validation passes.
4. **Never touch billing, payments or account-level settings.**
5. **Budgets are daily, in micros** (USD × 1,000,000). Google may spend up to 2×
   the daily budget on a single day, but with an end date the period total is
   capped at `daily × days`. **Always set an end date on tests.**
6. Read-only reporting and forecasting need no confirmation.

## 2. API v23 breaking changes (v20 is blocked by Google)

- **Auth without a developer token** needs the Python `google-ads` library
  **≥ 34**. Older versions refuse to load a config that lacks
  `developer_token`.

- **`Campaign.start_date` / `end_date` no longer exist.** Use
  `start_date_time` / `end_date_time` in `"yyyy-MM-dd HH:mm:ss"` format on
  create and update.
- **`campaign.contains_eu_political_advertising` is required** on campaign
  create. Use `"DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING"` unless the ads are
  political.
- **Keyword forecasting moved.** In v23 `KeywordPlanService` only has
  `mutate_keyword_plans`. `GenerateForecastMetrics`,
  `GenerateForecastCurve` and `GenerateHistoricalMetrics` live on
  **`KeywordPlanIdeaService`**. Don't build a KeywordPlan tree to forecast.
- **Audience insights shapes changed:** `BasicInsightsAudience` became
  `InsightsAudience`, `country_location` became `country_locations`, and
  user interests go through `topic_audience_combinations`.

## 3. Mutation gotchas

- **`update_mask` is a plain camelCase string**, comma-separated:
  `"update_mask": "amountMicros,name"`. `{"paths": [...]}` fails with
  "FieldMask JSON value not a string" and snake_case fails with "must not
  contain _".
- **Use temporary resource names in one atomic mutate** to create linked
  objects together: `-1` budget, `-2` campaign, `-3` ad group, referenced as
  `customers/<id>/campaignBudgets/-1` and so on.
- **Reports: prefer the streaming search** (`search_stream`). It avoids paging
  state and is the path that has proven reliable.

### Working App-campaign template (installs)

One `atomic_mutate`, in this order:

1. `campaign_budget` `{resource_name: -1, amount_micros, delivery_method: STANDARD, explicitly_shared: false}`
2. `campaign` `{resource_name: -2, advertising_channel_type: MULTI_CHANNEL,
   advertising_channel_sub_type: APP_CAMPAIGN, status: PAUSED,
   contains_eu_political_advertising, maximize_conversions: {},
   app_campaign_setting: {app_id, app_store: GOOGLE_APP_STORE | APPLE_APP_STORE,
   bidding_strategy_goal_type: OPTIMIZE_INSTALLS_WITHOUT_TARGET_INSTALL_COST},
   start_date_time, end_date_time}`
3. `campaign_criterion` location, e.g. `geoTargetConstants/2840` (US)
4. `campaign_criterion` language, e.g. `languageConstants/1000` (English)
5. `ad_group` `{resource_name: -3, status: ENABLED}`
6. `ad_group_ad` with `app_ad`: 2 to 5 headlines (≤ 30 chars), 1 to 5
   descriptions (≤ 90 chars)

`app_id` is the Play package name (`com.example.app`) or the numeric App Store
ID.

## 4. The Android-installs trap: "0 conversions" on a working campaign

A Google Play App campaign can show **0 in `metrics.conversions` while it is
delivering installs**. One real campaign read 0 conversions while it had 25
installs at about $1 CPI. Anyone reading only the default column would have
killed it.

- The system action **"Android installs (all other apps)"**
  (`ANDROID_INSTALLS_ALL_OTHER_APPS`) is often enabled with
  `include_in_conversions_metric: false`, so Play installs never enter
  `metrics.conversions`.
- **That field is immutable.** Mutating it returns "The field attempted to be
  mutated is immutable". Don't retry.
- **Don't "fix" it by enabling Firebase Android `first_open` as well.** Both
  would count the same install (`all_conversions` double counts).

**The fix is the query.** For Android installs always read `all_conversions`:

```sql
SELECT campaign.name, segments.conversion_action_name, segments.date,
       metrics.all_conversions, metrics.cost_micros
FROM campaign
WHERE segments.date DURING LAST_7_DAYS
```

Report Android CPI as `cost_micros / 1e6 / all_conversions`. Never conclude
"0 conversions = failing" without checking `all_conversions`. iOS first-open
from Firebase usually *is* in the conversions metric, so iOS reads normally.

Imported GA4/Firebase conversions often sit as `HIDDEN` actions. "Importing"
one is flipping its status to `ENABLED` through the API (the Ads UI wizard is
unreliable). List them first:

```sql
SELECT conversion_action.id, conversion_action.name, conversion_action.type,
       conversion_action.status, conversion_action.include_in_conversions_metric
FROM conversion_action
```

## 5. Reporting recipes (GAQL)

```sql
-- Campaign performance
SELECT campaign.id, campaign.name, campaign.status, metrics.impressions,
       metrics.clicks, metrics.cost_micros, metrics.conversions,
       metrics.all_conversions
FROM campaign
WHERE segments.date DURING LAST_7_DAYS
ORDER BY metrics.cost_micros DESC
```

- Per day: add `segments.date` to the SELECT.
- `cost_micros / 1,000,000` = account currency. Always state the period.

## 6. Keyword research and forecasting

Needs **Basic** access or above on the Cloud project (Explorer returns nothing). Planning RPCs are
rate limited to about **1 request per second**.

| Need | Call |
|---|---|
| Discover keywords (seeds are expanded) | `generate_keyword_ideas` from keywords / URL / site |
| Volume for an exact list (no expansion) | `generate_keyword_historical_metrics` |
| Clicks / CTR / CPC at a daily budget | `generate_keyword_forecast_metrics` |

Typical args: `language="languageConstants/1000"`,
`geo_target_constants=["geoTargetConstants/2840"]`,
`keyword_plan_network="GOOGLE_SEARCH"`, `currency_code`, and
`daily_budget_micros`. Forecast dates must be **in the future**.

**Forecasting spends nothing and creates nothing.** It is safe under the
guardrails.

Gotchas:

1. **Per-keyword or per-ad-group `max_cpc_bid_micros` only work with
   `MANUAL_CPC`.** With `MAXIMIZE_CLICKS` / `MAXIMIZE_CONVERSIONS` the call
   fails with `keyword_plan_idea_error: INVALID_VALUE` and **no field path**.
   Under automated strategies pass the bid as the strategy ceiling.
2. **proto-plus messages are falsy when every field is at its default.** An
   `if not metrics` check silently turns a real all-zero forecast into `{}`.
   Test `is None`.
3. **Forecast cost ≈ `daily_budget × days`** whenever there is inventory: the
   forecast spends the budget. The useful numbers are **CTR and average CPC**.
4. **A zero forecast is an answer, not an error.** Either the bid is under the
   auction floor or Google has no ad inventory for those terms. Long-tail
   product terms often have real search volume and **zero** buyable
   inventory, so a Search campaign built on them spends $0 and gets nothing.

**Compare channels on cost per install, not cost per click.** If an App
campaign already gets installs at CPI X, a Search campaign whose CPC alone is
above X will almost always lose once click-to-install drop-off is counted.
Forecast before spending on Search.

## 7. Running the MCP server lean

Mounting every tool group floods the agent's context. Mount what the task
needs:

```bash
uv run main.py --groups core                               # campaigns, budgets, ads, GAQL
uv run main.py --groups core --servers keyword_plan_idea   # + keyword research (about 30 tools)
```
