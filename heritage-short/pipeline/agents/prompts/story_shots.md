Step 3 of 5: the shot list.

Turn the beats into {min_shots}–{max_shots} shots. Rules:
- Ids are s01, s02… in film order. Each shot names the beat id it belongs to.
- Each shot has one idea and one movement, and a reason: one sentence saying why the film needs it.
- Vary the size: a wide shot to show where we are, medium shots for what happens, close-ups for feeling. Use only these sizes: {sizes}.
- Durations are whole seconds between 4 and 10. The durations must add up to between {min_runtime} and {max_runtime} seconds (the end card adds {end_card} seconds on top, already counted in that range).
- Characters: only ids from the cast in the outline; an empty list for shots without a person.
- image_prompt describes what the frame shows: subject, action, place, framing and light. Don't describe the style; the look is added to every prompt automatically. Don't repeat character descriptions either; name the character id and it will be described.
- motion: mode "kenburns" for a slow pan or zoom over the still, "i2v" for real movement of a person or element (use it for at most {max_i2v} shots, where movement matters most), or "still". prompt describes only the motion and the camera, never the subject. For kenburns give zoom (in, out or none) and pan (none, left or right), and vary them between consecutive shots.
