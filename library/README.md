# Library

* `music/<series-id>/*.mp3|wav|m4a` — music beds for a series (one is picked per episode, deterministic by
  episode id). `music/*.mp3` at the top level is the shared fallback. Use royalty-free / licensed tracks only
  (IG may mute reels with copyrighted music). If empty, a procedural bed is generated.
* `sfx/<name>.wav|mp3` — overrides for the built-in procedural SFX. Names: whoosh, pop, ding, boom,
  record_scratch, alarm, cash, click, swoosh_up, thud, tick, riser, sparkle, buzzer, camera_shutter, scribble.
* `voices/` — reference clips for F5-TTS voice cloning (`ref_audio` in a series voice config).
