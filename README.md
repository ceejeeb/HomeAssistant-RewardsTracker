# Rewards Tracker

A Home Assistant integration for a child's reward money. Add one entry per child. Each child gets ticks, stars, spending money, and a savings balance that earns interest.

## How the numbers work

A full first tier becomes one of the second tier. A full second tier adds the amount of spending money you chose. The defaults are 5 of the first tier, named Ticks with a check icon, then 3 of the second tier, named Stars with a star icon, paying 1 unit of money.

When the second tier fills, it pays out and the count of that tier drops by its threshold. Both conversions happen on the same award, so the one that completes the set becomes money immediately.

Deposit moves 1 unit from spending money into savings. Withdraw moves 1 unit back. Neither press changes the interest bar. A part-built unit of interest can only come back out after it has been paid into savings as a whole unit.

Savings earn the percent you set, over the period you set. A separate timer decides how often that interest is worked out. At 1% every 1 day, calculated every hour, each hour adds one twenty-fourth of that day's interest and the bar moves. At 1% every 1 day, 10 units of savings earn 10 hundredths a day. When the hundredths reach 100, 1 unit is added to savings and the bar starts again. A unit paid as interest starts earning on the next calculation. If Home Assistant was off, missed time is caught up on the next start, up to 31 days. The first time a child is added, the clock starts then, so nothing is paid for time before that.

Spending uses the list you configure on that child. Each option has a description, a cost, and an icon. The press subtracts the cost from spending money when the balance covers it.

## Install with HACS

1. Push this repository to GitHub.
2. In HACS, open Integrations, open the menu, and choose Custom repositories.
3. Paste the repository URL and choose Integration.
4. Download Rewards Tracker and restart Home Assistant.
5. Go to Settings, Devices and services, Add integration, and choose Rewards Tracker.

## Install by copying the folder

Copy `custom_components/rewards_tracker` into your Home Assistant config folder so the path is `config/custom_components/rewards_tracker`. Restart Home Assistant, then add the integration as above.

Home Assistant 2025.1 or newer is required.

## Add a child

The first screen can link a Home Assistant person. That person's name is used, and their picture shows on the card. Leave the person empty to type a name instead. Then choose a name, icon, and count for each tier, how much money a full second tier pays, the currency symbol, and the interest. Interest is a percent over a period, such as 1% every 1 day, plus a separate calculation interval, such as every hour. The defaults are Ticks, a check icon, 5, then Stars, a star icon, 3, paying £1 at 1% every 1 day, calculated every day.

The next screen is the spend list. Add a way to spend, for example Buy Book at 3 with the icon `mdi:book-open-variant`, then finish. You can add more later. `mdi` icons work without anything else installed.

Each child appears as a device with five sensors: Ticks, Stars, Money, Savings, and Interest. Interest is the hundredths built toward the next unit, from 0 to 99.

## The card

On a normal dashboard the integration adds the card resource for you. Refresh the browser once after the first restart. Edit the dashboard, add a card, and choose Rewards Tracker. Pick that child's Money sensor.

```yaml
type: custom:rewards-tracker-card
entity: sensor.charlie_money
```

The card shows a large picture and name, with a coloured button to award one of the first tier. Ticks sit on the left and stars on the right, with a curve between them and another curve down to the bank. Spend choices, plus save and take-out, are boxes three across. Savings sits under that, with the interest bar inside the box. A button is faded when that balance cannot cover it.

If the dashboard is in YAML mode, add the resource yourself:

```yaml
resources:
  - url: /rewards_tracker/rewards-tracker-card.js?v=0.1.6
    type: module
```

## Correct a mistake

The card cannot type a new balance. Open the integration, choose the child, and press Configure.

Rules and currency changes the thresholds, the interest percent, how often that percent applies, how often it is calculated, and the symbol. Ways to spend adds, edits, or removes rewards. Correct balances sets ticks, stars, spending money, savings, and the interest bar. Saving that screen converts any ticks or stars that are already past the threshold, and turns every 100 interest points into 1 unit of savings.

## Services

Actions are available on any of the child's sensors. The Money sensor is the easiest target. Reward ids are in that sensor's `rewards` attribute.

```yaml
action: rewards_tracker.award_tick
target:
  entity_id: sensor.charlie_money
```

```yaml
action: rewards_tracker.deposit
target:
  entity_id: sensor.charlie_money
```

```yaml
action: rewards_tracker.withdraw
target:
  entity_id: sensor.charlie_money
```

```yaml
action: rewards_tracker.spend
target:
  entity_id: sensor.charlie_money
data:
  reward_id: a1b2c3d4
```

Balances are stored in `.storage/rewards_tracker.<entry id>` inside the Home Assistant config folder, so they are part of a normal backup.
