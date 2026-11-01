# Archive design

## What a reader should be able to trace

A reported number should lead to its physical problem, uncompressed source,
compressed circuit, comparator checkpoint, verification record, and work ledger.
The archive separates recorded evidence from the scripts used to inspect it.

| Material | Storage | Reason |
| --- | --- | --- |
| Frozen code, guides, checksums, and small tables | Git | Reviewable changes and stable paths |
| Large original and extracted records | Fixed private release asset | Content-addressed retrieval without large Git objects |
| Reconstructed tables and figures | Local `reproduced/` directory | Derived outputs stay separate from source records |
| New compression attempts | New `execution/` directory | Existing results remain untouched |

## Original bytes and derived views

The source index checked 834 original file hashes. Mixed-condition records were
non-destructively extracted into full-orbital subsets with the original hash and
extraction locator retained. Identical progress/final files use path aliases;
their equality does not collapse separate evaluation events.

The current release contains 1,270 content-addressed objects. Logical source paths
resolve through [archive-manifest.json](../data/metadata/archive-manifest.json).
Scope and costs are documented separately from presentation choices such as
rounded table cells or the omission of a visible provenance column.

The 22-condition current application and 41-condition historical collection have
different evidential roles. Historical missingness, stopping conditions, and
partial certificates remain labeled rather than being promoted to current-policy
results.

## Immutable release and current documentation

The code/data release is
[artifact-v1.0.0](https://github.com/Reimangod/ceo-circuit-compression/releases/tag/artifact-v1.0.0).
Its tag, assets, data hashes, and frozen implementation remain unchanged when the
maintained English documentation or CI improves. New figures in `docs/assets/`
are explanatory views derived from the same recorded selections.

The GitHub source ZIP alone does not contain release assets. A future complete
public deposit must include the data packages, code, checksums, licenses, and
version information. No DOI has been registered, and this documentation update
does not change repository visibility or publish a new scientific result.

## Attribution and publication

The upstream CEO code and license are preserved under `third_party/`. Original
software uses Apache-2.0; original data and guides use CC BY 4.0. Archived material
retains its own attribution and verification scope. See [NOTICE](../NOTICE) and
[CITATION.cff](../CITATION.cff).

The design follows the practical goal that another researcher can retrieve the
recorded inputs and regenerate the reported comparisons. Useful published
guidance includes:

- Wilson et al., *Good enough practices in scientific computing*, PLOS
  Computational Biology (2017),
  [DOI: 10.1371/journal.pcbi.1005510](https://doi.org/10.1371/journal.pcbi.1005510).
- Smith, Katz, and Niemeyer, *Software citation principles*, PeerJ Computer
  Science (2016), [DOI: 10.7717/peerj-cs.86](https://doi.org/10.7717/peerj-cs.86).

Repository organization supports reproducibility and review. Scientific
interpretation still depends on the recorded comparison, budget, and numerical
conditions described in the [study overview](OVERVIEW.md).
