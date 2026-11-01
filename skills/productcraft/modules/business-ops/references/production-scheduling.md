# Production scheduling: constraints, sequencing, changeovers and disruptions

Read this when the task is sequencing work orders on machines or lines, deciding between campaigns and mixed runs, finding the bottleneck, responding to a breakdown, shortage or absence, or interpreting OEE. Writing a scheduler or optimiser in code also needs `../../engineering-workflow/GUIDE.md`; simulation of a line is in `../../scientific-computing/GUIDE.md` (discrete-event simulation).

## Ground rules

- **The schedule must be executable.** It respects real capacity (machines, shifts, maintenance windows, tooling), qualified people, material availability and hard rules (allergen or contamination sequences, labour agreements, working-time law).
- **Use the plant's measured times.** Setup and run times, yields and downtime come from shop-floor records (MES or logs), not standards nobody has checked.
- **Decisions about which customer waits are commercial.** The scheduler shows the trade-off; management decides.
- **Publish changes to the shop floor yourself only if the owner has said so.** Otherwise produce the revised sequence for approval.

## Concepts that decide most schedules

- **MRP plans with infinite capacity.** It says what is needed and when, assuming every work centre can do it. Finite-capacity scheduling says when it can actually be done. Never release an MRP plan to the floor without a finite-capacity pass.
- **Backward then forward.** Schedule backward from due dates to find the latest start (keeps work-in-progress low); if that start is already in the past, schedule forward from now to find the real completion date and flag the order as late.
- **The constraint sets the pace.** The bottleneck is the resource with the highest ratio of required hours to available hours for the current mix. Test it: would one more hour there raise plant output? Work piling up in front of a machine can also be caused by upstream batch release or a shared resource (a crane, an inspector), so check before adding capacity.
- **Drum-buffer-rope.** Schedule the constraint first (the drum), protect it with a time buffer of work ahead of it (the buffer), and release new work at the constraint's pace (the rope). Non-constraints are scheduled to serve the constraint, not to maximise their own utilisation.
- **Shifting bottlenecks.** Product mix can move the constraint between shifts or weeks. Recompute utilisation by shift and mix, not as a weekly average.

## Sequencing rules

| Situation | Rule | What it optimises |
|---|---|---|
| Single resource, due dates matter | Earliest due date (EDD) | Minimises the maximum lateness on one machine |
| Single resource, throughput and work-in-progress matter | Shortest processing time (SPT) | Minimises mean flow time on one machine |
| Sequence-dependent setups | Setup matrix plus a heuristic (nearest neighbour, then pairwise swaps) checked against due dates | Total changeover time, subject to due dates |
| Mixed-model assembly | Levelled sequence (for example A-B-A-C-A-B rather than AAA-BB-C) | Smooth component consumption and labour load |

Priority order when jobs compete: safety and regulatory constraints, jobs already past due or about to be (ordered by contractual exposure, as agreed with management), jobs feeding a constraint whose buffer is running low, then the dispatching rule. Write the tie-breakers down so the schedule is reproducible.

## Changeovers

- **Setup matrix:** record the changeover time and cost (labour, scrap, lost output) for each product pair. Prohibited transitions (allergens, incompatible chemistry) are hard constraints, not costs.
- **Campaign versus mixed runs:** longer campaigns cut changeovers but raise cycle stock and lead time for other products. Compute the trade-off with actual changeover cost and holding cost; do not guess.
- **Setup reduction (SMED):** separate internal steps (machine stopped) from external ones (done while running), move internal steps outside, then streamline what remains (quick clamps, standard heights, pre-staged tools, first-piece checks that remove adjustments). Re-measure before using the new time in the schedule.

## Disruptions

1. Establish the facts: what is down or missing, the realistic recovery time (from maintenance or purchasing, with their confidence), and whether it touches the constraint.
2. Freeze work that is in progress or about to start; move it only if it is physically impossible to run.
3. Re-sequence the unfrozen work with the priority rules, using alternate routings, substitute materials or partial builds where they are approved.
4. Quality holds remove the held stock from the plan immediately; re-run the schedule without it.
5. Absence: check the skills matrix (operator x work centre x qualification level). Protect the constraint first; never assign an unqualified person to a regulated or safety-critical step.
6. Publish the revised schedule once, then hold it stable for a set period unless a new disruption arrives. Constant re-sequencing does more harm than the disruption.
7. Tell sales or customer service as soon as a committed date is at risk, with the new estimate and the recovery plan.

## OEE and its traps

OEE = availability x performance x quality, where availability = run time / planned production time, performance = (ideal cycle time x total count) / run time, and quality = good count / total count.

- Plants define "planned production time" differently (some exclude changeovers or planned maintenance). Compare OEE only between lines that use the same definition; write yours down.
- Commonly quoted "world-class" OEE figures are rough benchmarks, not targets. Track the trend and the loss categories on your own line.
- Quality losses at the constraint cost the whole plant's output; improving yield there is worth as much as adding the same share of capacity.
- When a full-calendar view matters (capacity investment), use TEEP, which counts all calendar time.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Releasing MRP planned orders straight to the floor | Finite-capacity pass first; flag overloads with dates |
| Adding capacity where work piles up | Verify the constraint with the "one more hour" test |
| Maximising utilisation of every machine | Subordinate non-constraints to the constraint's pace |
| Setup times from the routing master that nobody has measured | Recent shop-floor data, refreshed on a schedule |
| Re-sequencing after every small event | Frozen window and a stability period after each published change |
| Schedules that ignore who is qualified to run what | Skills matrix as a hard constraint |
| Complex changeovers or first-piece checks placed at the end of long shifts | Schedule critical steps when fatigue risk is lower, where the plant's rules allow |

## Closing the loop

- Every shift, compare scheduled versus actual per operation (start, finish, quantity, scrap, downtime reason), update the remaining schedule and publish it.
- Persistent gaps mean the parameters are wrong (times, yields) or the floor is not following the sequence. Fix the inputs; a schedule the floor does not trust stops being used.
- Watch for demand that has no order behind it (for example from a bill-of-materials error in MRP) and hold it rather than scheduling it.

## Checks (done when)

- [ ] Capacity, qualified labour, material and hard sequencing rules are all respected in the published or proposed schedule.
- [ ] The constraint is identified for the current mix and verified, not assumed from where work piles up.
- [ ] Setup and run times come from recent shop-floor data, with their source.
- [ ] Late orders and the trade-offs between customers are listed for a management decision.
- [ ] OEE figures state their definition; comparisons use the same definition.
