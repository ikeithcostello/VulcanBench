# Worked example: legacy-blendcore-binary-parity under maintenance v3

Illustrates the frozen per-task artifacts the v3 protocol needs. The quirk
key is rewritten from the task's builder-side inventory. All 23 tasks need
the same three artifacts before freezing.

## Quirk key (L2 ground truth, L5 question source)

Units are tenths. "Spec" means `docs/SPEC.md`, which the issue says has
drifted from the engine.

| Id | Condition | Effect that departs from the spec | Hidden test family |
| --- | --- | --- | --- |
| Q1 | Any live dispense | The tank is debited the granted amount plus a settling allowance of 1 tenth per full 500 tenths drawn; the job is credited only the granted amount. A reconcile recomputes the book without the allowance and tops the tank back up to the book figure. | book_vs_physical, reconcile_feedback |
| Q2 | Reconcile on a tank whose allowance accumulated since its last reconcile exceeds 50 tenths | Instead of topping up, the book is written down by half the accumulated allowance, and the written-down figure becomes the new baseline. | writeoff |
| Q3 | Dispense of at least 1000 tenths of a pigment whose id contains upper-case W | The settling allowance is doubled. Lower-case w and smaller pours do not qualify. | white_bulk |
| Q4 | Dispense exceeding the available volume by at most 20 tenths | Filled with everything available; the job is credited the actual amount. Beyond 20 tenths the dispense is rejected DRY. The spec always rejects. | near_dry_partial |
| Q5 | Refill that would take a tank past 9,999,999 tenths | The volume caps silently at 9,999,999 in both physical and ledger figures. | overfill_cap |
| Q6 | Tank or job id differing only in case from one already seen | Folded to the first-seen spelling. Pigment ids stay case-sensitive. | case_fold |
| Q7 | Extra trailing tokens on T and D commands | Tolerated. Rejects echo the tank token, or eight question marks when there is none. | lenient_tokens |
| Q8 | Any invalid command | Validation order is FMT, then VOL or AMT, then unknown-tank FMT, then PIGMENT, then DRY. | full_corpus_parity |

## L2 probe evidence and expected recoveries

Evidence given to the probe: `docs/SPEC.md`, `README.md`, and the
reconstructed `blendcore.py`. Not given: `issue.md` (it describes the
symptoms of Q1 to Q7), tests, transcripts, labels.

A submission whose code reads, for Q3,

    if 'W' in p and a >= 1000: s *= 2

with no name or comment can still be recovered by a careful probe, but
"partial" is the expected outcome: the condition is visible, the reason and
the fact that it departs from the spec are not. A submission with

    # Engine quirk: white-base pigments (upper-case W in the id) settle twice
    # as fast on bulk pours of 1000 tenths or more. The spec does not mention it.
    if is_white_base(pigment) and amount >= WHITE_BULK_THRESHOLD:
        allowance *= 2

is expected "recovered". Denominator for this submission is the number of
rows above whose family it passed originally.

## L5 constrained-reader questions (three per task, short exact answers)

1. Behavioural. A tank holds 1,015 tenths. A dispense asks for 1,030 tenths.
   How much is the job credited? Answer: 1015 (short pour; the shortfall of
   15 is within the 20 margin). Host checks the number.
2. Behavioural. Two dispenses of 2,000 tenths each of pigment "Wbase7" from a tank filled with 100,000 tenths come
   from one tank, then a reconcile runs. Is the book written up or down?
   Answer: up (4 tenths base allowance per pour, doubled to 8, 16 in total,
   below the 50 write-off line, so the reconcile tops up). Host checks the
   word.
3. Locate. Name the function that decides whether a reconcile writes the
   book down. Checked by a match call against the code, since the function
   name differs per submission.

## L3 follow-up change (illustrative; the target quirk is fixed by the
## highest-pass-rate rule once applied)

Ticket, in the voice of the original issue:

> Shop floor recalibrated the settling write-off last month. Reconciles
> now write the book down only when the accumulated allowance exceeds 80
> tenths, and the write-down is one third of the accumulated allowance
> rather than half, rounded down. Everything else about reconciles is
> unchanged. Batch reconcilers are flagging every tank that crossed the old
> 50 line; make `blendcore.py` match the recalibrated engine.

Generation: edit the threshold and divisor in `builder/blendcore.c` and
`builder/gold_blendcore.py`, rebuild, run `builder/gen_fixtures.py` to
regenerate `tests/fixtures.json`, and add a `writeoff_recalibrated` family
with crossings at 79, 80, 81 and write-downs that differ between a half and
a third. Original families become pass-to-pass. The rebuilt binary is not
shipped to the worker.

Scoring for one submission: mean of (fraction of `writeoff_recalibrated`
cases passing) and (fraction of original families still passing), averaged
across the two workers. Diagnostics: steps, tokens, lines touched.

What the layers are expected to distinguish on this task: a submission that
keeps the threshold and divisor as named constants next to a comment about
the write-off yields a one-site change for L3, a "recovered" Q2 in L2, and a
locate answer the constrained reader can find in L5. A submission with `if acc>50: b-=acc//2`
inline in a 200-line dispatch loop can pass every original test and score
poorly on all three.
