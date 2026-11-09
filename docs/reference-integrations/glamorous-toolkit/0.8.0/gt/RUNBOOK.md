# GT 0.8.0 runbook

Use one **new extraction of GT 1.1.657** for each GT condition. Do not reuse an image from another condition.

A new extraction does **not** give a new Lepiter database. GT stores pages in `C:\Users\<user>\Documents\lepiter\default`, outside the image, and every extraction shares that folder. It can hold earlier pages, including old AIP work. Before each GT condition, with GT closed:

1. Rename `Documents\lepiter` to `lepiter-before-<condition>`.
2. Start the new GT extraction. GT creates an empty `Documents\lepiter`.
3. After the session, close GT. Move `Documents\lepiter` to the researcher area as that condition's record, then rename `lepiter-before-<condition>` back to `lepiter`.

`createPageIn:` also refuses to start while another condition's page exists.

| Environment | Contents |
|---|---|
| Development | the AIP checkout |
| Participant | the corpus directory and the GT image of the condition |
| Researcher | the researcher key, `i1-freeze/aip/` and the scoring material |

## 1. Get GT

Download `GlamorousToolkit-Windows-x86_64-v1.1.657.zip` from the [v1.1.657 release](https://github.com/feenkcom/gtoolkit/releases/tag/v1.1.657). Extract it into a new folder and keep a pristine copy of that folder.

## 2. Build the corpus (operator)

Run this in the AIP checkout. The output directory must be empty. Use a path that the GT image can read.

```bash
python3 docs/reference-integrations/glamorous-toolkit/0.8.0/gt/materialize_corpus.py \
  --repo . --out <corpus directory> --gt
```

The script stops if any file differs from its frozen digest. Give the participant only this directory.

## 3. Check the connection to hosted AIP (GT + AIP only)

Run this in a GT Playground and inspect the result:

```smalltalk
| client answer |
client := GtLMcpClient new.
client transport: (GtLMcpHttpTransport new url: 'https' , '://mcp.daip.io/mcp'; yourself).
answer := (client
	callToolResult: 'get_binding_picture'
	withArguments: { 'request' -> {
		'mode' -> 'query'.
		'bounded_context_id' -> 'catalog-management'.
		'environment' -> 'local'.
		'broker_ids' -> #('kafka:sokol111-local') } asDictionary } asDictionary)
	at: 'structuredContent'.
{ client listTools. answer at: 'outcome'. ((answer at: 'data') at: 'rows') size.
  (answer at: 'snapshot') at: 'snapshot_id' }
```

Expected:
- 7 tools;
- `PARTIAL`;
- `9`;
- `aip:snapshot:v1:7f171aea2d3c5070e6be3dd9c6b53a234ad75934be5724681b95cd3e1705c413`.

If any step fails, report the error text.

## 4. Load the packages

Load `AIP-GT-Promises.st` in every GT condition. Load `AIP-GT-Promises-AIP.st` only in GT + AIP. Load from a Playground:

```smalltalk
CodeImporter evaluateFileNamed: '<path>/AIP-GT-Promises.st'.
CodeImporter evaluateFileNamed: '<path>/AIP-GT-Promises-AIP.st'.   "GT + AIP only"
```

## 5. Create the investigation page

Create the page in the same GT session as step 4. A restart without saving the image loses the loaded packages. A page created by an older package version keeps its old layout, because `createPageIn:` returns an existing page unchanged.

Each condition gets its own page. It holds the task text, the first answer item (first impression), the snippets that open the contracts (and in GT + AIP the binding picture), and then answer items 2–5. Nothing else is on it.

```smalltalk
"GT, no AIP"
GtAipInvestigationPage
	createPageIn: (GtAipPromiseCorpus onDirectory: '<corpus directory>')
	condition: 'GT'.

"GT + AIP"
GtAipHostedClient
	createInvestigationPageIn: (GtAipPromiseCorpus onDirectory: '<corpus directory>')
	condition: 'GT+AIP'.
```

## 6. Smoke gate (I2)

Report each check as pass or fail.

1. The packages load without errors. In the no-AIP image, `Smalltalk globals includesKey: #GtAipHostedClient` is `false`.
2. The Contracts view lists five contracts, the Markdown one as `DEMO-CONTRACT-001` with kind `external contract`. All five show a Raw view. The four YAML contracts also show Fields and Evidence. In the Evidence view, a source opens a local corpus file.
3. The investigation page exists, and its snippets run.
4. Type a test line on the page, save the image, restart GT and reopen the page. The line is still there.
5. GT + AIP only:
   - `GtAipHostedClient session bindingPicture` shows 9 rows with every field.
   - The Evidence view of any row resolves all of its refs.
   - `GtAipHostedClient new expectedSnapshotId: 'x'; bindingPicture` signals `Snapshot mismatch`.
   - `GtAipHostedClient session exportLogTo: '<file>'` writes a file that contains the calls made above through `session`, including evidence drill-down. The log records the session as parsed messages. It is not byte evidence.

**Session log in I3.** Every AIP call of a participant goes through `GtAipHostedClient session`: the page snippet uses it, and its views reuse it for drill-down. At the end of the session, run `GtAipHostedClient session exportLogTo: '<file>'`. A client that a participant creates with `GtAipHostedClient new` is not in that log. Record any such use as a deviation.
6. Report where the database stores its pages: inspect `LeDatabasesRegistry defaultPrimaryDatabase` and copy its storage location. The smoke run on 2026-11-09 reported `Documents\lepiter\default`.

After the smoke test, delete the test page or use a new GT extraction for I3.
