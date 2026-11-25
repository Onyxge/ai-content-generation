# FAILURES

What broke, what we tried and what fixed it, written when it happens, with the evidence that shows it.

## F1: vertical subtitles ran to three lines (2026-11-25, assemble)

Symptom. All 19 tests passed and every export measured correctly, yet a frame grab of the full-size vertical mock film showed a three-line subtitle. The chunker had produced two lines of up to 42 characters, and libass wrapped the first line again because it was wider than the 720-pixel frame. No test could see this, because the tests check text and numbers, not pixels.

What we tried. We measured the rendered character width from the frame (about 22 px per character at FontSize 11). The first fix shortened vertical lines to 28 characters, which exposed a second problem: a one-word card shown for 0.4 s.

What fixed it. Line length per orientation (28 vertical, 42 horizontal); a smaller vertical font with wider side margins, to stay clear of phone UI; and a balanced chunker that breaks after punctuation. Both rules now have tests (E17).

What it changed. Looking at a rendered frame is now part of checking any change to assembly, alongside the tests.
