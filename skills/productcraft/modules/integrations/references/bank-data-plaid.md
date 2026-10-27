# Bank data with Plaid

Read this when an app links users' bank accounts through Plaid to read transactions, balances, account and routing numbers or identity, or to start bank payments. Other bank-data aggregators share the same shape (a hosted linking flow, a long-lived access token per connection, webhooks for updates); check their documentation for the specifics.

Bank data is sensitive financial personal data. Before building, confirm with the owner which products are needed, which countries are served, and who reviews the privacy notice and data-retention policy (`../../legal-ready/GUIDE.md`). Open-banking rules (for example PSD2 in the EU and UK, and US data-access rules whose status has been changing) affect consent and retention; get qualified review.

## Concepts

| Term | Meaning |
|---|---|
| Link | Plaid's hosted UI where the user picks a bank and logs in; your app never sees bank credentials |
| `link_token` | Short-lived token your server creates to open Link for one user and one configuration |
| `public_token` | Short-lived token Link returns to the browser; exchanged once on the server |
| `access_token` | Long-lived secret that reads one Item; server-side only, encrypted at rest |
| Item | One user's connection to one institution, possibly with several accounts |
| Products | `transactions`, `auth`, `balance`, `identity`, `investments`, `liabilities` and others; each is priced and may need approval |

## Environments

- **Sandbox** for development and tests, with documented test users (username `user_good`, password `pass_good`) and endpoints that create Items and fire webhooks without Link.
- **Production** for real data, with limited free access for early testing on recent plans. The former Development environment has been retired; code that still points at it fails.
- Separate client secrets per environment, entered by the user. Plaid identifies your app with `PLAID-CLIENT-ID` and `PLAID-SECRET` headers (the SDK sets them from configuration).

## Linking flow

1. **Server:** create a `link_token` for the signed-in user (`client_user_id` is your stable, non-personal user ID), the products, country codes, language, your webhook URL and, for OAuth institutions, your registered redirect URI.
2. **Browser:** open Link with the token (`react-plaid-link` or the platform SDK). On success Link returns a `public_token` and metadata (institution, accounts selected).
3. **Server:** exchange the `public_token` for an `access_token` and `item_id`, bound to the user from the session, not from request data. Store the token encrypted and the Item and account IDs in plain columns.
4. **Do not request products you will not use.** Each product costs money, adds consent text and can reduce the institutions available.

```python
# Server side, plaid-python. Error handling and encryption omitted for brevity.
exchange = client.item_public_token_exchange(
    ItemPublicTokenExchangeRequest(public_token=public_token)
)
save_item(user_id=session_user_id,
          item_id=exchange["item_id"],
          access_token_ciphertext=encrypt(exchange["access_token"]))
```

## Transactions: use the sync endpoint

- `/transactions/sync` returns `added`, `modified` and `removed` transactions since a cursor. Store the cursor per Item, start with none, and loop while `has_more` is true. It replaces the older date-range `/transactions/get` for new work.
- Commit the page's changes and the new cursor in one transaction. If Plaid reports that data changed during pagination, restart the loop from the cursor you saved before it began.
- Call sync when the `SYNC_UPDATES_AVAILABLE` webhook arrives, plus a periodic safety sync.
- Amounts are positive when money leaves the account and negative when it arrives. `pending` transactions are later removed and replaced by posted ones with new IDs (linked by `pending_transaction_id`); handle both changes.
- Prefer the `personal_finance_category` field over the legacy `category` array for categorization.

```python
cursor = load_cursor(item_id)          # None on the first run
added, modified, removed = [], [], []
while True:
    params = {"access_token": token, **({"cursor": cursor} if cursor else {})}
    resp = client.transactions_sync(TransactionsSyncRequest(**params))
    added += resp["added"]; modified += resp["modified"]; removed += resp["removed"]
    cursor = resp["next_cursor"]
    if not resp["has_more"]:
        break
apply_changes_and_save_cursor(item_id, added, modified, removed, cursor)   # one DB transaction
```

## Other products

- **Balance:** `/accounts/balance/get` fetches live balances and is slower and billed separately; balances in other responses may be cached. Use live balance only where a decision depends on it (for example before a bank debit).
- **Auth:** returns account and routing numbers for ACH. Some institutions return tokenized account numbers that work only for payments, not as the real number. To move money, prefer a payment partner integration with a processor token over handling raw numbers yourself.
- **Identity:** names, emails, phone numbers and addresses on the account; compare with your user's data for ownership checks and store only the result unless you need the data.

## Item health

| Signal | Meaning | Response |
|---|---|---|
| `ITEM_LOGIN_REQUIRED` error or `ITEM: ERROR` webhook | Credentials changed or the bank needs re-authentication | Mark the Item as needing attention; let the user fix it through Link in update mode (a `link_token` created with the existing `access_token`) |
| `PENDING_EXPIRATION` or `PENDING_DISCONNECT` webhook | Consent is about to lapse | Prompt the user to re-consent before it does |
| `PRODUCT_NOT_READY` | Initial data still being fetched | Wait for the webhook; do not poll in a tight loop |
| `RATE_LIMIT_EXCEEDED` | Too many calls | Back off; reduce balance calls |
| User disconnects or deletes their account | Consent withdrawn | Call `/item/remove`, delete the access token and the data your policy does not require you to keep |

## Webhooks

- Plaid signs webhooks with a JWT in the `Plaid-Verification` header (ES256). Fetch the key by its key ID from the verification-key endpoint (cache it), verify the JWT, reject tokens issued more than five minutes ago, and compare the SHA-256 of the raw body with the token's body-hash claim in constant time. The SDK and Plaid's docs show the exact steps.
- Webhook payloads carry `webhook_type`, `webhook_code` and `item_id`, not the data itself. Look up the Item, then call the API.
- Everything in `webhooks.md` applies: raw body, deduplication, fast acknowledgement, idempotent processing.

## Testing

- Sandbox endpoints create Items without the Link UI and fire chosen webhooks, so integration tests can cover linking, sync, update mode and errors without a browser.
- Unit tests use a fake adapter with fixtures for `added`, `modified`, `removed`, pending-to-posted replacement and a restart during pagination.
- Never use real bank credentials in tests or share Production access tokens with developers.

## Pitfalls

| Pitfall | Fix |
|---|---|
| `access_token` sent to the browser or logged | Server-only, encrypted at rest, redacted from logs and error reports |
| `public_token` exchange trusts a user ID from the request body | Bind the Item to the session's user |
| Date-range polling for transactions | `/transactions/sync` with a stored cursor and webhooks |
| Pending transactions duplicated after posting | Apply `removed` and link by `pending_transaction_id` |
| Requesting every product "just in case" | Request what features use; add more with update mode later |
| Data kept after the user disconnects | `/item/remove` and deletion per the written retention policy |

## Done when

- [ ] Access tokens never leave the server, are encrypted at rest and are absent from logs (inspection or test).
- [ ] Transactions sync by cursor with atomic saves, handles removed and pending-to-posted changes, and recovers from a mid-pagination restart (tested with fixtures).
- [ ] Webhook JWT verification, body-hash comparison and deduplication are tested.
- [ ] Update mode and disconnect (`/item/remove` plus deletion) work in Sandbox.
- [ ] The owner has confirmed products, countries, privacy notice and retention policy.
