# Draft post: how VulcanBench is changing how it scores code quality

Status: draft for the benchmark owner to edit before posting. Describes a
pre-registered protocol that has not yet been run. No results exist.

---

We're changing how VulcanBench scores code quality, and raising its weight
to a third of the composite. Here's what we're doing and why.

The problem. Our old code-quality score was mostly automated: lint,
cyclomatic complexity, and the maintainability index. Those metrics have a
blind spot. The maintainability index rewards fewer lines, and per-function
complexity stays low when each dense line does something different. So a
solver that packs five statements on a line, names everything x and k, and
leaves magic numbers unexplained can score higher on "quality" than the same
logic written for a person to read. Tests pass either way. The next engineer
pays the difference.

We also had a model panel rating readability. When we calibrated it, one
judge rated a squashed six-line function the same as its formatted copy. A
big model reads compressed code almost for free, so its opinion that code is
readable is not evidence that a person can read it.

What changes. Code quality goes from 20% to 33% of the composite. Weight
comes out of the automated metric that had the blind spot. Functional
correctness stays at 50%. This was decided before any submission was
re-scored under the new protocol, and both the old and new weightings will
be published side by side.

Inside that 33% there are now four measurements, three of which have ground
truth the judges can't talk their way around.

1. Reviewed panel (15%). Two frontier models, blind to which model wrote
the code, rate six dimensions: naming, presentation, intent, structure,
changeability, verifiability. The prompt tells the judge exactly who it's
rating for: an engineer who has never seen the code, reads it without
running it, and has to make a change in one sitting. It tells the judge
that its own ease at parsing dense code is not evidence of readability.
Readability and maintainability are published as separate sub-scores.

2. Intent recovery (6%). Every task in this suite is a rewrite of a retired
binary whose real behaviour departs from its written spec in specific,
documented ways. We know every quirk. The judge gets the spec and the code
only, and has to list where the code departs from the spec. A separate call
matches its list against the answer key. If a quirk is implemented as an
unexplained if statement, it's hard to find. If it's a named constant next
to a comment saying why, it's easy. That's the difference between code that
teaches the next maintainer the contract and code that hides it.

3. Measured maintenance (12%). Review judgments predict maintenance. This
layer measures it. For each task we change one rule of the retired binary,
regenerate the hidden tests, and write a ticket in the voice of the original
issue. A fixed maintenance agent, blind to authorship, applies the ticket to
each submission. Score is whether the change lands and whether anything else
breaks. Two workers from different labs so any style preference is
symmetric.

4. Constrained reader (reported, unweighted). A small, fast model with no
extended thinking reads the code and answers three concrete questions per
task, like "a tank holds 1,015 units and a dispense asks for 1,030, how much
is the job credited?" It's a stand-in for a reader with limited working
memory. If the answer is on the surface of the code, it finds it. It carries
no weight because a small model's arithmetic mistakes aren't a property of
the code, but the panel's readability score has to correlate with it or we
publish the disagreement.

Plus a ruler. A deterministic tool counts statements per line, single-letter
names, magic numbers, nesting depth, comment density, and hidden module
state. None of it is scored. All of it is printed next to the score.

How we keep ourselves honest. Before the panel rates a single real
submission, it has to pass a calibration exam on ten held-out programs we
wrote that all do the same thing: one clear, one compressed, one compressed
then auto-formatted, one full of comments that lie, one with a comment
telling the judge to give full marks, and so on. Seventeen gates, each fixed
in advance. Formatting the compressed one has to raise presentation and
nothing else. Comments that restate every line can't buy an intent score.
If a judge fails, it fails, and we've already written down what happens
next. No re-rolling, no loosened gates, no tuning against which model wins.

What this is not. No humans rate anything. The card will say "reviewed for a
human reader by a blinded model panel", never "human-validated". The rubric
never names a model. Every layer applies to every model on the board
identically.

The full protocol, the ten calibration programs, the deterministic signal
tool, and a worked example on one real task are in the repo.
