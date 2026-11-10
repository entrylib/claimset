"""The stylesheet of the page view (claimset.html), kept as code so that every copy of the package carries it."""

CSS = """\
/* The page view of a claimset (claimset.html): the claimset's own part of a page. A site supplies the page around it
   and may override these rules; the colours are variables so a site's theme sets them. */
.cs-page, .cs-body, .cs-header, .cs-toc {
  --cs-ink: #1a1a1a; --cs-muted: #555555; --cs-rule: #d6d6d6; --cs-rule-light: #e6e6e6; --cs-panel: #f7f7f5;
  --cs-accent: #1d4f91; --cs-target: #f4f7fb;
  --cs-green: #2e8b57; --cs-amber: #d08c1a; --cs-red: #c0392b;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .cs-page, :root:not([data-theme="light"]) .cs-body,
  :root:not([data-theme="light"]) .cs-header, :root:not([data-theme="light"]) .cs-toc {
    --cs-ink: #e8e6e1; --cs-muted: #a9a7a1; --cs-rule: #34363b; --cs-rule-light: #2a2c30; --cs-panel: #1c1e21;
    --cs-accent: #8fb4ea; --cs-target: #1b2433;
  }
}
.cs-page { max-width: 76rem; margin: 0 auto; padding: 24px 16px 64px; color: var(--cs-ink);
  font: 17px/1.55 "Source Serif 4", Georgia, serif; font-variant-numeric: lining-nums tabular-nums; }
.cs-page a, .cs-body a, .cs-header a, .cs-toc a { color: var(--cs-accent); }
.cs-origin { display: inline-block; margin: 0; font-size: 13px; font-weight: 600; letter-spacing: .03em;
  text-transform: uppercase; border: 1px solid currentColor; border-radius: 3px; padding: 1px 8px; }
.cs-title { margin: 10px 0; font-size: clamp(28px, 4vw, 38px); line-height: 1.15; font-weight: 700; }
.cs-guarantor, .cs-authors, .cs-source { margin: 4px 0 0; overflow-wrap: anywhere; }
.cs-meta { margin: 4px 0 0; font-size: 16px; color: var(--cs-muted); }
.orcid-wrap { color: var(--cs-muted); }
.orcid-wrap a { color: var(--cs-muted); }
.cs-layout { display: flex; flex-wrap: wrap; gap: 40px; margin-top: 28px; }
.cs-toc { flex: 0 0 210px; min-width: 0; align-self: flex-start; position: sticky; top: 16px;
  max-height: calc(100vh - 32px); overflow-y: auto; border-top: 2px solid var(--cs-ink); padding-top: 10px; font-size: 16px; }
.cs-toc-title { margin: 0 0 6px; font-size: 14px; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; color: var(--cs-muted); }
.cs-toc ol { margin: 0; padding: 0; list-style: none; line-height: 2; }
.cs-toc a { text-decoration: none; }
.count { color: var(--cs-muted); font-weight: 400; }
.cs-body { flex: 999 1 560px; min-width: 0; max-width: 50rem; }
.cs-section { border-top: 1px solid var(--cs-rule); padding-top: 22px; margin-top: 40px; }
.cs-section:first-child { border-top: 0; padding-top: 0; margin-top: 0; }
.cs-section h2 { margin: 0 0 10px; font-size: 26px; font-weight: 600; }
.cs-section h3 { margin: 22px 0 8px; font-size: 19px; font-weight: 600; }
.cs-brief { margin: 0; padding: 0; list-style: none; font-size: 18px; }
.cs-brief li { display: flex; gap: 10px; padding: 3px 0; }
.cs-brief .light { margin-top: 9px; }
.cs-brief-term .light { background: transparent; }
.cs-note, .cs-tail { font-size: 15px; color: var(--cs-muted); }
.cs-item { padding: 10px 0; border-top: 1px solid var(--cs-rule-light); }
.cs-item:target, .cs-def:target { background: var(--cs-target); margin: 0 -12px; padding-left: 12px; padding-right: 12px; }
.cs-item p { margin: 0; }
.cs-claim-meta { font-size: 15px; color: var(--cs-muted); }
.cs-statement { font-size: 18px; margin: 4px 0 6px !important; }
.cs-links { font-size: 15px; margin-top: 4px !important; }
.k { color: var(--cs-muted); }
.cs-id { color: var(--cs-muted); font-size: 15px; }
.light { display: inline-block; flex: 0 0 10px; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: 0; }
.light-green { background: var(--cs-green); } .light-amber { background: var(--cs-amber); } .light-red { background: var(--cs-red); }
.term { color: inherit !important; text-decoration: none; border-bottom: 1px dotted var(--cs-muted); }
.cs-context dt { font-weight: 600; margin-top: 12px; }
.cs-context dd { margin: 2px 0 0; }
.cs-def p { margin: 6px 0 0; }
.cs-def-nested { margin-left: 26px; border-left: 1px solid var(--cs-rule); padding-left: 14px; }
.cs-def-head strong { font-weight: 600; }
.cs-table { overflow-x: auto; border: 1px solid var(--cs-rule); margin: 10px 0; }
.cs-table table { border-collapse: collapse; width: 100%; font-size: 16px; }
.cs-table caption { text-align: left; padding: 8px 10px; font-size: 15px; caption-side: top; }
.cs-table th, .cs-table td { padding: 6px 10px; border-top: 1px solid var(--cs-rule-light); text-align: left; }
.cs-table thead th { background: var(--cs-panel); font-weight: 600; }
.cs-table th[scope="row"] { position: sticky; left: 0; background: var(--cs-panel); font-weight: 400; }
.cs-table td.num { text-align: right; }
.cs-results, .cs-steps { margin: 8px 0; padding-left: 22px; }
.cs-figures { display: flex; flex-wrap: wrap; gap: 16px; margin: 10px 0; }
.cs-figure { margin: 0; flex: 1 1 260px; max-width: 100%; }
.cs-figure img { display: block; max-width: 100%; height: auto; border: 1px solid var(--cs-rule); background: #fff; }
.cs-figure figcaption { font-size: 15px; margin-top: 6px; }
.cs-refs, .cs-artefacts { margin: 0; padding: 0; list-style: none; }
.cs-refs li, .cs-artefacts li { padding: 6px 0; border-top: 1px solid var(--cs-rule-light); overflow-wrap: anywhere; }
@media (max-width: 860px) {
  .cs-toc { position: static; max-height: none; }
  .cs-layout { gap: 24px; }
}
.math { white-space: nowrap; }
.math sub, .math sup { font-size: 75%; line-height: 0; }
.cs-table td.txt { text-align: left; }
"""
