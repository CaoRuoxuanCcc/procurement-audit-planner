---
name: challenger-done-not-copied
description: CHALLENGER DONE is not sent to qa-reviewer directly; it arrives via a lead relay
metadata:
  type: feedback
---

The challenger's protocol sends CHALLENGER DONE to the planner and lead only; the lead relays it to qa-reviewer word for word. Wait for that relay before the final run rather than expecting it from the challenger.

**Why:** in the first team run the final run waited on a message that never came directly.
**How to apply:** after PLANNER DONE, if no CHALLENGER DONE arrives, expect a lead relay; quote the relayed line in review.md and note it was relayed.
