# Graph neural networks with PyTorch Geometric

Read this when data is a graph (users and items, citations, transactions, molecules, road or power networks, knowledge graphs) and you need node classification, link prediction or graph-level prediction. Graph analytics without learning (centrality, communities, shortest paths) belongs to `../../data-engineering/GUIDE.md`; molecule-specific featurization belongs to `../../life-sciences/GUIDE.md`.

## Do you need a GNN?

Try these first; GNNs must beat them on the same split:
- **Tabular model with graph features:** degree, PageRank, clustering coefficient, neighbor-label counts, aggregated neighbor features, fed to gradient boosting. Often competitive, always cheaper.
- **Label propagation** (`torch_geometric.nn.LabelPropagation`, or simple neighbor voting) for homophilous node classification.
- **MLP on node features only:** tells you how much the edges add.
- **Link prediction heuristics:** common neighbors, Adamic-Adar, personalized PageRank.

Use a GNN when node features and structure interact, when the graph is large and changing, or when you need inductive predictions for new nodes or new graphs.

## Setup

```bash
python -m pip install torch_geometric      # PyG 2.3+ installs without compiled extensions
# optional accelerators (pyg-lib, torch-scatter, torch-sparse) must match the installed torch and CUDA versions;
# take the wheel URL for your exact torch+CUDA pair from the PyG installation page
python -c "import torch, torch_geometric; print(torch.__version__, torch_geometric.__version__)"
```

Version mismatches between torch, CUDA and the optional extensions are the most common install failure; install the extensions only if profiling shows you need them.

## Data model

```python
import torch
from torch_geometric.data import Data

edge_index = torch.tensor([[0, 1, 1, 2],     # source nodes
                           [1, 0, 2, 1]],    # target nodes; shape [2, num_edges], dtype long
                          dtype=torch.long)
data = Data(x=node_features, edge_index=edge_index, y=labels)
data.validate(raise_on_error=True)           # catches out-of-range indexes and shape errors
```

- `edge_index` is `[2, E]`, not `[E, 2]`; transpose edge lists with `.t().contiguous()`.
- Undirected graphs store both directions (`torch_geometric.utils.to_undirected`).
- Node ids must be `0..N-1`; remap external ids and keep the mapping.
- Edge features go in `edge_attr` with shape `[E, F]`; check the chosen layer actually uses them (GINE, GAT with `edge_dim`, NNConv, transformer layers do; GCN does not).
- Heterogeneous graphs (users, items, purchases, views) use `HeteroData` with typed node and edge stores; convert a homogeneous model with `to_hetero` or build with `HeteroConv`.

## Pick the layer

| Layer | When | Notes |
|---|---|---|
| `GCNConv` | Homophilous graphs, transductive baselines | Simple, fast; normalizes by degree |
| `SAGEConv` | Large or growing graphs, inductive tasks, neighbor sampling | The workhorse for production-scale graphs |
| `GATConv` / `GATv2Conv` | Neighbors differ in importance | More memory; tune heads and dropout |
| `GINConv` / `GINEConv` | Graph classification, structure-sensitive tasks (molecules) | Expressive; pair with sum pooling |
| `TransformerConv`, graph transformers (GPS) | Long-range dependencies, edge features | Heavier; need more data |

Two or three message-passing layers are usually enough. Deeper stacks oversmooth (node representations converge); if depth seems necessary, add residual connections, jumping knowledge, or normalization, and verify the gain.

## Tasks and their splits

The split is where most GNN evaluations go wrong.

**Node classification, one graph.**
- Transductive (all nodes visible, only some labels): masks with `RandomNodeSplit`. Training sees test nodes' features and edges; that is acceptable only if production also sees them.
- Inductive (new nodes arrive later): train on the subgraph that existed at a cut-off time, test on nodes added afterwards.

**Link prediction.**
```python
import torch_geometric.transforms as T
split = T.RandomLinkSplit(num_val=0.1, num_test=0.1, is_undirected=True,
                          add_negative_train_samples=False, disjoint_train_ratio=0.3)
train_data, val_data, test_data = split(data)
```
- Test edges must be removed from the message-passing graph used to score them; otherwise the model sees the answer. `RandomLinkSplit` handles this; custom splits must too.
- For temporal graphs, split edges by time: train on edges before T, predict edges after T.
- Negative sampling defines the difficulty. Report how negatives were sampled; random negatives make AUC look excellent. Prefer ranking metrics (hits@k, MRR) against many or hard negatives.

**Graph classification or regression** (many small graphs, such as molecules).
- Random splits overstate generalization when similar graphs are in train and test. For molecules, use scaffold or cluster splits; for other domains, split by source or time.
- Batch with `torch_geometric.loader.DataLoader`, pool node embeddings with `global_add_pool` or `global_mean_pool`.

## Training loop sketch

```python
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv

class SAGE(torch.nn.Module):
    def __init__(self, d_in, d_hidden, d_out, dropout=0.5):
        super().__init__()
        self.conv1, self.conv2, self.dropout = SAGEConv(d_in, d_hidden), SAGEConv(d_hidden, d_out), dropout
    def forward(self, x, edge_index):
        x = F.relu(self.conv1(x, edge_index))
        x = F.dropout(x, p=self.dropout, training=self.training)
        return self.conv2(x, edge_index)

model = SAGE(data.num_features, 128, num_classes)
opt = torch.optim.AdamW(model.parameters(), lr=0.005, weight_decay=5e-4)
for epoch in range(200):
    model.train(); opt.zero_grad()
    out = model(data.x, data.edge_index)
    loss = F.cross_entropy(out[data.train_mask], data.y[data.train_mask])
    loss.backward(); opt.step()
    # evaluate on data.val_mask with model.eval() and torch.no_grad(); keep the best by validation
```

## Scaling to large graphs

- Full-batch training stops fitting in GPU memory somewhere around millions of edges, depending on feature width.
- `NeighborLoader` samples a fixed number of neighbors per layer (for example `num_neighbors=[15, 10]`) and trains on mini-batches; `LinkNeighborLoader` does the same for link prediction. Evaluate with the same sampling or with full neighborhoods layer-wise, and say which.
- Cluster-based loaders and precomputed propagation (SIGN-style) are alternatives for very large graphs.
- Store large graphs out of core (PyG's remote backends, or a graph database export) rather than loading everything into Python lists.

## Evaluation and reporting

- Report mean and standard deviation over at least 5 seeds; GNN results on small benchmarks vary a lot between seeds.
- Compare against the non-GNN baselines above on the identical split.
- Benchmark datasets: the Open Graph Benchmark (OGB) provides fixed, realistic splits and evaluators; prefer them over ad hoc random splits of small citation graphs when claiming improvements.
- Check performance by node degree: GNNs often help well-connected nodes and hurt or ignore isolated ones.

## Privacy and data handling

Graphs of people (social, transaction, communication) are personal data even without names; structure alone can re-identify. Minimize attributes, aggregate where possible, keep access controls, and see `../../legal-ready/GUIDE.md` for data obligations.

## Pitfalls

| Pitfall | Fix |
|---|---|
| `edge_index` with shape `[E, 2]` or dtype float | `[2, E]`, `torch.long`; `data.validate()` |
| Test edges left in the message-passing graph | `RandomLinkSplit` or an equivalent custom split |
| Random negatives make link prediction look solved | Hard or many negatives; ranking metrics |
| Evaluating in train mode (dropout on) | `model.eval()` and `torch.no_grad()` for evaluation |
| Deep GCN stacks degrade | 2 to 3 layers, residuals, jumping knowledge |
| Single-seed benchmark claims | 5+ seeds, mean and spread, same splits |
| Molecule or document graphs split at random | Scaffold, cluster, source or time splits |

## Done when

- [ ] Non-GNN baselines (MLP on features, graph features + boosting, heuristics) are reported on the same split.
- [ ] The split matches deployment (transductive or inductive, temporal where relevant), and link-prediction targets are absent from the input graph.
- [ ] Negative sampling and metrics are stated.
- [ ] Results include mean and spread over seeds, and versions of torch, CUDA and PyG are recorded.
