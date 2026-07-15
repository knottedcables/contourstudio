Read contour-studio-spec.md — it's the complete brief for this project. I'm an IT manager, not a developer, so explain things in plain terms and don't assume I can debug code myself.

Before writing any code:
1. Set up the project skeleton (folder structure, git init, .gitignore, README stub) and a CLAUDE.md capturing the conventions you'll follow.
2. Give me a one-paragraph summary of your implementation approach and flag anything in the spec that's ambiguous, risky, or that you'd do differently. Wait for my OK.

Then implement milestone by milestone (M1–M7), in order. At the end of each milestone:
- Show me the acceptance-criteria evidence (generated SVG files I can open, screenshots, or test output).
- Stop and wait for my go-ahead before starting the next milestone.

Ground rules:
- Verify as you go: run the test bboxes in §11 after any change to the render pipeline, and keep the unit tests passing.
- Commit at each milestone with a clear message so I can roll back.
- If a third-party service (Overpass, Nominatim, tile server) causes trouble, follow the spec's fail-soft guidance rather than blocking.
- Don't add features beyond the spec without asking; if a milestone is stalling, the spec says saving (M6) and aspect-ratio lock are cut-first.

Start with the skeleton and your approach summary now.
