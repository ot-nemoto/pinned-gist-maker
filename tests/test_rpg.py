import copy
import random
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import ranking  # noqa: E402
import rpg  # noqa: E402

WORLD = rpg.load_world()
DAY = date(2026, 10, 6)


def play(days, contributions=3, seed=0):
    state = rpg.new_state(WORLD)
    for i in range(days):
        rpg.advance(WORLD, state, DAY + timedelta(days=i + seed * 1000), contributions)
    return state


class WorldTest(unittest.TestCase):
    def test_layout(self):
        areas = WORLD["areas"]
        self.assertEqual(areas[0]["start"], 0)
        for a, b in zip(areas, areas[1:]):
            self.assertEqual(a["end"] + 1, b["start"])
        self.assertEqual(WORLD["total"], sum(a["length"] for a in areas))

    def test_steps_for(self):
        self.assertEqual([rpg.steps_for(WORLD, c) for c in (0, 1, 2, 3, 5, 6, 40)], [0, 1, 1, 2, 2, 3, 3])


class AdvanceTest(unittest.TestCase):
    def test_same_day_is_processed_once_and_deterministic(self):
        a, b = rpg.new_state(WORLD), rpg.new_state(WORLD)
        self.assertTrue(rpg.advance(WORLD, a, DAY, 3))
        self.assertFalse(rpg.advance(WORLD, a, DAY, 3))  # 同じ日は進めない
        rpg.advance(WORLD, b, DAY, 3)
        self.assertEqual(a, b)  # 同じ日・同じ周回なら同じ結果
        self.assertEqual(a["day"], 1)

    def test_rest_day_heals_and_does_not_move(self):
        state = rpg.new_state(WORLD)
        state["hero"]["hp"] = 1
        rpg.advance(WORLD, state, DAY, 0)
        self.assertEqual(state["pos"], 0)
        self.assertGreater(state["hero"]["hp"], 1)
        self.assertIn(state["last"]["events"][0], WORLD["rest"])

    def test_moves_by_steps(self):
        state = rpg.new_state(WORLD)
        rpg.advance(WORLD, state, DAY, 6)
        self.assertEqual(state["pos"], 3)

    def test_boss_blocks_until_defeated(self):
        state = rpg.new_state(WORLD)
        area = WORLD["areas"][0]
        state["pos"] = area["end"] - 1
        state["hero"]["hp"] = 1
        state["hero"]["potions"] = 0
        rpg.advance(WORLD, state, DAY, 6)  # 弱いまま挑んで負ける
        self.assertEqual(state["pos"], area["start"])  # 町に戻される
        self.assertEqual(state["deaths"], 1)
        self.assertNotIn(area["name"], state["boss_cleared"])

    def test_fall_halves_gold(self):
        state = rpg.new_state(WORLD)
        state["pos"] = WORLD["areas"][1]["start"] + 5
        state["hero"]["gold"] = 101
        day = rpg.Day(WORLD, state, random.Random(0))
        day.fall()
        self.assertEqual((state["pos"], state["hero"]["gold"]), (WORLD["areas"][1]["start"], 50))
        self.assertEqual(state["hero"]["hp"], state["hero"]["max_hp"])

    def test_town_heals_and_buys_better_gear(self):
        state = rpg.new_state(WORLD)
        state["hero"].update(hp=1, gold=1000)
        day = rpg.Day(WORLD, state, random.Random(0))
        day.town(WORLD["areas"][1])
        hero = state["hero"]
        self.assertEqual(hero["hp"], hero["max_hp"])
        self.assertEqual(hero["weapon"]["name"], "鉄の剣")
        self.assertEqual(hero["armor"]["name"], "鎖かたびら")
        day.town(WORLD["areas"][0])  # 弱い装備には買い替えない
        self.assertEqual(hero["weapon"]["name"], "鉄の剣")

    def test_clear_records_and_restarts(self):
        state = rpg.new_state(WORLD)
        last = WORLD["areas"][-1]
        state["pos"] = last["end"]
        state["boss_cleared"] = [a["name"] for a in WORLD["areas"][:-1]]
        state["hero"].update(level=30, base_atk=200, base_def=100, max_hp=999, hp=999)
        rpg.advance(WORLD, state, DAY, 1)
        self.assertEqual(state["lap"], 2)
        self.assertEqual((state["pos"], state["lap_day"], state["boss_cleared"]), (0, 0, []))
        self.assertEqual(state["hero"]["level"], 1)  # レベルと装備はリセット
        self.assertEqual(state["records"][0]["lap"], 1)
        self.assertIn("クリア", state["last"]["events"][-1])
        rpg.advance(WORLD, state, DAY + timedelta(days=1), 1)  # 次の日から 2 周目が進む
        self.assertEqual(state["lap_day"], 1)

    def test_journal_is_capped(self):
        state = play(rpg.JOURNAL_DAYS + 5, contributions=0)
        self.assertEqual(len(state["journal"]), rpg.JOURNAL_DAYS)
        self.assertEqual(state["journal"][0]["date"], (DAY + timedelta(days=rpg.JOURNAL_DAYS + 4)).isoformat())


class BalanceTest(unittest.TestCase):
    def test_average_player_clears_in_about_three_months(self):
        days, deaths = [], []
        for seed in range(40):
            rng, state, d = random.Random(seed), rpg.new_state(WORLD), DAY + timedelta(days=seed * 1000)
            while state["lap"] == 1 and state["day"] < 1000:
                rpg.advance(WORLD, state, d, rng.choices([0, 1, 3, 6], [30, 30, 25, 15])[0])
                d += timedelta(days=1)
            self.assertEqual(state["lap"], 2, "1000 日でクリアできない")
            days.append(state["records"][0]["days"])
            deaths.append(state["records"][0]["deaths"])
        days.sort()
        self.assertTrue(70 <= days[len(days) // 2] <= 120, days)
        self.assertLess(max(deaths), 15)


class DisplayTest(unittest.TestCase):
    def test_card_fits_and_has_five_lines(self):
        for state in (rpg.new_state(WORLD), play(1), play(40), play(120, contributions=6)):
            lines = rpg.build_text(WORLD, state).splitlines()
            for line in lines[:5]:
                self.assertLessEqual(ranking.width(line), ranking.LINE_MAX, line)
            self.assertEqual(lines[5], "")  # カードの 5 行のあとに詳細が続く
            self.assertTrue(lines[0].startswith("⚔️ Day"))

    def test_fit(self):
        self.assertEqual(rpg.fit("あいう", 6), "あいう")
        self.assertEqual(rpg.fit("あいうえお", 6), "あい…")

    def test_teaser_before_boss(self):
        state = rpg.new_state(WORLD)
        state["pos"] = WORLD["areas"][0]["end"] - 1
        state["lap_day"] = 1
        self.assertIn("キングスライム", rpg.teaser(WORLD, state))


class StateTest(unittest.TestCase):
    def test_save_and_load(self):
        state = play(3)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "rpg.json"
            rpg.save_state(state, path)
            self.assertEqual(rpg.load_state(WORLD, path), state)
            path.write_text("<<<<<<< HEAD")
            with self.assertRaises(SystemExit):
                rpg.load_state(WORLD, path)
        self.assertEqual(rpg.load_state(WORLD, Path("/nonexistent/rpg.json")), rpg.new_state(WORLD))


class ContributionsTest(unittest.TestCase):
    def test_sums_contributions_and_falls_back_to_next_token(self):
        ok = {"data": {"user": {"contributionsCollection": {
            "totalCommitContributions": 3, "totalIssueContributions": 1, "totalPullRequestContributions": 1,
            "totalPullRequestReviewContributions": 0, "restrictedContributionsCount": 2}}}}
        denied = {"errors": [{"message": "Resource not accessible by integration"}]}
        with mock.patch.object(ranking, "api", side_effect=[denied, ok]) as api:
            self.assertEqual(rpg.fetch_contributions("me", DAY, ["t1", "t2"]), 7)
        body = api.call_args.args[3]
        self.assertEqual(body["variables"]["from"], "2026-10-06T00:00:00+09:00")  # JST の 1 日
        self.assertEqual(body["variables"]["to"], "2026-10-06T23:59:59+09:00")

    def test_all_tokens_fail(self):
        with mock.patch.object(ranking, "api", side_effect=OSError("down")), \
             self.assertRaises(ranking.FetchError):
            rpg.fetch_contributions("me", DAY, ["t1"])
        with self.assertRaises(ranking.FetchError):
            rpg.fetch_contributions("me", DAY, [])


class MainTest(unittest.TestCase):
    def run_main(self, state, argv, env=None):
        saved = {}
        with mock.patch.object(rpg, "load_state", return_value=state), \
             mock.patch.object(rpg, "save_state", side_effect=lambda s: saved.setdefault("s", copy.deepcopy(s))), \
             mock.patch.object(ranking, "update_gist") as gist, \
             mock.patch.object(sys, "argv", ["rpg.py", *argv]), mock.patch.dict("os.environ", env or {}, clear=True), \
             mock.patch("sys.stdout"):
            rpg.main()
        return saved.get("s"), gist

    def test_advances_saves_and_updates_gist(self):
        saved, gist = self.run_main(rpg.new_state(WORLD), ["--date", "2026-10-06", "--contributions", "3"],
                                    {"GIST_ID_RPG": "g", "GIST_PAT": "p"})
        self.assertEqual(saved["day"], 1)
        self.assertEqual(gist.call_args.args[:3], ("g", "p", rpg.FILENAME))

    def test_already_processed_only_updates_gist(self):
        state = play(1)
        saved, gist = self.run_main(state, ["--date", DAY.isoformat()], {"GIST_ID_RPG": "g", "GIST_PAT": "p"})
        self.assertIsNone(saved)
        gist.assert_called_once()

    def test_fetch_failure_skips_the_day(self):
        with mock.patch.object(rpg, "fetch_contributions", side_effect=ranking.FetchError("x")), \
             mock.patch.object(ranking, "warn"):
            saved, gist = self.run_main(rpg.new_state(WORLD), ["--date", "2026-10-06"],
                                        {"RPG_USER": "me", "GIST_ID_RPG": "g", "GIST_PAT": "p"})
        self.assertIsNone(saved)
        gist.assert_not_called()

    def test_dry_run_writes_nothing(self):
        saved, gist = self.run_main(rpg.new_state(WORLD), ["--dry-run", "--contributions", "1"])
        self.assertIsNone(saved)
        gist.assert_not_called()


if __name__ == "__main__":
    unittest.main()
