# GraphQL servers and clients

Read this when you build or change a GraphQL server (schema, resolvers, batching, errors, limits, subscriptions, federation) or a GraphQL client (caching, code generation, pagination). Contract rules (schema evolution, nullability changes, connections, typed mutation errors, depth and cost limits, authorization in the business layer) are already in the GraphQL section of `../../engineering-practices/references/api-contracts.md`; this file adds the engineering around them.

## When GraphQL fits

- **Fits:** several clients (web, mobile, partners) that need different shapes of the same graph; deeply related data; teams that want a typed contract with generated clients.
- **Does not fit well:** simple CRUD with one client, file transfer, webhooks, heavily cached public reads (HTTP caching is harder), or a team without capacity to run query cost limits and schema governance. A REST or RPC API is fine there.
- Introducing GraphQL in front of existing REST services works as a backend-for-frontend layer; it does not require rewriting the services.

## Servers and approaches

- **JavaScript and TypeScript:** Apollo Server (major 5 is current; 4 reached end of life in January 2026), GraphQL Yoga, Mercurius (Fastify), `@nestjs/graphql`. Code-first schema builders: Pothos, TypeGraphQL, NestJS code-first.
- **Other languages:** Strawberry or Ariadne (Python), gqlgen (Go, schema-first), Spring for GraphQL or Netflix DGS (JVM), Hot Chocolate (.NET), async-graphql (Rust).
- **Schema-first** (SDL files, generated resolver types) keeps the contract readable in review. **Code-first** keeps types and resolvers together. Either is fine; follow the project. With schema-first, generate resolver types (GraphQL Code Generator `typescript-resolvers`) so a resolver cannot drift from the SDL.

## Schema design idioms

- Model the domain, not the tables. Hide join tables and storage columns.
- Prefer specific mutations (`publishPost`, `cancelOrder`) over generic updates (`updatePost(status: ...)`); each gets its own input and payload type.
- Use custom scalars for meaning (`DateTime`, `EmailAddress`, `URL`) and represent money as an integer or decimal string with a currency field. Avoid a generic `JSON` scalar; it opts out of the type system.
- Fields that can fail independently (a call to another service) are nullable, so one failure returns partial data instead of nulling the parent.
- Interfaces for shared fields across types; unions for "one of these unrelated types", including typed error results.
- If clients use Relay or a normalized cache, give every entity a stable `id` (globally unique, opaque) and implement `node(id:)` for Relay.
- Every list is a connection with a maximum `first`.

## Resolvers and batching

- Resolvers stay thin: read arguments and context, call a domain service, return. Business rules and authorization live in that service so REST, jobs and GraphQL share them.
- Build the context per request: the authenticated principal, request-scoped loaders, a request id for logs.
- **Create DataLoaders per request.** A module-level loader caches across users and leaks one user's data to another.
- The batch function returns exactly one result per key, in key order, with an `Error` for keys that failed.

```ts
// Per-request loaders. Authorization is applied inside the batch query, not after.
export function createLoaders(viewer: Viewer) {
  return {
    projectById: new DataLoader<string, Project | null>(async (ids) => {
      const rows = await db.project.findMany({
        where: { id: { in: [...ids] }, orgId: viewer.orgId },
      });
      const byId = new Map(rows.map((r) => [r.id, r]));
      return ids.map((id) => byId.get(id) ?? null);   // same length and order as ids
    }),
  };
}

export const resolvers = {
  Task: {
    project: (task: TaskRow, _args: unknown, ctx: Ctx) => ctx.loaders.projectById.load(task.projectId),
  },
};
```

- Count queries per operation in tests (an ORM query log or a counter) so an N+1 regression fails the build.
- Field-level lookahead (selecting only requested columns) is an optimization for measured hot paths, not a default.

## Errors

- Expected business outcomes (validation failed, not allowed, conflict) are typed results in the payload (`../../engineering-practices/references/api-contracts.md`). The top-level `errors` array is for unexpected faults.
- Give every error in `errors` an `extensions.code` clients can branch on.
- Mask unexpected errors in production: Yoga masks by default; in Apollo Server use `formatError` to replace internal messages and log the original with the request id. No stack traces, SQL or hostnames to clients.
- Clients must handle partial data: `data` and `errors` can both be present.

## Protecting the server

The baseline (depth and cost limits, pagination limits, timeouts, persisted operations) is listed in `../../engineering-practices/references/api-contracts.md`. How to apply it:

- Enforce depth, cost, alias count and token count before execution (for example with graphql-armor or graphql-query-complexity). Aliases let one request call a field hundreds of times, such as a login mutation for password guessing; limit aliases and batched operations per request.
- For first-party clients, register operations at build time and accept only their ids in production (persisted operations, also called trusted documents). That removes arbitrary queries entirely.
- Disabling introspection in production hides the schema from casual browsing but is not a security control; field suggestions in error messages leak names too.
- CSRF: with cookie authentication, reject requests that a browser could send cross-site without a preflight. Apollo Server enables CSRF prevention by default (it requires a non-simple content type or a specific header); keep it on. Never run mutations over GET.
- Multipart file uploads are a CSRF and resource risk; prefer signed direct-to-storage uploads with a mutation that records the result.
- Authorize per object in the domain layer, including objects reached through nested fields (`user { organization { invoices } }`).

## Subscriptions

- Use the `graphql-ws` library and its `graphql-transport-ws` protocol, or Server-Sent Events (`graphql-sse`). The older `subscriptions-transport-ws` package is unmaintained.
- Authenticate in `connection_init` (or the HTTP upgrade), and authorize every event before sending it: filter by the subscriber's permissions, not only by topic.
- An in-memory pub/sub works for one instance only. With several, publish through Redis, NATS or Kafka.
- Send small change notifications and let clients refetch large objects; a subscription that pushes whole documents multiplies bandwidth per subscriber.
- Transport, scaling and reconnect practice: `realtime-websockets.md`.

## Federation

- Use federation when several teams own parts of one graph and deploy independently. One team with one service is better served by a single schema.
- Federation 2 directives: `@key` declares an entity and its key fields; `@shareable` allows several subgraphs to resolve a field; `@external`, `@requires` and `@provides` describe fields owned elsewhere; `@override` migrates a field between subgraphs; `@inaccessible` hides a field from the public schema.
- Entity resolution (`__resolveReference`) is called once per entity per query plan; batch it with a DataLoader or it becomes the N+1 of the gateway.
- Run composition and breaking-change checks for each subgraph in CI before deploy.
- Licensing: Apollo's router and composition tools are under the Elastic License 2.0, and some features need a commercial plan. Check the terms for your use, or choose an open-source gateway that supports the federation spec.

## Clients

- **Apollo Client:** normalized cache keyed by `__typename` and `id`. Configure `typePolicies` with `keyFields` for types without `id`, and `merge` functions (or the `relayStylePagination` helper) for paginated fields. Major 4 (2025) moved React hooks to `@apollo/client/react` and changed error types; follow its migration guide.
- **urql:** document cache by default (refetch by query and variables); add Graphcache for normalized caching.
- **Relay:** fragments colocated with components and a compiler that enforces conventions; strongest consistency, highest setup cost.
- **TanStack Query with a small GraphQL fetch function** is enough for apps that do not need normalization.
- Common cache bugs: an entity without `id` in the selection is not normalized; a create mutation does not add the item to existing lists (update the cache with `cache.modify` or refetch the list); pages overwrite each other without a merge policy.

Generate types from operations, not by hand:

```ts
// codegen.ts (GraphQL Code Generator, client preset)
import type { CodegenConfig } from "@graphql-codegen/cli";

const config: CodegenConfig = {
  schema: "schema.graphql",              // or the server's SDL output, never a production endpoint with credentials
  documents: ["src/**/*.{ts,tsx}"],
  generates: { "src/gql/": { preset: "client", presetConfig: { fragmentMasking: true } } },
};
export default config;
```

Run code generation in CI and fail on a diff, so operations that no longer match the schema break the build rather than production.

## Testing

- Execute operations against the real schema in tests (Apollo `server.executeOperation`, Yoga `yoga.fetch`) with a test context; assert `data` and `errors` separately.
- Test authorization through nested paths, not only top-level fields.
- Check schema changes for breaks in CI (`graphql-inspector diff`, or the composition tool's check).
- Client components: mock at the network layer (MSW supports GraphQL operations) or with the client library's mock provider.

## Done when

- [ ] Schema changes are classified compatible or breaking (`../../engineering-practices/references/api-contracts.md`) and checked in CI.
- [ ] Every new list is a bounded connection; every new nested field that loads data is batched.
- [ ] Loaders are created per request; authorization is applied inside the data access, including nested paths.
- [ ] Depth, cost and alias limits are enforced and tested with an over-limit query.
- [ ] Production errors are masked and carry `extensions.code`; generated client types are up to date.
