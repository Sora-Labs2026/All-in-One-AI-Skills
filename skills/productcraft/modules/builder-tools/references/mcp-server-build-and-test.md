# Building and testing an MCP server

Read this when implementing the design from `mcp-server-design.md`. It covers SDK choice and version checks, a complete small Python server, automated tests, manual inspection and agent-level evaluation.

Contents: pick and pin the SDK · project layout · a complete Python server · TypeScript shape · automated tests · manual inspection · evaluation with an agent · done when.

## Pick and pin the SDK

Use an official MCP SDK in the language the team maintains (Python and TypeScript are the most widely used). SDK APIs have changed between major versions, and your memory of them may be out of date, so check what is installed before writing code:

```bash
python3 -c "import importlib.metadata as m; print('mcp', m.version('mcp'))"   # Python SDK
npm ls @modelcontextprotocol/sdk                                               # TypeScript SDK
```

Then read that version's README or migration notes for: the server class and import path, how tools are registered, how tool errors are raised, how structured output is declared, and how to connect an in-process test client. Examples:
- Python SDK 2.x: `from mcp.server import MCPServer`; tool errors with `mcp.server.mcpserver.exceptions.ToolError`; annotation fields in snake_case (`read_only_hint`); `mcp.Client(server)` connects in-process for tests. The example below runs as written on 2.3.
- Python SDK 1.x: the same decorator style on `FastMCP` (`from mcp.server.fastmcp import FastMCP`, errors via `mcp.server.fastmcp.exceptions.ToolError`, annotation fields in camelCase such as `readOnlyHint`); in-process tests through `mcp.shared.memory.create_connected_server_and_client_session`.
- TypeScript SDK: `McpServer` with `registerTool(name, {title, description, inputSchema, outputSchema, annotations}, handler)` and zod schemas.

Pin the major version in the project's dependency file (`mcp>=2,<3`, `"@modelcontextprotocol/sdk": "^1"`) so an upgrade is a deliberate change.

## Project layout

```text
billing-mcp/
├── pyproject.toml          # or package.json; pins the SDK
├── README.md               # tools, required env vars, client config snippet, permissions needed
├── src/billing_mcp/
│   ├── server.py           # tool registration only: thin wrappers
│   ├── client.py           # upstream API client: auth, timeouts, retries, error mapping
│   └── shaping.py          # trims upstream payloads into tool outputs
└── tests/
    ├── test_tools.py       # in-process client tests with a fake upstream
    └── test_stdio.py       # one end-to-end run over stdio
```

Keeping the upstream client and the output shaping separate from registration lets you test them without the protocol, and keeps each tool handler to a few lines.

## A complete Python server (SDK 2.x)

```python
"""notes_server.py: read-only search over a small notes store."""
import base64
import json
import logging
import os
import sys
from typing import Annotated

from pydantic import BaseModel, Field

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

logging.basicConfig(stream=sys.stderr, level=logging.INFO)   # stdout belongs to the protocol
log = logging.getLogger("notes")

NOTES = [{"id": f"n{i:03d}", "title": f"Note {i}", "tag": "ops" if i % 3 == 0 else "dev",
          "body": f"Body of note {i}"} for i in range(1, 58)]


class NoteSummary(BaseModel):
    id: str
    title: str
    tag: str


class SearchResult(BaseModel):
    items: list[NoteSummary]
    total: int = Field(description="Matches across all pages.")
    next_cursor: str | None = Field(description="Pass to the next call to get more; null when there are no more.")


class Note(NoteSummary):
    body: str


mcp = MCPServer("notes", instructions="Read-only access to team notes. Search first, then fetch by id.")
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"o": offset}).encode()).decode()


def _decode_cursor(cursor: str) -> int:
    try:
        return int(json.loads(base64.urlsafe_b64decode(cursor.encode()))["o"])
    except Exception:
        raise ToolError("Invalid cursor. Pass the exact `next_cursor` from the previous notes_search "
                        "result, or omit it to start from the first page.") from None


@mcp.tool(annotations=READ_ONLY)
def notes_search(
    query: Annotated[str, Field(description="Words to match in note titles, case-insensitive. Use '' to list all.", max_length=200)],
    tag: Annotated[str | None, Field(description="Only notes with this tag, e.g. 'ops' or 'dev'.")] = None,
    limit: Annotated[int, Field(ge=1, le=50, description="Maximum notes to return (1-50).")] = 20,
    cursor: Annotated[str | None, Field(description="Opaque `next_cursor` from a previous call.")] = None,
) -> SearchResult:
    """Search team notes by title words and optional tag. Returns ids and titles only; call notes_get for a body.

    Use this first when you do not know a note id."""
    offset = _decode_cursor(cursor) if cursor else 0
    q = query.lower().strip()
    hits = [n for n in NOTES if q in n["title"].lower() and (tag is None or n["tag"] == tag)]
    page = hits[offset:offset + limit]
    end = offset + len(page)
    return SearchResult(items=[NoteSummary(id=n["id"], title=n["title"], tag=n["tag"]) for n in page],
                        total=len(hits), next_cursor=_encode_cursor(end) if end < len(hits) else None)


@mcp.tool(annotations=READ_ONLY)
def notes_get(note_id: Annotated[str, Field(description="Note id such as 'n007', as returned by notes_search.", pattern=r"^n\d{3}$")]) -> Note:
    """Fetch one note, including its body, by id."""
    for n in NOTES:
        if n["id"] == note_id:
            return Note(**n)
    raise ToolError(f"No note with id '{note_id}'. Call notes_search to find valid ids.")


if __name__ == "__main__":
    if not os.environ.get("NOTES_TOKEN"):
        log.warning("NOTES_TOKEN is not set; using built-in sample data only")
    mcp.run()   # stdio; mcp.run("streamable-http", host="127.0.0.1", port=8000) for HTTP
```

What it shows: typed parameters with descriptions and bounds become the input schema; pydantic return types become the output schema and structured content; `ToolError` messages reach the model as recoverable errors; pagination uses an opaque cursor; logs go to stderr.

## TypeScript shape

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({ name: "notes", version: "1.0.0" });

server.registerTool(
  "notes_get",
  {
    title: "Get note",
    description: "Fetch one note, including its body, by id. Use notes_search first if you do not know the id.",
    inputSchema: { note_id: z.string().regex(/^n\d{3}$/).describe("Note id such as 'n007'") },
    annotations: { readOnlyHint: true, openWorldHint: false },
  },
  async ({ note_id }) => {
    const note = NOTES.find((n) => n.id === note_id);
    if (!note) {
      return { isError: true, content: [{ type: "text", text: `No note with id '${note_id}'. Call notes_search to find valid ids.` }] };
    }
    return { content: [{ type: "text", text: JSON.stringify(note) }], structuredContent: note };
  },
);

await server.connect(new StdioServerTransport());   // console.error for logs; console.log would corrupt stdio
```

If you declare an `outputSchema`, every successful result must include matching `structuredContent`.

## Automated tests

Test through a real client session, in process, so schemas, validation and error mapping are exercised exactly as a host would see them. With the Python SDK 2.x and the standard library's `unittest`:

```python
import sys
import unittest

from mcp import Client, StdioServerParameters

import notes_server


class NotesServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_tools_have_schemas_and_hints(self):
        async with Client(notes_server.mcp) as client:
            tools = {t.name: t for t in (await client.list_tools()).tools}
        self.assertEqual(sorted(tools), ["notes_get", "notes_search"])
        self.assertEqual(tools["notes_search"].input_schema["properties"]["limit"]["maximum"], 50)
        self.assertTrue(tools["notes_get"].annotations.read_only_hint)

    async def test_pagination_returns_every_item_once(self):
        seen, cursor = [], None
        async with Client(notes_server.mcp) as client:
            while True:
                args = {"query": "", "limit": 25} | ({"cursor": cursor} if cursor else {})
                data = (await client.call_tool("notes_search", args)).structured_content
                seen += [item["id"] for item in data["items"]]
                cursor = data["next_cursor"]
                if not cursor:
                    break
        self.assertEqual(len(seen), 57)
        self.assertEqual(len(set(seen)), 57)

    async def test_unknown_id_is_an_actionable_tool_error(self):
        async with Client(notes_server.mcp) as client:
            result = await client.call_tool("notes_get", {"note_id": "n999"})
        self.assertTrue(result.is_error)
        self.assertIn("notes_search", result.content[0].text)

    async def test_out_of_range_argument_is_rejected(self):
        async with Client(notes_server.mcp) as client:
            result = await client.call_tool("notes_search", {"query": "x", "limit": 500})
        self.assertTrue(result.is_error)

    async def test_runs_over_stdio(self):
        params = StdioServerParameters(command=sys.executable, args=["notes_server.py"])
        async with Client(params) as client:
            result = await client.call_tool("notes_get", {"note_id": "n003"})
        self.assertEqual(result.structured_content["tag"], "ops")


if __name__ == "__main__":
    unittest.main()
```

Cover at least: tool list and schemas; one success per tool; each documented error (not found, invalid input, permission denied, upstream timeout, rate limit) with the message the model will see; pagination end to end; truncation of oversized results; and one stdio or HTTP round trip so the transport and startup (missing env var, stdout hygiene) are exercised. Replace the upstream API with a fake in tests; never point tests at production data or real accounts.

## Manual inspection

The MCP Inspector is the protocol project's interactive client: `npx @modelcontextprotocol/inspector <command that starts your server>` opens a local web UI to list tools, call them with arguments, and read raw results and errors. Recent versions also have a command-line mode for scripted checks; see its `--help`. It downloads from the npm registry on first use, so check with the user before running it where network access is restricted. Use it to read descriptions and results the way a model will, and to try the wrong inputs a model is likely to send.

## Evaluation with an agent

Unit tests prove the server works; they do not prove an agent can use it. Write 5 to 10 realistic tasks that need several calls ("Which ops note mentions the March outage, and what is its id?"). Give each a single answer a script can compare, and state the expected format in the task ("answer with the id only"). Keep reruns comparable: tasks only read, never depend on each other's results, and use records that will not change. Run them with an agent connected to the server and record: answered correctly, number of calls, errors hit, and tokens. Then read the transcripts: repeated failed calls point to unclear descriptions or schemas, huge results point to missing filters or pagination, and invented ids point to search results that do not carry ids. Change one thing, rerun, compare. The method mirrors skill evaluation (`skill-evaluation.md`).

## Done when

- The design checklist in `mcp-server-design.md` holds.
- Automated tests pass, including error paths and one real transport round trip.
- The Inspector (or an equivalent client) shows the intended names, descriptions, schemas and annotations, or you have said why it could not run.
- The README lists tools, required environment variables and scopes, a client configuration example, and known limits.
- Agent tasks were run and their results recorded, or the hand-off says they were not.
