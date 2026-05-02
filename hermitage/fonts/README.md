# Bundled Fonts

Hermitage ships these fonts so the typography is identical on every machine,
regardless of what's installed system-wide. They're registered at runtime via
`PangoCairo.FontMap.add_font_file()` (see `hermitage/typography.py`) and never
copied to the user's font directory.

| File | Family | Role | License |
|---|---|---|---|
| `Fraunces-Variable.ttf` | Fraunces | Display — Codex hero title, large headings | OFL 1.1 |
| `Fraunces-Italic-Variable.ttf` | Fraunces Italic | Display italic | OFL 1.1 |
| `InterVariable.ttf` | Inter | Body — synopsis, metadata, UI chrome | OFL 1.1 |
| `InterVariable-Italic.ttf` | Inter Italic | Body italic | OFL 1.1 |
| `IBMPlexSansCondensed-Regular.ttf` | IBM Plex Sans Condensed | Tag pills, section labels | OFL 1.1 |
| `IBMPlexSansCondensed-Medium.ttf` | IBM Plex Sans Condensed | Tag pills, section labels | OFL 1.1 |
| `IBMPlexSansCondensed-SemiBold.ttf` | IBM Plex Sans Condensed | Tag pills, section labels | OFL 1.1 |

Per-family licenses live in `OFL-Inter.txt`, `OFL-Fraunces.txt`, and
`OFL-IBMPlex.txt` in this directory.

Sources:
- Inter — https://github.com/rsms/inter (v4.1)
- Fraunces — https://github.com/undercasetype/Fraunces
- IBM Plex Sans Condensed — https://github.com/IBM/plex (@ibm/plex-sans-condensed@2.0.0)
