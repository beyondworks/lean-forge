# bench

Eight tasks on a small Python invoicing library (`fixture*/`), graded by hidden tests (`hidden/`).
A scripted user (Claude Sonnet) answers every harness from the same intent file (`intent/`).

| Task | Kind | What the hidden tests check |
|---|---|---|
| t1 | vague feature: CSV export for an accountant | header text and order, UTF-8 BOM, date order, values |
| t2 | bug with a wrong user diagnosis ("it's `round()`") | discount on the subtotal, half-up rounding |
| t3 | typo | the one word |
| t4 | vague feature: invoice numbering for tax filing | format, yearly reset, gaps kept, legacy ids ignored |
| t5 | bug with a narrow user fix ("just strip it") | spaces, case, corporate prefixes, no partial match |
| t6 | vague feature: payment due date, "30 days" | calendar days, weekend roll-forward, month end |
| t7 | vague feature: amount in Korean words for receipts | "금 … 원정", explicit 일, 만/억 grouping, zero rejected |
| t8 | bug with a wrong user diagnosis ("discounts") | year–month keys, VAT included, ordered, empty |

Arms in `results/` (`c<case>-<arm>-<task>-r<run>.json`):

| Arm | Harness |
|---|---|
| A | dryforge |
| B | Castra + Ponytail |
| C | prototype v0.3: questions forced by a hook, on top of B |
| D | prototype v0.4: C + Jev triage + "any other rule?", on top of B |
| E | the v0.4 gate alone |
| F | lean-forge 1.0: gate + a light proof hook + Ponytail ladder text |
| G | **lean-forge 2.0** (this repository) |

Case 1 = no other harness loaded. Case 2 = the author's full personal setup (other plugins, hooks and
memory), with B/C/D stacked on it and G replacing Castra and Ponytail in it. Only case 1 is runnable
from this folder: `python3 run.py <A|B|G> <task> <run>` (see the docstring for the environment variables).

Results keep numbers only; transcripts are not published.
