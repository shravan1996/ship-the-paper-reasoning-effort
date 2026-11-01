import unittest

from analyze import decide, decompose, policies, random_split, verdict_ok
from effort import bbeh


def row(a1_ok, a2_ok, x1_ok, a1_ans="x", a2_ans="x", chk1=True, chk2=True, line=True):
    r = {"id": "t-00", "task": "t", "a1_ok": a1_ok, "a2_ok": a2_ok, "x1_ok": x1_ok,
         "a1_ans": a1_ans, "a2_ans": a2_ans, "x1_ans": "y",
         "a1_line": line, "a2_line": line, "x1_line": True,
         "chk1_pass": chk1, "chk2_pass": chk2}
    for role, usd, s in (("a1", 1.0, 10), ("a2", 1.0, 12), ("x1", 3.0, 30), ("chk1", 0.5, 5), ("chk2", 0.5, 5)):
        r[f"{role}_usd"], r[f"{role}_s"], r[f"{role}_out"] = usd, s, 100
    return r


class VerdictTest(unittest.TestCase):
    def test_last_verdict_wins(self):
        self.assertTrue(verdict_ok("Verdict: INCORRECT\n...on reflection\nVerdict: CORRECT"))
        self.assertFalse(verdict_ok("Verdict: CORRECT\nWait.\nVerdict: INCORRECT"))

    def test_incorrect_is_not_read_as_correct(self):
        self.assertFalse(verdict_ok("Verdict: INCORRECT"))
        self.assertFalse(verdict_ok("verdict: **incorrect**"))

    def test_missing_verdict_escalates(self):
        self.assertFalse(verdict_ok("The reply looks right to me."))
        self.assertFalse(verdict_ok(""))
        self.assertFalse(verdict_ok(None))

    def test_markup_around_verdict(self):
        self.assertTrue(verdict_ok("**Verdict: CORRECT**"))
        self.assertTrue(verdict_ok("Verdict: **CORRECT**"))


class PolicyTest(unittest.TestCase):
    def test_gold_ladder_keeps_low_success_and_pays_once(self):
        p = policies(row(True, False, False))["gold_ladder"]
        self.assertEqual(p, (True, 1.0, 10, False))

    def test_gold_ladder_escalates_on_failure_and_pays_both(self):
        p = policies(row(False, False, True))["gold_ladder"]
        self.assertEqual(p, (True, 4.0, 40, True))

    def test_agreement_ladder_trusts_agreed_wrong_answer(self):
        p = policies(row(False, False, True, a1_ans="7", a2_ans="7"))["agreement_ladder"]
        self.assertEqual(p, (False, 2.0, 12, False))

    def test_agreement_ladder_escalates_on_disagreement(self):
        p = policies(row(True, False, False, a1_ans="7", a2_ans="8"))["agreement_ladder"]
        # disagreement throws away a right low answer for a wrong xhigh one
        self.assertEqual(p, (False, 5.0, 42, True))

    def test_selfcheck_ladder(self):
        passed = policies(row(False, True, True, chk1=True))["selfcheck_ladder"]
        self.assertEqual(passed, (False, 1.5, 15, False))
        flagged = policies(row(False, True, True, chk1=False))["selfcheck_ladder"]
        self.assertEqual(flagged, (True, 4.5, 45, True))

    def test_second_ordering_uses_a2_and_chk2(self):
        p = policies(row(False, True, False, chk1=False, chk2=True), "a2", "a1", "chk2")
        self.assertEqual(p["selfcheck_ladder"], (True, 1.5, 17, False))
        self.assertEqual(p["fixed_low"], (True, 1.0, 12, False))

    def test_fixed_policies(self):
        p = policies(row(True, True, False))
        self.assertEqual(p["fixed_low"], (True, 1.0, 10, False))
        self.assertEqual(p["fixed_xhigh"], (False, 3.0, 30, True))


class DecideTest(unittest.TestCase):
    def s(self, xa, xc, **kw):
        base = {"accuracy": xa, "usd_per_item": xc}
        out = {"fixed_xhigh": base}
        for k, (a, c) in kw.items():
            out[k] = {"accuracy": a, "usd_per_item": c}
        return out

    def test_continue(self):
        s = self.s(0.80, 1.0, gold_ladder=(0.85, 0.7), agreement_ladder=(0.79, 0.7), selfcheck_ladder=(0.70, 0.6))
        d = decide(s, None)
        self.assertTrue(d["replicated"])
        self.assertEqual(d["outcome"], "continue")
        self.assertEqual(d["continue_met_by"], ["agreement_ladder"])

    def test_stop_on_cost(self):
        s = self.s(0.80, 1.0, gold_ladder=(0.85, 0.7), agreement_ladder=(0.80, 1.2), selfcheck_ladder=(0.81, 1.1))
        self.assertEqual(decide(s, None)["outcome"], "stop")

    def test_partial(self):
        s = self.s(0.80, 1.0, gold_ladder=(0.85, 0.7), agreement_ladder=(0.77, 0.9), selfcheck_ladder=(0.70, 0.8))
        self.assertEqual(decide(s, None)["outcome"], "partial")


class ExtraAnalysisTest(unittest.TestCase):
    def test_random_split_line(self):
        s = {"fixed_low": {"accuracy": 0.6, "usd_per_item": 1.0},
             "fixed_xhigh": {"accuracy": 0.8, "usd_per_item": 3.0},
             "half": {"accuracy": 0.65, "usd_per_item": 2.0},
             "dearer": {"accuracy": 0.9, "usd_per_item": 4.0}}
        line = random_split(s)
        self.assertAlmostEqual(line["half"], 0.7)
        self.assertIsNone(line["dearer"])

    def test_decompose_counts_fixable_and_low_only(self):
        rows = [row(False, False, True, a1_ans="1", a2_ans="2", chk1=False),   # fixable, both flag
                row(False, False, True, a1_ans="1", a2_ans="1", chk1=True),    # fixable, neither flags
                row(True, True, False, a1_ans="1", a2_ans="2", chk1=True),     # low-only, agreement flags
                row(False, False, False)]                                      # both wrong
        d = decompose(rows)
        self.assertEqual((d["low_wrong"], d["both_wrong"], d["fixable"], d["low_only"]), (3, 1, 2, 1))
        self.assertEqual(d["fixable_flagged"], {"agreement": 1, "selfcheck": 1})
        self.assertEqual(d["low_only_flagged"], {"agreement": 1, "selfcheck": 0})


class GraderTest(unittest.TestCase):
    def test_benchmark_grader(self):
        self.assertTrue(bbeh.correct("work\nThe answer is: (A)", "(A)"))
        self.assertTrue(bbeh.correct("The answer is: 2, 3, 4", "2,3,4"))
        self.assertFalse(bbeh.correct("The answer is: 2, 3, 5", "2,3,4"))
        self.assertFalse(bbeh.correct("", "4"))

    def test_answers_normalise_for_agreement(self):
        self.assertEqual(bbeh.answer("The answer is: (A)"), bbeh.answer("so\nThe answer is: (a)."))

    def test_items(self):
        items = bbeh.load_items(per_task=16)
        self.assertEqual(len(items), 368)
        self.assertEqual(len({i["task"] for i in items}), 23)
        self.assertFalse(any(i["id"].endswith(("-18", "-19")) for i in items))


if __name__ == "__main__":
    unittest.main()
