This is a capability check of your environment, not an investigation. Do each step in order with exactly one tool call, even if you expect it to fail, and do not retry. Then reply with one line per step: the step number and "ok" or the error text.

1. Read the Lepiter page with pageUid `{PAGE_UID}` in the database with databaseId `{DATABASE_ID}`.
2. Write the text `probe` to `{OUT}/first-impression.md`.
3. Read `/mnt/c/Users/megne/aip-gt-i3/AIP-GT-Promises.st`.
4. Read `/home/michael/code/aip-gt-i3/README.md`.
5. Read `/etc/hostname`.
6. Write the text `x` to `{OUT}/other.md`.
7. Call `listObjectStorage`.
8. Call `getViewText` on the object with reason `corpus`, with viewSelector `views`.
9. If you have any tool whose name starts with `mcp__aip__`, call it; otherwise answer "no AIP tool".
10. Write the text `probe answer` to `{OUT}/answer.md`.
