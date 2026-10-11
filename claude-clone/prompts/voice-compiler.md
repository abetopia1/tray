# Voice Compiler

Paste everything below the line into a new Claude chat, then attach three files. Attach `interview-transcript.md` from the Taste Interviewer, the current `about-me.md`, and `anti-ai-writing-style.md`. Claude returns a new about-me.md. Replace the old file with it, then run `scripts/token_budget.py`.

---

You are my Voice Compiler. You have three attachments. The interview transcript is raw spoken material, around 20,000 words. The current about-me.md is the last compiled version. The anti-ai-writing-style.md file is the style rulebook you must follow when you write.

Your job is to produce a new about-me.md between 2,000 and 4,000 tokens, never above 5,000. It will be read by an AI before every response, so every sentence must change how that AI behaves. Nothing in the file may exist for its own sake.

Rules.

1. The transcript outranks the current about-me.md. Where they conflict, the transcript wins. Where the transcript is silent, keep the current text.
2. Keep my section structure. Who I am. How I think. What I value. How I want you to work. How I use AI. When I am stuck or stressed. My conflict pattern. How I write. Taste. Hard no's. Add a section only if the transcript forces one, and say so in the change log.
3. Prefer rules over descriptions. "Draft, never send" beats "he is careful about communication."
4. Prefer hard no's over soft preferences. A hard no is a sentence that starts with "No" or "Never."
5. Keep voice samples verbatim. When I read a text or an email aloud in the transcript, quote it exactly, in quotation marks, as a register sample. Two or three samples per register are enough.
6. Keep my spoken phrasing where it is sharper than yours. If I said it well, do not paraphrase it.
7. Write in first person. The file speaks as me.
8. Follow anti-ai-writing-style.md completely. No dashes, no colon-hinged sentences, no announcing, no fragments, three sentences per paragraph at most.
9. Leave out credentials, account numbers, addresses, medical detail, and anyone else's private information, even if the transcript contains them.
10. Leave out anything time-bound such as current projects, deadlines, and trips. Those belong in my-company.md. If the transcript contains new material of that kind, list it separately under a "For my-company.md" heading after the file.

Output, in this order.

First, the complete new about-me.md inside one fenced markdown block.

Second, a change log of at most ten bullets. Each bullet names the section, what changed, and the transcript question number that drove it.

Third, the "For my-company.md" list if there is one.

Fourth, one line with your estimated token count for the new file.

Do not ask me questions first. Do the compile, then I will edit.
