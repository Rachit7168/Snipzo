# Copyright and takedown process

Snipzo only processes content users confirm they own or have rights to (checkbox on upload, import, and publish), and only imports YouTube videos from the user's own connected channel.

## Receiving notices

- Public form: `/takedown` in the web app (stored via `POST /takedown` in the `takedown_requests` table).
- Also publish a designated agent email in the privacy/terms pages (`NEXT_PUBLIC_CONTACT_EMAIL`).
- For DMCA safe harbor in the US, register a designated agent with the US Copyright Office.

## Handling a notice (target: 2 business days)

1. Check the notice is complete: work identified, infringing URL, contact details, good-faith statement.
2. Find the project/clip/publication (match the Short URL against `publications.external_id`).
3. Disable access: delete the renders (`DELETE /projects/{id}`), and if Snipzo published the Short, ask the user to remove it or remove it with the stored channel token.
4. Notify the account owner with a copy of the notice and how to send a counter-notice.
5. Set `takedown_requests.status` to `actioned`, `rejected`, or `countered`, with notes.
6. Repeat infringers: suspend accounts after repeated valid notices.

## Counter-notices

If the user sends a valid counter-notice, forward it to the reporter. Restore the content after 10–14 business days unless the reporter files a court action.
