# Legacy canonical documents

Shapes that exist on disk in Vaults and workspaces created by earlier versions of this suite. They
are here so that "the read path still works" is a thing the build checks, rather than a thing a
release note claims.

Each fixture is a wrapper, not a bare document:

```yaml
schema: PIPELINE        # the $defs name in _shared/schemas.yml
writable: false         # would validate_new_write refuse it? false is the interesting case
why: one sentence naming the version or the writer this shape came from
value: {...}            # the document itself, exactly as it would sit on disk
```

`writable: false` is the point of most of them. A fixture that both reads and writes proves nothing
about the read/write split, so `scripts/test_schema_contract.py` asserts that at least one refuses
the strict writer and that all of them pass the tolerant reader.

Add a fixture whenever a field is frozen, a shape is superseded, or a producer is retired. Never
edit one to make a test pass: the file on somebody's disk did not change when the schema did, and
that is exactly what these are here to remember.
