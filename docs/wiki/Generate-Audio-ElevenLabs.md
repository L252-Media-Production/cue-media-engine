# Generate audio with ElevenLabs

Type an announcement, pick a voice from your own ElevenLabs account, listen to it and save it into the library as a normal track.

Useful for a "Voice of God" line, a walk-in message or a last-minute change to the running order. The audio is made only when you
press **Generate**, never when a cue fires, and nothing reaches the Live output until you have saved the track and played it like any
other. Saved tracks play, cue, trim and show in Companion exactly like uploaded ones.

## Connect your account

1. In ElevenLabs open **Developers › API keys** and create a key. Give it these permissions:
   - `text_to_speech`: to make speech (needed);
   - `voices_read`: to list your voices (needed);
   - `user_read`: to show how many characters you have left (optional).
2. In the player open **Settings › System › ElevenLabs**, paste the key and press **Save key**. The group's heading then says
   **Key set · ends in** and the last four characters.
3. Press **Test key**. Green means the key works (if it lacks `user_read`, a note says the usage can't be shown); red means the key is
   not valid or lacks `voices_read`; amber means the player can't reach ElevenLabs (check its internet connection and DNS). Making
   speech can't be tested without spending characters, so a key without `text_to_speech` shows its error on the first Generate.

**Replace** saves a different key, **Remove** deletes it. Tracks you already saved stay in the library.

**Where the key is kept:** only on the player, in the file `elevenlabs.key` next to `config.json`, readable only by the account the
player runs as (on Windows the player limits the file to that account; if that fails the key is still saved and an amber note says so).
It is not in `config.json` or `state.json`, it is never shown again or sent to the page (only its last four characters), and it is never
written to the log, the health report, push messages or Companion variables. Updating the player with the deploy scripts leaves it in
place. The web page has no password, so anyone who can open it can generate audio with your key, but nobody can read the key from it.

## Make a track

Press the **sound-wave button** in the Library header (next to Expand all and Collapse all), or **Open** under Generate audio in Settings.

- **Track name:** becomes the file name and the title in the library (characters a file name can't hold become `_`).
- **Voice:** your voices, with a chip that says where each one comes from (**Own**, **Cloned** or **Library**), and a play button for a
  short sample where ElevenLabs offers one. The list is fetched when the window opens and kept for a few minutes; **Refresh** fetches it
  again. This browser remembers the voice you used last.
- **Text:** what to say. The counter shows the characters it uses.
- **Advanced:** the model (listed only if your key may read the model list; otherwise the default model is used), and the voice's
  stability and similarity. Leave them alone to use the voice's own settings.

The line at the top shows the characters left in your plan this period. **Generate** is turned off, with an amber note, when the text is
longer than what you have left, or longer than the model accepts in one request (10,000 characters for the default model). It usually
takes a few seconds; **Stop** cancels it. One generation runs at a time, and playback is not affected.

When it is ready, the window shows a player with the waveform and length, where the preview plays (your usual Preview choice: this
browser, the player's Preview output, or both), the voice, the text and the characters used. Then:

- **Save to library** puts it in the folder named in **Save to folder** (**Generated** by default; created if needed). If the very same
  audio is already in the library, nothing new is saved and you are told where it is.
- **Edit and regenerate** goes back to the text.
- **Discard** throws it away. Closing the window (or pressing Esc) without saving does the same.

## Change a generated track

Generated tracks show a small **ElevenLabs** label. The pen button beside the rename pencil (**Edit text and regenerate**) opens the window
with the track's stored text and voice. After generating, choose **Save as a new track**, or **Replace** the old one: Replace keeps its
places in every playlist, but clears its A/B points and trigger points (their times belonged to the old audio). Replace is refused while
the track is playing, about to play or previewing.

## Privacy, plan and problems

The text you type is sent to ElevenLabs to make the audio, and the audio is subject to your ElevenLabs plan and terms (characters used,
how you may use the result). The player keeps the text, the voice and the model with each generated track (in `playlists.json`) so it can
be regenerated; it never keeps the key there.

Messages are shown in the window in green, amber or red, in plain words: no key, a key that is not valid, a key without a permission (the
permission is named), no internet or DNS, quota used up, ElevenLabs busy or too many requests (with the wait time when ElevenLabs gives
one, otherwise "try again in a moment"), text too long, and no answer in time. None of them changes the status light or sends a push
message.

The button and the window are for computers and tablets; they are hidden at phone width. Developer details (routes, storage, API calls):
[API reference](../api-reference.md#elevenlabs-290).
