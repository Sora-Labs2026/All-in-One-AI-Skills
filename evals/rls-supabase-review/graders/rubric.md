---
type: llm
weight: 2
---
PASS only if the answer does all of the following:
- Says the `invoice_totals` view runs with its owner's rights and so bypasses row-level security, and fixes it with `security_invoker = true` (PostgreSQL 15+) or by revoking client access.
- Says the insert policy `with check (true)` lets any signed-in user insert invoices for another `user_id`, and fixes it with a check such as `user_id = auth.uid()` or by moving inserts to the server.
- Says a user can update their own `plan` column (for example set it to a paid plan), and fixes it with column privileges, a trigger, or by moving billing fields out of the user-editable table.
FAIL if the answer calls the migration safe, or misses any of these.
