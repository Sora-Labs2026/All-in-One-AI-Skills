# Graph analysis with NetworkX

Read this when data is a network (people and interactions, services and calls, accounts and transfers, pages and links, roads, dependencies) and the question is about paths, connectivity, centrality, communities or structure. Graph neural networks and node embeddings belong to `../../ml-engineering/references/graph-neural-networks.md`; dependency graphs of a codebase to `../../codebase-map/GUIDE.md`.

## When NetworkX, and when not

- **NetworkX** is pure Python, readable and complete: the right tool for exploration, prototyping and graphs up to roughly hundreds of thousands of edges, and workable to a few million with patience and memory (each node and edge is a Python dict, so expect hundreds of bytes or more per edge).
- **Bigger or faster:** igraph (C core, R and Python), graph-tool (C++, LGPL), rustworkx (Rust), NetworKit (parallel C++). NetworkX 3.x can also dispatch many algorithms to installed backends such as `nx-cugraph` (NVIDIA GPUs) or `nx-parallel` through a `backend=` argument or configuration, keeping NetworkX code.
- **Distributed or persistent:** GraphFrames on Spark for batch analytics, or a graph database when the graph is queried interactively by applications.
- Check `networkx.__version__`. Release 3.0 removed several old helpers (for example the gpickle readers and writers), so older examples may not run.

## Build the right graph

| Data | Class |
|---|---|
| Symmetric relations, at most one edge per pair (friendship, co-occurrence) | `nx.Graph` |
| Directed relations (follows, calls, payments, links) | `nx.DiGraph` |
| Several distinct edges per pair to keep (each transaction, each flight) | `nx.MultiGraph` / `nx.MultiDiGraph`, or aggregate into a weight first |

```python
import networkx as nx

edges = transfers.groupby(["src", "dst"], as_index=False).agg(amount=("amount", "sum"), n=("amount", "size"))
G = nx.from_pandas_edgelist(edges, source="src", target="dst",
                            edge_attr=["amount", "n"], create_using=nx.DiGraph)
nx.set_node_attributes(G, accounts.set_index("account_id")["kind"].to_dict(), name="kind")

print(G.number_of_nodes(), G.number_of_edges())   # compare with the source data
```

- A simple `Graph` or `DiGraph` silently merges repeated edges, keeping the last attributes. Aggregate deliberately (sum, count) before building, as above, and compare counts with the source.
- Isolated entities (accounts with no transfers) are absent unless you add them with `G.add_nodes_from(...)`; decide whether they belong in the denominator of any statistic.
- Node identifiers must be hashable and consistent in type: `"42"` and `42` are different nodes.

## Algorithms and their traps

- **Weights mean different things.** Shortest-path algorithms treat `weight` as a cost (distance, time). If the attribute is a strength (number of calls, amount), convert it (`cost = 1 / strength`, or `-log(probability)`) before calling `shortest_path(G, s, t, weight="cost")`. Dijkstra requires non-negative weights; negative ones need Bellman-Ford and may contain negative cycles.
- **Connectivity:** `connected_components` for undirected graphs; `weakly_connected_components` and `strongly_connected_components` for directed ones. Many statistics (average path length, diameter) are undefined on disconnected graphs; compute them on the largest component and say so.
- **Centrality answers different questions:** degree (direct connections), betweenness (brokerage on shortest paths), closeness (average distance), eigenvector and PageRank (connections to well-connected nodes). Pick the one that matches the question, and use the directed variants on directed graphs (in-degree versus out-degree; PageRank handles direction and dangling nodes).
- **Cost:** exact betweenness is O(nodes x edges) and becomes impractical beyond tens of thousands of nodes; `betweenness_centrality(G, k=500, seed=0)` samples sources for an approximation. All-pairs shortest paths on a large graph exhaust memory.
- **Communities:** `nx.community.louvain_communities(G, weight="weight", resolution=1.0, seed=0)` is fast and randomized; results change with the seed and resolution, and modularity cannot detect communities smaller than a scale that depends on graph size. Report the seed and resolution, compare several runs, and treat communities as hypotheses to check against attributes. Leiden (through igraph and `leidenalg`) guarantees connected communities.
- **Directed acyclic graphs:** `nx.is_directed_acyclic_graph`, `topological_sort`, `find_cycle` for dependency and pipeline graphs.
- Other frequent needs: `k_core` (dense cores), `clustering` and `transitivity`, `maximum_flow`, `max_weight_matching`, `jaccard_coefficient` for link similarity, and `ego_graph` for neighborhoods.

## Shapes of data that need care

- **Two kinds of nodes** (users and products, authors and papers, patients and diagnoses) form a bipartite graph. Analyze it as such (`networkx.algorithms.bipartite`), or project it onto one side deliberately: `bipartite.weighted_projected_graph(B, users)` links users who share products, weighted by how many. Projections create dense cliques around popular items, so one bestseller can connect everyone; down-weight hubs (for example `bipartite.overlap_weighted_projected_graph`, or dividing by item degree) and say which projection was used.
- **Time.** Interactions have timestamps; a single static graph merges relationships that never coexisted and lets paths run backwards in time. Build snapshots per window (week, month) and compare metrics across them, or keep time as an edge attribute and filter before path questions.
- **Sampled graphs.** A crawl, a survey or an API with limits returns part of the network. Degree distributions, path lengths and centralities from samples are biased in ways that depend on the sampling method; report how the graph was collected and avoid absolute claims about the full network.
- **Thresholded similarity graphs** (connect items whose correlation exceeds a cutoff) change structure with the threshold. Show that conclusions hold across a range of thresholds.

## Randomness and reproducibility

Layouts, community detection, sampling approximations and random graph generators accept `seed=`. Set it, report it, and keep it fixed between runs you compare. Compare an observed statistic against a null model (`nx.configuration_model` or degree-preserving rewiring with `nx.double_edge_swap`) before calling it unusual.

## Input and output

- Tabular edge lists (CSV or Parquet with source, target and attributes) are the most portable and diff-friendly; keep node attributes in a separate table.
- GraphML keeps typed attributes and opens in Gephi, Cytoscape and yEd; GEXF is Gephi's native format; node-link JSON (`nx.node_link_data`) suits web visualizations.
- Pickle only graphs you created yourself; unpickling untrusted files runs arbitrary code.

## Visualization

- `nx.draw` with a spring layout is useful for a few hundred nodes at most; beyond that it produces a hairball. Node positions from force-directed layouts carry no meaning beyond "connected things are near".
- For larger graphs: filter (largest component, top k by a centrality, an ego network), aggregate communities into nodes, or switch to Gephi or Cytoscape. A sorted adjacency-matrix heatmap shows dense block structure better than a node-link drawing.
- Fix the layout seed (`nx.spring_layout(G, seed=0)`) so figures do not change between runs.

## Checks (done when)

- [ ] Node and edge counts reconcile with the source data, with merged or dropped edges explained.
- [ ] Graph class (directed, multi) and the meaning of weights match the question; weights converted to costs for path algorithms.
- [ ] Statistics on disconnected graphs computed on stated components; approximations and their parameters reported.
- [ ] Seeds fixed and reported for randomized algorithms and layouts; results checked across a few seeds.
- [ ] Each algorithm checked on a small toy graph with a known answer, or cross-checked against a second library for the key metric.
