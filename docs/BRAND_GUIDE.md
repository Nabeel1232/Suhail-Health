# Suhail Health brand and interface assets

Brand name: **Suhail Health**. Product descriptor: **Screening to care coordination**. Tagline: **Guiding every result to care.** The navigation-star idea follows the team's supplied Suhail story; use it as a calm visual reference, not a medical-effectiveness claim.

## Supplied and additional assets

Preserve `logo-original.png` unchanged, with its original proportions and adequate clear space. It is a raster image, not a vector logo. On a dark header, keep its existing light canvas inside a simple light logo tile. Do not stretch, recolor, crop, trace or replace it automatically.

Additional code-native assets are secondary treatments:

- `app-icon.svg` and `favicon.svg`: original simple navigation-star app marks, distinct from the supplied company logo.
- `journey-motif.svg`: a quiet route/star illustration for onboarding and empty states. Decorative only.
- `social-card.svg`: a share-card composition with the product name and tagline. Export to PNG through a renderer for platforms requiring raster metadata.
- `theme.css` and `tokens.json`: application/report tokens. Integrate with the project's styling system rather than adding competing themes.

## Palette

| Token | Value | Usage |
| --- | --- | --- |
| Teal | #006568 | Primary controls, selected navigation, meaningful emphasis |
| Deep ink | #143D3C | Brand text, headings, dark surfaces |
| Gold | #C9A25B | Small decorative star and navigation accent |
| Page | #F4F8F7 | Light application background |
| Surface | #FFFFFF | Panels and forms |
| Text | #173D3B | Main light-mode text |
| Muted text | #526C69 | Supporting text on light surfaces |
| Border | #D4E2DE | Quiet separators |
| Soft teal | #E8F3F0 | Low-emphasis selected/grouped content |

Gold is not small text on white and is not the sole signal for urgent or failed work. Use semantic status colors plus explicit words/icons. Examples: Waiting for acceptance, Needs clinician review, Overdue, Evidence missing, Completed milestone and Care completed. A clinically urgent state must not share a purely decorative gold treatment.

## Type and layout

Use a readable interface font such as Inter or a system sans-serif fallback; for Arabic use a compatible Arabic font such as Noto Sans Arabic or system fallback. Bundle fonts only after checking their licenses. Body text is normally 14-16px; editable fields remain readable on mobile. Use tabular numbers for times and counts, moderate heading sizes, consistent spacing and restrained radii. Avoid an oversized marketing dashboard inside staff workflows.

Use responsive layouts. Staff desktop: navigation, work queue or timeline, and a focused action/evidence area. Patient mobile: one clear next step, responsible team and help action, with progressive detail. Do not compress every milestone into an unreadable horizontal strip. Arabic changes direction and alignment, not just the displayed words.

## Interaction language

Use calm, concrete wording. Prefer Your care team will explain the next step, Referral awaiting acceptance and This case needs more evidence before it can close. Never use Everything is fine or No cancer unless an authorized documented clinical outcome supports that statement. Distinguish AI-prepared drafts from clinician-authored replies.

Every status tells the user what happened, what is next and who is responsible. Required actions have clear labels. A blocked action names the missing evidence or required decision. Model failure is handled by a truthful service state and staff route; do not expose raw stack traces or sensitive prompts.

## Components and accessibility

Use consistent navigation, buttons, tables, form fields, evidence rows, milestone indicators, consultation threads and notifications. Keep focus outlines, semantic HTML, text labels and accessible error associations. Verify contrast and keyboard behavior in the actual app. Pair color with text or icon. Support reduced motion, mobile touch targets and readable RTL.

Keep clinical and developer views separate. A patient needs the next step and care-team contact. A staff member needs source evidence and pending decisions. A developer may need model/configuration and evaluation traces. Do not place model pickers, benchmark scoreboards or chain-of-thought displays in patient journeys.

Print/export reports use the same name, typography and restrained teal headers, with source/version/run metadata and actual measurements. Unmeasured values read Not measured, never a reassuring green zero. Add no Microsoft, hospital, regulator or certification mark without actual permission and supporting status.
