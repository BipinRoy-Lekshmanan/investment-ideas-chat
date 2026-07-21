# data/

This folder holds the source document locally. Nothing in it except this file
is committed to git — see `.gitignore`.

To set it up:

```bash
python prepare_document.py path/to/your-report.pdf
```

This writes `data/document.txt`, which `app.py` reads at startup via
`context.py`. Keep the original PDF here too if you like (`data/document.pdf`
is also gitignored), but only the extracted `.txt` is actually used.
