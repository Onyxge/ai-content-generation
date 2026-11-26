# DESIGN

Who the film is for, what it should do, how we tested it and what changed because of the tests. The audience and intent section is written and committed before the first real model call; git history shows the order.

## Audience and intent

Written Thu 26 Nov 2026, 00:25 EAT, from Y's answers, before the first story call.

Who watches: Ethiopians on social media, at home and in the diaspora, who love stories from the imperial era and the people around it.
Where and how they watch: on a phone, vertical, scrolling a feed (TikTok, Instagram Reels, YouTube Shorts, Facebook). Often with the sound low or off at first, so the subtitles must carry the story on their own.
What they should feel or understand at the end: the dignity of the people history doesn't name. A man who spent his life unseen was, for one moment, seen by name, and that moment is worth remembering.
Why this story, and why now: it comes from a story Y's grandmother tells about a man who served honey wine at the emperor's palace. Stories like it live in families and rarely reach the screen. The film is inspired by that story; its scenes are imagined.
Logline: A palace server who spent years pouring honey wine for the emperor, unnoticed, is called by his name for one night.
Languages: English first, as the guaranteed version, then Amharic; the user tests pick the main version (ADR-015).
What we will not do: name or portray a real emperor. Y decided on 2026-11-26 that the emperor is "the great emperor": an unnamed, fictional ruler, a short elderly man with an upright posture, never voiced and never in close-up (ETHICS.md).

## Why each shot exists

From `storyboard.json` (v1, with decisions P-0001 to P-0008 applied). Every shot's `reason` is required by the schema; this table is copied from it.

| Shot | Beat | Size | Picture | Why it's in the film |
|---|---|---|---|---|
| s01 | b1 | wide | Ken Burns | Establishes the quiet routine and humble environment where Tesfaye begins his day of palace service. |
| s02 | b1 | insert | Wan 2.2 motion | Shows the craft and steady precision of serving honey wine into the traditional glass flask. |
| s03 | b1 | medium close-up | Ken Burns | Introduces Tesfaye's composed and watchful demeanour as he prepares to serve unnoticed. |
| s04 | b2 | wide | Ken Burns | Sets the stage of the formal evening banquet and the grandeur surrounding the unnoticed server. |
| s05 | b2 | medium | Ken Burns | Captures the dismissive arrogance of the nobleman questioning Tesfaye's significance. |
| s06 | b2 | medium close-up | Wan 2.2 motion | Shows Tesfaye absorbing the mockery with silent restraint and wounded pride. |
| s07 | b3 | wide | Ken Burns | Shows the emperor taking notice and commanding the hall to honor the server. |
| s08 | b3 | close-up | Ken Burns | Highlights the pivotal emotional breakthrough as Tesfaye is recognized by name. |
| s09 | b4 | insert | Ken Burns | Reflects the intimate ritual of his final pour after the hall has emptied. |
| s10 | b4 | medium | Ken Burns | Concludes the film on Tesfaye's quiet private pride and transformed dignity. |

## User test 1: radio cut

Date: [Y: when the radio cut went out] · Storyboard: v1 (`docs/storyboard-history/v1.json`) · Versions played: English radio cut (`outputs/radio/radio_en.mp4`; later with score m1.13) · **[Y: the radio-cut replies aren't recorded yet. The brief needs at least three testers for this round too.]**

Protocol: played once with no introduction, then three questions. In one sentence, what was it about? Which moment stayed with you? Where were you lost or bored?

| Tester (initials, relation to audience) | Version heard | Channel | What they said, in their words | Insight | Change (storyboard version, shot) |
|---|---|---|---|---|---|

What we changed from v1 to v2: …

## User test 2: near-final cut

Date: Thu 26 Nov 2026, evening · Cut: storyboard v1 with decisions P-0001 to P-0008 (`outputs/final/`, built 19:00) · Played: the vertical films (English and Amharic) · Questions: the three from test 1, plus "would you forward it, and to whom?", "could you read the subtitles on your phone?" and, for bilingual testers, "which version would you send to family?" · Answers as Y received them, copied word for word.

| Tester (initials, relation to audience) | Version heard | Channel | What they said, in their words | Insight | Change (storyboard version, shot) |
|---|---|---|---|---|---|
| T1 [Y: initials, relation] | [Y] | [Y] | About: "A short story about heritage and the importance of remembering where we come from." Stayed: "The closing images and the feeling they left behind." Lost or bored: "I wasn't lost, though the middle felt a little slow." Forward: "Yes—to family members who enjoy stories about culture and heritage." Subtitles: "Mostly; they were readable, but a little small in a few moments." Version: "I'd send the Amharic version to family." | The ending lands. The middle (s04–s07, mostly Ken Burns) drags. The subtitles are too small on a phone | Subtitles larger (config, v1 → v2); middle not changed (see below) |
| T2 [Y] | [Y] | [Y] | About: "It showed how memories and traditions connect people to their past." Stayed: "The part where the visuals and narration came together to make the heritage feel personal." Lost or bored: "I wanted a little more context near the beginning." Forward: "Yes—to friends who are interested in Ethiopian culture." Subtitles: "Yes, though the lines moved a bit quickly." Version: "I'd choose the Amharic version, since it would feel more natural for my family." | The opening doesn't say where or who; the subtitle cards change quickly | Opening line gains its place: s01 (P-0009, pending Y) |
| T3 [Y] | [Y] | [Y] | About: "A reflective piece about cultural roots, memory, and passing heritage on." Stayed: "The final moment; it gave the video a thoughtful ending." Lost or bored: "A couple of transitions felt abrupt, but I stayed engaged." Forward: "Yes—to relatives and younger family members as a conversation starter." Subtitles: "They were legible, but I'd make them slightly larger for small screens." Version: "I'd send whichever version is easiest for them to follow—probably Amharic for older relatives." | The hard cuts feel abrupt; the subtitles should be larger | Subtitles larger (same change as T1); transitions not changed (see below) |

Insights across the three:
- **The feeling lands, the plot doesn't.** All three remember the ending, and all three would forward the film. But none of the one-sentence summaries mentions the server, the emperor or the name. People take away "heritage" and "memory", not *this* story. That fits T2's request for more context at the start: the film never says where we are or who he is until the second shot.
- **Subtitles are too small on a phone** (T1, T3) and change quickly (T2). The audience watches with the sound low, so this matters more than it looks.
- **Amharic is the version people would send** (all three).
- **The middle is slow, and the cuts are abrupt** (T1, T3).

What we changed from v1 to v2:
- **Subtitles.** Vertical subtitles go from FontSize 9 to 11, with narrower side margins so that 28-character lines still fit on two lines. Checked on a rendered frame, as F1 requires. This is a config change, so no storyboard version.
- **The opening.** s01's line now says where we are: the emperor's palace in Addis Ababa, in English and Amharic (P-0009, Y to approve; two narration calls).
- **The main version: Amharic** (`meta.primary`, decision P-0010).
- **Not changed: the slow middle and the abrupt cuts.** Crossfades would shift picture against voice in every shot, and shortening shots s04–s07 would push the narration out of its shots. Both need another test round we don't have time for before the deadline. They're the first item for a v3.

Main version chosen: **Amharic** (decision P-0010, Y, 2026-11-26), because all three testers would send the Amharic version to family. `outputs/final/film_am_9x16.mp4` is the main submission, and the English film is the second version.
