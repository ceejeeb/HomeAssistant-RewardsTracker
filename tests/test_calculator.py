"""Tests for the reward rules."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "custom_components" / "rewards_tracker"),
)

from calculator import (  # noqa: E402
    Pot,
    Rules,
    apply_interest,
    award_tick,
    deposit,
    settle,
    spend,
    withdraw,
)

RULES = Rules(ticks_per_star=5, stars_per_pound=3, daily_interest_percent=1)
TODAY = date(2026, 9, 29)


class RewardRulesTest(unittest.TestCase):
    def test_fifth_tick_becomes_a_star(self) -> None:
        pot = Pot(ticks=4)
        updated = award_tick(pot, RULES)
        self.assertEqual(updated.ticks, 0)
        self.assertEqual(updated.stars, 1)

    def test_third_star_becomes_money_on_the_same_tick(self) -> None:
        pot = Pot(ticks=4, stars=2)
        updated = award_tick(pot, RULES)
        self.assertEqual(updated.ticks, 0)
        self.assertEqual(updated.stars, 0)
        self.assertEqual(updated.balance, 1)

    def test_settle_converts_a_backlog(self) -> None:
        updated = settle(Pot(ticks=12, stars=4, interest_pence=250), RULES)
        self.assertEqual(updated.ticks, 2)
        self.assertEqual(updated.stars, 0)
        self.assertEqual(updated.balance, 2)
        self.assertEqual(updated.savings, 2)
        self.assertEqual(updated.interest_pence, 50)

    def test_deposit_and_withdraw_move_one_unit_and_leave_interest(self) -> None:
        start = Pot(balance=4, savings=10, interest_pence=40)
        saved = deposit(start)
        assert saved is not None
        self.assertEqual((saved.balance, saved.savings, saved.interest_pence), (3, 11, 40))
        back = withdraw(saved)
        assert back is not None
        self.assertEqual((back.balance, back.savings, back.interest_pence), (4, 10, 40))

    def test_deposit_and_withdraw_refuse_an_empty_side(self) -> None:
        self.assertIsNone(deposit(Pot(balance=0, savings=3)))
        self.assertIsNone(withdraw(Pot(balance=3, savings=0)))

    def test_spend_subtracts_the_cost(self) -> None:
        updated = spend(Pot(balance=3), 3)
        assert updated is not None
        self.assertEqual(updated.balance, 0)
        self.assertIsNone(spend(Pot(balance=2), 3))
        self.assertIsNone(spend(Pot(balance=5), 0))

    def test_first_interest_run_stamps_today_without_paying(self) -> None:
        updated = apply_interest(Pot(savings=10), RULES, TODAY)
        self.assertEqual(updated.savings, 10)
        self.assertEqual(updated.interest_pence, 0)
        self.assertEqual(updated.interest_last_paid, TODAY)

    def test_ten_units_reach_one_unit_of_interest_in_ten_days(self) -> None:
        start = Pot(savings=10, interest_last_paid=date(2026, 9, 19))
        updated = apply_interest(start, RULES, TODAY)
        self.assertEqual(updated.savings, 11)
        self.assertEqual(updated.interest_pence, 0)
        self.assertEqual(updated.interest_last_paid, TODAY)

    def test_three_units_leave_a_remainder_on_the_bar(self) -> None:
        start = Pot(savings=3, interest_last_paid=date(2026, 8, 26))
        updated = apply_interest(start, RULES, TODAY, max_days=40)
        self.assertEqual((TODAY - date(2026, 8, 26)).days, 34)
        self.assertEqual(updated.savings, 4)
        self.assertEqual(updated.interest_pence, 2)

    def test_a_large_day_pays_more_than_one_unit(self) -> None:
        start = Pot(savings=40, interest_pence=80, interest_last_paid=date(2026, 9, 28))
        updated = apply_interest(start, RULES, TODAY)
        self.assertEqual(updated.savings, 41)
        self.assertEqual(updated.interest_pence, 20)

    def test_catch_up_is_capped_at_31_days(self) -> None:
        start = Pot(savings=1, interest_last_paid=date(2026, 1, 1))
        updated = apply_interest(start, RULES, TODAY)
        self.assertEqual(updated.savings, 1)
        self.assertEqual(updated.interest_pence, 31)
        self.assertEqual(updated.interest_last_paid, TODAY)

    def test_same_day_does_not_pay_twice(self) -> None:
        start = Pot(savings=10, interest_pence=10, interest_last_paid=TODAY)
        self.assertEqual(apply_interest(start, RULES, TODAY), start)

    def test_zero_rate_marks_the_day_paid_without_backpay_later(self) -> None:
        paused = Rules(5, 3, 0)
        start = Pot(savings=10, interest_last_paid=date(2026, 9, 28))
        marked = apply_interest(start, paused, TODAY)
        self.assertEqual(marked.interest_pence, 0)
        self.assertEqual(marked.interest_last_paid, TODAY)
        resumed = apply_interest(marked, RULES, TODAY)
        self.assertEqual(resumed.interest_pence, 0)


if __name__ == "__main__":
    unittest.main()
