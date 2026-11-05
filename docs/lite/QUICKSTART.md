# Quick start

Run the source tree with Python 3.11+ or execute `semcrys-lite.pyz`.

```powershell
python -m semcrys_lite demo
python -m semcrys_lite compare input.bin
python -m semcrys_lite encode input.bin compact.crys
python -m semcrys_lite decode compact.crys restored.bin
```

The default is `BINARY` + `PACKED_VARINT` + outer `NONE`. To inspect the
logical event body, use `inspect --body`. To see an intentionally transparent
wire form, select:

```powershell
python -m semcrys_lite encode input.bin inspectable.crys --envelope TEXT --body-representation JSON_EVENTS
```

For a local self-contained byte legend:

```powershell
python -m semcrys_lite encode input.bin output.crys --profile L:BYTE_LOCAL_DENSE
```

For a caller-held external legend, supply `--legend`; external placement is the
default for supplied legends. Use `--legend-placement SELF_CONTAINED` only when
embedding is intentional.

Full-unique occurrence projection requires the optional concealment dependency,
a 32-byte-or-longer key, and an external moving legend. It hides public equality
in the tested artifact but carries `security_claim: NONE`.
