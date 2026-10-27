# Type safety in TypeScript

Read this when you write or review TypeScript, change `tsconfig.json`, model domain states, handle data from outside the program, or design types other code depends on.

Types are only as trustworthy as their weakest boundary. The goal is that a value with a given type really has that shape at runtime, and that impossible states cannot be expressed.


Framework-specific typing (React props and events, Vue `defineProps` and JSDoc-typed JavaScript, Angular signal inputs, NestJS DTOs and injected classes) is in the matching file under `../../stacks/references/`.

## Compiler configuration

- `"strict": true` is the baseline. It enables `strictNullChecks`, `noImplicitAny`, `strictFunctionTypes`, `strictBindCallApply`, `strictPropertyInitialization`, `noImplicitThis`, `useUnknownInCatchVariables` and `alwaysStrict`.
- Worth adding where the codebase can absorb them:

| Flag | Catches |
|---|---|
| `noUncheckedIndexedAccess` | `arr[i]` and `record[key]` may be `undefined` |
| `exactOptionalPropertyTypes` | Confusing "property missing" with "property set to `undefined`" |
| `noImplicitOverride` | Accidental overrides in subclasses |
| `noFallthroughCasesInSwitch` | Missing `break` or `return` between cases |
| `noPropertyAccessFromIndexSignature` | Dot access hiding that a key may not exist |
| `verbatimModuleSyntax` | Type-only imports that would otherwise be emitted or dropped unpredictably |
| `isolatedModules` | Constructs that single-file transpilers (esbuild, SWC, Babel) cannot handle |

- **Run the type checker in CI and before saying done:** `npx tsc --noEmit` (or `tsc -b` with project references). Vite, esbuild, SWC, Babel and Node's type stripping remove types without checking them, so a green dev build proves nothing about types.
- **Tightening an existing codebase:** enable one flag at a time and fix its errors; or enable it in a stricter `tsconfig` for new or migrated directories first; or keep a committed count of errors per flag and fail CI when it rises (a ratchet). Do not leave a flag half-enabled with blanket suppressions.
- If code runs through type stripping (Node's built-in TypeScript support) or uses `erasableSyntaxOnly` (TypeScript 5.8+), avoid syntax that needs code generation: `enum`, `namespace` with values, constructor parameter properties.

## Boundaries: parse untrusted data

TypeScript types do not exist at runtime. Anything from outside the program must be checked before it is trusted: request bodies, query strings, `JSON.parse` output, environment variables, `localStorage`, messages from queues, workers or `postMessage`, third-party API responses, files.

- Validate with a schema library the project already uses (for example Zod, Valibot, ArkType, TypeBox with Ajv) and derive the static type from the schema, so the two cannot drift:

```ts
import { z } from "zod";

const CreateInvoice = z.object({
  customerId: z.string().min(1),
  amountMinor: z.number().int().positive(),
  currency: z.enum(["EUR", "USD", "GBP"]),
  dueDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Use YYYY-MM-DD"),
});
type CreateInvoice = z.infer<typeof CreateInvoice>;

export function parseCreateInvoice(body: unknown): CreateInvoice {
  return CreateInvoice.parse(body); // throws with field-level issues; map them to your error shape
}
```

- Parse once at the boundary into a precise type; inner code takes that type and does not re-check.
- Validate environment variables at startup in one module and export a typed config object; do not read `process.env` throughout the code.
- Never write `JSON.parse(text) as Order` or `(await res.json()) as Order`. That is an unchecked claim.

## Avoid unchecked escapes

- **`unknown` instead of `any`** for values of unknown shape; narrow with `typeof`, `instanceof`, `in`, discriminant checks or a schema. Enable typescript-eslint's type-aware rules (`recommended-type-checked` or `strict-type-checked`), including `no-explicit-any` and the `no-unsafe-*` family.
- **`satisfies` instead of `as`** when you want to check an object literal against a type but keep its precise inferred type:

```ts
const routes = {
  home: "/",
  invoice: "/invoices/:id",
} satisfies Record<string, `/${string}`>;
// routes.invoice keeps its literal type; a typo in a value is a compile error
```

- **Type assertions** (`as X`) only where you know more than the compiler and can say why in a comment, typically right after a runtime check the compiler cannot follow. `as unknown as X` is almost always a sign the types or the design are wrong.
- **Non-null `!`** only with a comment proving the value exists; otherwise handle the `undefined` case.
- **`// @ts-expect-error <reason>`** instead of `// @ts-ignore` when a suppression is unavoidable: it fails once the error disappears, so stale suppressions do not accumulate. Enforce with `@typescript-eslint/ban-ts-comment`.
- Do not add any of these to make an error go away without understanding it; that moves the bug to runtime.

## Model states so invalid ones cannot exist

- **Discriminated unions** instead of objects full of optional fields:

```ts
type Payment =
  | { status: "pending"; createdAt: Date }
  | { status: "authorized"; createdAt: Date; authorizationId: string }
  | { status: "failed"; createdAt: Date; failureCode: "card_declined" | "expired" | "network" }
  | { status: "refunded"; createdAt: Date; refundId: string; refundedMinor: number };
```

- **Exhaustive handling:** switch on the discriminant and end with a `never` check, so adding a new variant produces compile errors at every place that must handle it. Also enable `@typescript-eslint/switch-exhaustiveness-check`.

```ts
function label(p: Payment): string {
  switch (p.status) {
    case "pending": return "Waiting for confirmation";
    case "authorized": return "Authorized";
    case "failed": return `Failed (${p.failureCode})`;
    case "refunded": return "Refunded";
    default: {
      const unhandled: never = p;
      throw new Error(`Unhandled payment status: ${JSON.stringify(unhandled)}`);
    }
  }
}
```

- **Distinct types for look-alike values** (user IDs versus order IDs, cents versus euros) using a branded type with a single constructor that validates:

```ts
declare const orderIdTag: unique symbol;
export type OrderId = string & { readonly [orderIdTag]: true };

export function toOrderId(raw: string): OrderId {
  if (!/^ord_[A-Za-z0-9]{12}$/.test(raw)) throw new Error("Not an order id");
  return raw as OrderId; // the only assertion, guarded by the check above
}
```

- **Literal unions and `as const`** for fixed sets; derive types from values (`typeof`, `keyof`, indexed access types) so a list and its type stay one source of truth:

```ts
export const CURRENCIES = ["EUR", "USD", "GBP"] as const;
export type Currency = (typeof CURRENCIES)[number];
```

- Prefer string literal unions or `as const` objects to `enum` in new code, unless the project already uses enums consistently.

## Functions and APIs

- Give exported functions explicit return types; it keeps the public contract stable and puts errors where they belong.
- Use an options object instead of several positional booleans (`send(msg, { retry: true, urgent: false })`).
- Accept `readonly` arrays and `Readonly<T>` for inputs you do not mutate.
- Use generics only when a type parameter connects inputs to outputs; constrain them (`<T extends { id: string }>`). Elaborate conditional and mapped types belong in libraries with type tests, rather than in application code.
- Return typed results for expected failures, for example `{ ok: true; value: Invoice } | { ok: false; error: "not_found" | "forbidden" }`, and keep exceptions for the unexpected.
- In `catch`, the error is `unknown`: narrow with `instanceof Error` before reading `.message`, and keep the original as `cause` when rethrowing.
- Use `??` rather than `||` for defaults when `0`, `""` or `false` are valid values.

## Tests and type tests

- Build test data with typed factories instead of partial objects cast with `as`:

```ts
export function buildInvoice(overrides: Partial<Invoice> = {}): Invoice {
  return {
    id: "inv_1",
    customerId: "cus_1",
    amountMinor: 1_000,
    currency: "EUR",
    status: "draft",
    ...overrides,
  };
}
```

- For libraries and shared types, test the types themselves: `expectTypeOf` in Vitest, `tsd`, or a type-test file in which lines marked `// @ts-expect-error` must keep failing.
- Check published package types and exports with `npx @arethetypeswrong/cli --pack` and `npx publint`.

## Module hygiene

- Use `import type` for type-only imports (required under `verbatimModuleSyntax`).
- Avoid circular imports (`npx madge --circular --extensions ts,tsx src/`) and barrel files that re-export entire directories.
- Generate types from contracts (OpenAPI, GraphQL, protobuf, database schema) rather than hand-copying them, and regenerate in CI to catch drift.

## Checks (done when)

- [ ] `tsc --noEmit` (or the project's equivalent) passes with no new errors, and it runs in CI.
- [ ] Every new external input is parsed by a schema at the boundary; no `as` casts on parsed JSON or responses.
- [ ] No new `any`, `@ts-ignore`, `as unknown as` or unexplained `!`; any `@ts-expect-error` has a reason.
- [ ] New state models use discriminated unions with exhaustive handling.
- [ ] Changed public types are documented and, for libraries, covered by type tests.

## Anti-patterns

- Relying on the bundler for type checking.
- `any` spreading from one untyped boundary through the codebase.
- Optional-field bags where only certain combinations are valid.
- `as` casts in tests to fake partial objects.
- `// @ts-nocheck` or file-wide suppressions to get a migration past the type checker.
- Duplicated hand-written types for the same API on client and server.
