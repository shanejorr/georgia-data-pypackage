# For LLM agents

This site is built to be read by language-model agents as well as people.

## Markdown pages

Every HTML page has a Markdown twin at the same address with `.md` in place
of `.html`:

| Page                                                                   | Markdown                                                             |
|------------------------------------------------------------------------|----------------------------------------------------------------------|
| `https://georgiacivicdata.org/py/index.html`                           | `https://georgiacivicdata.org/py/index.md`                           |
| `https://georgiacivicdata.org/py/articles/analysis.html`               | `https://georgiacivicdata.org/py/articles/analysis.md`               |
| `https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.html` | `https://georgiacivicdata.org/py/generated/georgiacivicdata.rows.md` |

Each HTML page also names its twin in its `<head>`:

```html
<link rel="alternate" type="text/markdown" href="analysis.md">
```

The Markdown pages hold the same text, code and outputs as the HTML pages,
with tables as plain text.

## llms.txt

- [`llms.txt`](https://georgiacivicdata.org/py/llms.txt) lists every page's
  Markdown address with a one-line description, following
  [https://llmstxt.org](https://llmstxt.org).
- [`llms-full.txt`](https://georgiacivicdata.org/py/llms-full.txt) holds
  every page in one file.

## Writing code with the package

- Import it as `import georgiacivicdata as gcd`. There is no API key.
- Find a dataset with `gcd.search("plain words")` or `gcd.datasets()`, read
  it with `gcd.describe(name)` and `gcd.columns(name)`, then get rows with
  `gcd.rows(name, **filters)`.
- Filters are keyword arguments named after the API's parameters; the
  `filters` table of `gcd.describe(name)` lists every one with its values.
- A missing metric usually means the value was suppressed for privacy, not
  zero. Never add the `all` total to its subgroups, and pool rates from their
  counts instead of averaging them.
- The API itself is documented at [https://georgiacivicdata.org/docs](https://georgiacivicdata.org/docs), and
  Georgia Civic Data also runs an MCP server for agents; see the main site.
