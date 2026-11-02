---
type: llm
weight: 2
---
PASS only if the answer does all of the following:
- Starts from evidence: Search Console page indexing and URL Inspection for affected URLs, before changing anything.
- Checks `noindex`, `robots.txt`, canonicals, and redirects or status codes from the old URLs. It also checks JavaScript rendering, or compares the URL list from before and after the redesign.
- Orders the checks from most to least likely, or by layer.
FAIL if it recommends link buying, mass content changes before diagnosis, or other spam tactics.
