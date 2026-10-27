# AWS CDK

Read this when a repository has a `cdk.json`, imports `aws-cdk-lib`, or the user wants AWS infrastructure defined in TypeScript, Python, Java, C# or Go. Serverless design questions (queues, events, Lambda behavior) are in `aws-serverless-eda.md`.

The CDK synthesizes CloudFormation. Everything that applies to a CloudFormation change set applies here: `cdk diff` is the plan, `cdk deploy` is the apply, and the agent stops at the diff.

## Versions and setup

- CDK v2 ships as one library, `aws-cdk-lib`, plus `constructs` v10. CDK v1 reached end of support in 2023; migrate rather than extend it.
- Since early 2025 the CLI (`aws-cdk`) is released separately from the library, with its own version numbers. Check both (`npx cdk --version`, the lockfile entry for `aws-cdk-lib`) and keep the CLI at least as new as the library.
- Use the project's local CLI through `npx cdk` (or the language's equivalent) so everyone runs the same version. Experimental constructs live in separate `-alpha` packages with unstable APIs; pin them exactly.
- `cdk.json` holds feature flags under `context`. New projects get the current flags; changing a flag in an existing app can change synthesized resources, so diff every environment after touching one.
- Commit `cdk.context.json`. It caches lookups (VPCs, AMIs, availability zones) so synthesis is deterministic; refresh a cached value deliberately with `cdk context --reset KEY`.

## Structure

- **App, stages, stacks, constructs.** A stack is a deployment unit (one CloudFormation stack). Split stacks by lifecycle and blast radius: stateful resources (databases, buckets, keys) in their own stack with termination protection; frequently deployed compute in another.
- **Constructs are the reuse unit**, not stacks. Build an L3 construct for a company pattern (a bucket with encryption, logging, a policy and alarms) and instantiate it in several stacks.
- **Construct levels.** L1 (`Cfn*`) maps one-to-one to CloudFormation; L2 adds defaults and grant methods; L3 patterns compose several resources. Prefer L2. Drop to L1 or an escape hatch (`node.defaultChild`, `addPropertyOverride`) only for a property the L2 lacks, with a comment.
- **Environments.** Stacks without an explicit `env` are environment-agnostic and cannot do lookups. Production stacks set `env: { account, region }` explicitly, and each environment goes to its own account.
- **Let the CDK name things.** Omit optional physical names (`bucketName`, `functionName`, `tableName`). Generated names let the same construct deploy twice, and a resource with a fixed name cannot be replaced without a manual step. Set a name only when something outside the app must know it in advance, and prefer exporting the generated name through an SSM parameter.

## Identity is the logical ID

CloudFormation identifies a resource by its logical ID, which the CDK derives from the construct path. Renaming a construct ID, moving a construct to another parent or another stack changes the logical ID, and CloudFormation then creates a new resource and deletes the old one. For a database or bucket that is data loss.

- Run `cdk diff` after every refactor and look for `[-]` and `[+]` pairs on the same resource type.
- To keep a resource while changing code structure, pin its old logical ID with `overrideLogicalId`, or use CloudFormation stack refactoring (2025), which the CDK CLI exposes through a `refactor` command that may still be marked unstable in your version; check `cdk --help`.
- Set `removalPolicy` explicitly on stateful resources (`RETAIN`, or `SNAPSHOT` where supported). Defaults differ by construct; do not rely on memory.

## Cross-stack references

Passing a construct from one stack to another in the same app creates a CloudFormation export and import. The producer can then not change or remove that export while the consumer uses it ("Export ... cannot be deleted as it is in use"). To remove a reference safely: first deploy the producer with the value kept alive (`this.exportValue(...)`) and the consumer no longer using it, then remove the export in a second deployment. For loosely coupled stacks, share values through SSM parameters instead.

## Validation before any deploy

```bash
npm ci                        # or the language's locked install
npm run build && npm test     # compile and unit tests
npx cdk synth --quiet         # synthesis, cdk-nag aspects, template size limits
npx cdk diff --all            # the change set for every stack, against the deployed state
```

- **cdk-nag** applies rule packs (for example `AwsSolutionsChecks`) as an aspect during synthesis. Suppress a rule only with `NagSuppressions.addResourceSuppressions(resource, [{ id, reason }])` and a reason a reviewer can verify. Findings are advisory, like any scanner.
- **Assertions** test synthesized templates with `Template.fromStack(stack)`: `hasResourceProperties`, `resourceCountIs`, and `Match` helpers. Prefer fine-grained assertions on security-relevant properties (encryption, public access, IAM statements) over whole-template snapshots, which break on every library upgrade and get approved without reading.

```ts
const template = Template.fromStack(new StorageStack(app, "Test", { env }));
template.hasResourceProperties("AWS::S3::Bucket", {
  BucketEncryption: {
    ServerSideEncryptionConfiguration: Match.arrayWith([
      Match.objectLike({ ServerSideEncryptionByDefault: Match.objectLike({ SSEAlgorithm: "aws:kms" }) }),
    ]),
  },
  PublicAccessBlockConfiguration: { BlockPublicAcls: true, BlockPublicPolicy: true,
                                    IgnorePublicAcls: true, RestrictPublicBuckets: true },
});
```

- Read `cdk diff` like a Terraform plan: replacements (`[-]` and `[+]`, or "may be replaced"), IAM statement changes (the diff prints a security-changes table), security group rules, removal of stateful resources. Summarize these for the user.

## Deploying is the user's call

- `cdk bootstrap` creates resources (an S3 bucket, ECR repository and IAM roles) in the target account and region. It is a one-time change per account and region, and it needs approval like any deploy. Check whether the account is already bootstrapped (a `CDKToolkit` stack) before suggesting it.
- `cdk deploy` and `cdk destroy` change real infrastructure: hand over the exact command with the stack names and the diff summary. Keep the default `--require-approval broadening` (it prompts on IAM and security-group widening); never add `--require-approval never` or `--force` on your own.
- `--hotswap` and `cdk watch` bypass CloudFormation for faster development deploys and leave the stack drifted. Development accounts only, never production.
- Enable termination protection on stateful stacks (`terminationProtection: true`).
- In CI, deploy with short-lived OIDC credentials that can only assume the bootstrap roles, and promote the same synthesized cloud assembly through environments (`../../engineering-practices/references/ci-and-release.md`).

## Lambda in the CDK

- `NodejsFunction` bundles TypeScript or JavaScript with esbuild; `PythonFunction` (alpha package) bundles Python with Docker. Pin the runtime explicitly (for example `Runtime.NODEJS_22_X`) and the architecture (`Architecture.ARM_64` is usually cheaper per unit of work; test native dependencies on it).
- Grant access with L2 grant methods (`table.grantReadData(fn)`), which produce scoped policies, instead of writing `*` statements.
- Set log retention or a log group explicitly; Lambda log groups otherwise keep data forever.

## Done when

- [ ] Build, unit tests and `cdk synth` succeed, and cdk-nag findings are fixed or suppressed with a reason.
- [ ] `cdk diff` was run for every affected stack, and replacements, deletions and IAM or network widening are listed for the user.
- [ ] Stateful resources have explicit removal policies, their stacks have termination protection, and no refactor changes their logical IDs.
- [ ] No deploy, bootstrap or destroy ran without the user's explicit go-ahead.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Diff replaces a bucket or table after a refactor | Construct ID or path changed | Restore the path, `overrideLogicalId`, or use stack refactoring |
| "Export cannot be deleted as it is in use" | Removing a cross-stack reference in one step | Two deployments with `exportValue`, or SSM parameters |
| Lookup fails or returns a dummy value | Stack has no explicit `env`, or context cache missing | Set `env`; run synth with credentials once and commit `cdk.context.json` |
| Deploy fails with "already exists" | Fixed physical name on a resource being replaced | Remove the physical name, or retain and import |
| A `Token` string appears where a value was expected | Using a deploy-time value in synth-time logic | Branch on inputs known at synth time, or use CloudFormation conditions |
| Template exceeds size or resource limits | One stack holds too much | Split by lifecycle into more stacks or nested stacks |
