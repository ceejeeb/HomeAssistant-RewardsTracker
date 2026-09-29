# Rewards Tracker

A Home Assistant integration for a child's reward money. Add one entry per child. Each child gets ticks, stars, spending money, and a savings balance that earns interest.

## How the numbers work

A tick is one good thing. When the ticks reach that child's threshold, they become one star and the tick count goes back by that many. The default is 5 ticks to a star.

When the stars reach that child's threshold, they become 1 unit of spending money. The default is 3 stars to 1 unit. Both conversions happen on the same tick, so the star that completes the set becomes money immediately.

Deposit moves 1 unit from spending money into savings. Withdraw moves 1 unit back. Neither press changes the interest bar. A part-built unit of interest can only come back out after it has been paid into savings as a whole unit.

Savings earn the child's daily percent at 07:00 local time. At 1%, 10 units of savings earn 10 hundredths a day. When the hundredths reach 100, 1 unit is added to savings and the bar starts again. A unit paid as interest starts earning the next day. If Home Assistant was off, missed days are caught up on the next start, up to 31 days. The first time a child is added, today is marked as already paid, so interest starts the following morning.

Spending uses the list you configure on that child. Each option has a description, a cost, and an icon. The press subtracts the cost from spending money when the balance covers it.

## Install with HACS

1. Push this repository to GitHub.
2. In HACS, open Integrations, open the menu, and choose Custom repositories.
3. Paste the repository URL and choose Integration.
4. Download Rewards Tracker and restart Home Assistant.
5. Go to Settings, Devices and services, Add integration, and choose Rewards Tracker.

Before you publish the repository, replace `documentation` in `custom_components/rewards_tracker/manifest.json` with your repository URL. It is a placeholder at the moment.

## Install by copying the folder

Copy `custom_components/rewards_tracker` into your Home Assistant config folder so the path is `config/custom_components/rewards_tracker`. Restart Home Assistant, then add the integration as above.

Home Assistant 2025.1 or newer is required.

## Add a child

The first screen asks for the name, ticks per star, stars per unit of money, daily interest percent, and a currency symbol. The defaults are 5, 3, 1%, and £.

The next screen is the spend list. Add a way to spend, for example Buy Book at 3 with the icon `mdi:book-open-variant`, then finish. You can add more later. `mdi` icons work without anything else installed.

Each child appears as a device with five sensors: Ticks, Stars, Money, Savings, and Interest. Interest is the hundredths built toward the next unit, from 0 to 99.

## The card

On a normal dashboard the integration adds the card resource for you. Refresh the browser once after the first restart. Edit the dashboard, add a card, and choose Rewards Tracker. Pick that child's Money sensor.

```yaml
type: custom:rewards-tracker-card
entity: sensor.charlie_money
```

The card shows money, savings, the three progress bars, a Tick button, Deposit and Withdraw of 1, and one button per way to spend. A button is faded when that balance cannot cover it.

If the dashboard is in YAML mode, add the resource yourself:

```yaml
resources:
  - url: /rewards_tracker/rewards-tracker-card.js?v=0.1.0
    type: module
```

## Correct a mistake

The card cannot type a new balance. Open the integration, choose the child, and press Configure.

Rules and currency changes the thresholds, the interest percent, and the symbol. Ways to spend adds, edits, or removes rewards. Correct balances sets ticks, stars, spending money, savings, and the interest bar. Saving that screen converts any ticks or stars that are already past the threshold, and turns every 100 interest points into 1 unit of savings.

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
