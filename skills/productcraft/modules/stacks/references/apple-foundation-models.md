# Apple Foundation Models framework (on-device language model)

Read this before adding a feature that uses Apple's on-device language model through the `FoundationModels` framework: summarizing, extracting structured data, classifying or tagging, short generation, or tool calling inside an app. General Swift and SwiftUI practice is in `swift.md` and `swiftui-and-testing.md`. Choosing between an on-device model and a hosted model, evaluating output quality and writing prompts are covered in `../../ml-engineering/GUIDE.md`.

## What it is, and dates

- Announced in June 2025 and shipped with iOS 26, iPadOS 26, macOS 26 and visionOS 26 (September 2025). It gives apps access to the roughly 3-billion-parameter model behind Apple Intelligence, running on the device.
- **Requirements at runtime:** a device that supports Apple Intelligence, Apple Intelligence turned on by the user, a supported language and region, and the model assets downloaded. Any of these can be missing, so availability is a runtime state, not a build setting.
- **Costs and privacy:** no per-request fee or API key, works offline, and prompts and outputs stay on the device. The app still owes users an accurate privacy disclosure for what it does with the results.
- Later OS releases can add capabilities and change model versions. Check the current SDK documentation and the OS versions the project supports before relying on an API in this file; guard newer APIs with `if #available`.

## When to use it, and when not

| Good fit | Poor fit |
|---|---|
| Summarizing or rewriting text the user already has | Questions that need world knowledge or current facts (the model is small and has no browsing) |
| Extracting fields from free text into a Swift type (dates, amounts, entities) | Precise arithmetic, code generation, long multi-step reasoning |
| Classification and tagging (`SystemLanguageModel(useCase: .contentTagging)`) | Anything that must work on every device, including older ones, without a fallback |
| Suggestions the user reviews before anything happens | Decisions with legal, medical, financial or safety consequences |

Design every feature with a path for when the model is unavailable: hide the feature, fall back to non-AI behavior, or offer a hosted model with the user's consent and a separate privacy disclosure.

## Availability first

```swift
import FoundationModels

let model = SystemLanguageModel.default
switch model.availability {
case .available:
    showSummarizeButton = true
case .unavailable(.deviceNotEligible):
    showSummarizeButton = false              // never offer it on this device
case .unavailable(.appleIntelligenceNotEnabled):
    showEnableHint = true                    // explain where the setting is; do not nag
case .unavailable(.modelNotReady):
    showSummarizeButton = false              // assets still downloading; check again later
case .unavailable:
    showSummarizeButton = false
}
```

Re-check availability when the app returns to the foreground; users can change the setting at any time.

## Sessions, instructions and prompts

- `LanguageModelSession(instructions: ...)` holds a conversation. **Instructions** are the developer's fixed rules (role, style, length, what to refuse) and take priority over prompts. **Prompts** carry the request and user content.
- Never put user-provided text into the instructions; keep it in the prompt, clearly delimited. User text can try to override instructions (prompt injection), and tool calls widen what an injected instruction could trigger.
- **Single-turn features** (summarize this note) create a fresh session per request. Multi-turn features reuse a session; its transcript grows with every exchange.
- **One request at a time per session:** check `session.isResponding` (and disable the button) before sending another; use separate sessions for independent parallel work.
- `session.prewarm()` when the user is about to need it (opening the screen) reduces first-response latency.
- `GenerationOptions` sets sampling and temperature. Greedy sampling (`GenerationOptions(sampling: .greedy)`) makes output more repeatable for tests and for extraction tasks.

## The context window

- The on-device model's context window was 4,096 tokens per session in the 26.0 releases, shared by instructions, prompts, outputs, tool definitions and tool results. Exceeding it throws `LanguageModelSession.GenerationError.exceededContextWindowSize`.
- For long input, split it into chunks, summarize each in its own session, then combine summaries. For long conversations, start a new session seeded with a short summary of the old transcript.
- Keep instructions short; every token there is spent on every request in the session.

## Structured output with `@Generable`

Generate Swift values instead of parsing free text:

```swift
@Generable
struct ExpenseDraft {
    @Guide(description: "Merchant name as written on the receipt")
    var merchant: String
    @Guide(description: "Total amount in minor units, for example cents", .range(0...10_000_000))
    var totalMinorUnits: Int
    @Guide(description: "ISO 4217 currency code, three letters")
    var currency: String
    @Guide(description: "One-sentence note for the expense report")
    var note: String
}

let session = LanguageModelSession(instructions: "Extract expense fields from receipt text. Do not invent values.")
let draft = try await session.respond(to: receiptText, generating: ExpenseDraft.self).content
```

- `@Generable` works on structs and enums; `@Guide` adds a description and constraints (numeric ranges, array counts and others; check the SDK for the full list).
- **Properties are generated in declaration order.** Put fields the later ones depend on first, and summary-like fields (a note, a title) last so they can draw on what was generated before.
- Constrained decoding guarantees the shape, not the truth: validate values (currency against a list, amounts against the source text) and show the result for the user to confirm.
- **Streaming:** `session.streamResponse(to:generating:)` yields snapshots of a partially generated value (each property optional until generated), which suits progressive UI. Snapshots replace each other; they are not text deltas to append.

## Tool calling

- A tool is a type conforming to `Tool` with a `name`, a `description`, `@Generable` `Arguments`, and an async `call(arguments:)` that returns content the model can read. Pass tools when creating the session; the model decides when to call them.
- Tool output counts against the context window; return compact results (a few lines, not whole records).
- **Treat tool arguments as untrusted input.** The model chose them, possibly steered by user or document text. Validate them, scope them to the signed-in user's data, and never let a tool perform an irreversible or external action (sending, paying, deleting) without an explicit confirmation step in the UI.
- Errors thrown by a tool surface as `LanguageModelSession.ToolCallError` with the underlying error; map them to a useful message.

## Errors and guardrails

| Error case | Meaning | Handle by |
|---|---|---|
| `exceededContextWindowSize` | Too many tokens in the session | Chunking, or a fresh session with a summary |
| `guardrailViolation` | Apple's safety guardrails blocked the input or output | A neutral message; do not retry the same content in a loop, and do not try to work around the guardrails |
| `unsupportedLanguageOrLocale` | The language is not supported | Check supported languages up front; fall back |
| `rateLimited` | Too many requests, notably while the app is in the background | Back off; run model work in the foreground |

Guardrails cannot be turned off. Build the UX for refusals and blocked content, especially in apps where users paste arbitrary text.

## Custom adapters

Apple offers a toolkit to train adapters that specialize the system model for a task. Adapters are tied to a specific system model version and must be retrained and re-shipped when that model changes with an OS update; deploying them requires an entitlement from Apple. Exhaust instructions, `@Generable` guides and examples in the prompt first.

## Testing and evaluation

- Put the session behind a small protocol (`protocol ExpenseExtracting { func extract(_ text: String) async throws -> ExpenseDraft }`) so UI and logic tests use a fake and run on any machine.
- Keep a small evaluation set of real-looking inputs (with no personal data) and expected fields; run it on a supported device or a Mac with Apple Intelligence before releases and after OS updates, since the model can change with the OS. Score field accuracy, not wording.
- Profile latency and token use with the Foundation Models instrument in Instruments; iterate prompts in Xcode playgrounds (`#Playground`).
- Test the unavailable paths (each `availability` case), the context-window error with oversized input, guardrail refusals, and cancellation when the user leaves the screen.

## Done when

- [ ] Availability is checked before showing the feature, rechecked on foregrounding, and every unavailable case has designed behavior.
- [ ] User text stays out of instructions; tool arguments are validated and side effects need user confirmation.
- [ ] Inputs that can exceed the context window are chunked, and the error path is tested.
- [ ] Structured output is validated and shown to the user before it is saved or acted on.
- [ ] Logic is tested with a fake model; an evaluation set ran on a supported device, or the report marks it `NOT VERIFIED`.
- [ ] The app's privacy disclosure matches what it stores or sends, including any hosted-model fallback.
