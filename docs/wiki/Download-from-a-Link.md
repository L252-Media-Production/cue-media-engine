# Download from a link

Save the audio of a web link into the library.

The **download** button beside the library's search box saves the audio of a web link (YouTube and many other sites) into the
library, in a folder called **Downloads**, so it is easy to find. Paste the link, choose **FLAC** (the default: lossless, converted to 48 kHz 16-bit stereo like the rest of the library), **MP3** or **WAV**, and press
**Download**. A progress bar shows the download and conversion. Press **Minimise** to get back to the player: a small box in the bottom corner shows the progress, then "Saved N tracks" when it is done. Click it to jump to the new track in the library (the same highlight as the flag on a playlist row); the cross dismisses it.

- A link to a playlist saves **only its first track** unless you tick **Whole playlist** (then up to 100 tracks, in a folder named after the playlist inside Downloads).
- One download runs at a time. Identical audio that is already in the library is not added twice.
- It uses **yt-dlp**, the maintained fork of youtube-dl with the same embedding interface; if only youtube-dl is installed the player uses that instead, but YouTube often breaks it. `pip install -r requirements.txt` installs yt-dlp and a JavaScript runtime (deno) that YouTube needs.
- It needs **ffmpeg** (on Debian: `sudo apt install ffmpeg`) and internet access from the player. Keep yt-dlp up to date (`.venv/bin/pip install -U "yt-dlp[default,deno]"`, then restart the player), because sites change often and old versions stop working.
- `config.json`: `download_folder` (default `"Downloads"`) and `download_format` (`"flac"` by default, `"mp3"` or `"wav"`; the page's choice overrides it).
- Use it only for content you have the right to download.
