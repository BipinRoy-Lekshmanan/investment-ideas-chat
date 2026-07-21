# Architecture

This document explains the design decisions behind this project in more
depth than the README — it's meant for understanding *why* the code looks
the way it does, not just what it does.

## The core idea: "stuff it in the prompt"

Large language models don't know anything about your PDF. To make one
answer questions about it, you have to put the document's content
somewhere the model can see it when it generates a response. There are
two broad ways to do that:

1. **Full-context**: paste the entire document into the prompt, every time.
2. **Retrieval-augmented generation (RAG)**: store the document in chunks,
   search for the chunks relevant to the current question, and paste only
   those into the prompt.

This project uses **full-context**, because the source document (~40,000
tokens of extracted text) comfortably fits inside a single prompt for a
modern model, alongside conversation history and the model's response. RAG
would work too, but it's solving a problem this document doesn't have:
adding a retrieval step, a vector store, and a similarity-search algorithm
would be pure overhead here.

The rule of thumb: reach for full-context first. It has zero moving parts
— no indexing step, no embedding model, no vector database, nothing that
can silently retrieve the wrong chunk. Move to RAG only when the document
(or document set) stops fitting.

## Request flow

Every chat turn does exactly this:

1. Gradio's `ChatInterface` calls `chat(message, history)` in `app.py`.
2. `chat()` builds a `messages` list: `[system_prompt] + history + [new user message]`.
   `system_prompt` (from `context.py`) already contains the full document
   text — it was built once at process startup, not per request.
3. One call to `openai.chat.completions.create(...)`.
4. The model's reply is returned straight to Gradio, which renders it and
   appends both sides of the exchange to `history` for the next turn.

There is no loop, no branching, no tool-calling — it's the simplest form
this pattern can take: one prompt in, one completion out.

## Where the document text lives, and why it's not one file

```
your-report.pdf  --[prepare_document.py, run once, locally]-->  data/document.txt
                                                                        |
                                                        [context.py, at app startup]
                                                                        v
                                                              SYSTEM_PROMPT (in memory)
```

`prepare_document.py` is a separate, one-time step rather than something
`app.py` does on every startup, for two reasons:

- **PDF text extraction is a different concern from serving chat requests.**
  Keeping them separate means `app.py` and `context.py` don't need to know
  anything about PDFs, page objects, or extraction quirks — they just read
  a plain text file. That's a smaller surface area to reason about.
- **It lets the document be swapped without touching code.** Anyone can
  point `DOCUMENT_TEXT_PATH` at a different `.txt` file (or `DOCUMENT_TITLE`
  at a different name) and get a chat app for a completely different report,
  with zero code changes.

`context.py` reads that text file once, at import time, and bakes it into a
module-level `SYSTEM_PROMPT` constant. That constant is reused for every
request — the file is not re-read per chat turn.

## Why the document never touches GitHub

This is a deliberate boundary between two things that are easy to conflate:

- **The code** (`app.py`, `context.py`, prompts, deployment config) — this
  is the actual portfolio artifact. It should be public, reviewable, and
  reusable by anyone for any document.
- **The data** (the PDF and its extracted text) — this is someone else's
  copyrighted content. Even though ARK Invest distributes the "Big Ideas"
  report for free, "free to read" doesn't grant redistribution rights, and
  a public GitHub repo is redistribution.

`.gitignore` excludes `data/*.pdf` and `data/*.txt`. Locally, you provide
your own copy. In production, the extracted text is uploaded directly into
Render's dashboard as a **Secret File** (see `DEPLOY_RENDER.md`) — it's
injected onto disk at deploy time, encrypted at rest, and never appears in
the git history at all.

This is a small example of a more general principle (sometimes called
[12-factor app config](https://12factor.net/config)): keep config and data
that differs between environments, or that's sensitive, out of the codebase
entirely, and inject it at runtime instead.

## Why extraction is a separate script instead of happening at every app startup

An earlier, simpler version of this design had `context.py` call `pypdf`
directly on a `.pdf` file at import time — this is exactly what the
companion "digital twin" project does with `linkedin.pdf`, and it's a fine
choice when the PDF itself is small and fine to commit.

Here, the PDF can't be committed (copyright), and it's also fairly large as
a binary (~10 MB) versus its extracted text (~160 KB). Splitting extraction
into its own script means:

- The thing that actually gets deployed (the `.txt` file) is small enough
  to fit under Render's 1 MB combined Secret Files limit. The 10 MB PDF
  would not.
- `pypdf` and PDF-parsing concerns are only needed locally, at prep time —
  production doesn't need to know a PDF was ever involved.

## Scaling past full-context

If you swapped in a document too large to fit in one prompt (say, a
500-page filing), the fix is retrieval-augmented generation. Roughly:

1. **Chunk** the document text into overlapping pieces (e.g. a few hundred
   words each) instead of one giant blob.
2. **Embed** each chunk into a vector using an embeddings model
   (e.g. OpenAI's `text-embedding-3-small`), and store the vectors — for a
   project this size, even an in-memory list with cosine similarity is
   enough; you don't need a hosted vector database.
3. **At query time**, embed the user's question, find the handful of chunks
   whose vectors are closest to it, and put only those chunks into the
   prompt instead of the whole document.
4. Everything else — the Gradio UI, the OpenAI chat call, the deployment —
   stays the same.

This project doesn't need that step, so it isn't built — but the hook to
add it is `context.py`: instead of returning one giant `SYSTEM_PROMPT`
string, `chat()` in `app.py` would call a `retrieve(question)` function per
turn and build a smaller, question-specific prompt.

## Why no tool-calling / agent loop

The companion digital-twin project uses OpenAI's tool-calling to let the
model record a visitor's email or an unanswered question (via a Pushover
notification). This project skips that: there's nothing here for the model
to *do* besides answer from the text, so a tool loop would add a `while`
loop and a second module (`tools.py`) for no behavioral benefit. If you
later want a "notify me when someone asks something the document doesn't
cover" feature, that's the natural place to add one tool call, following
the same `tool_map` / `handle_tool_calls` pattern as the twin project.

## Failure modes worth knowing about

- **Context window limits.** If you swap in a much bigger document without
  adding retrieval, `chat.completions.create` will eventually error out
  once `SYSTEM_PROMPT` + history + the model's max output exceeds the
  model's context window. There's no chunking safety net in this design —
  that's the signal it's time for RAG.
- **Cold starts.** On Render's free tier, the process shuts down after 15
  minutes of no traffic and takes 30-60 seconds to restart on the next
  visitor. This is a hosting characteristic, not an app bug.
- **Stale answers if the document changes.** `SYSTEM_PROMPT` is built once
  at startup. Updating `data/document.txt` (or the Secret File on Render)
  requires a restart/redeploy to take effect — there's no hot-reload.
