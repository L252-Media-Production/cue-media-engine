# Library and playlists

Uploading and organising audio, building playlists, folders, favorites and hidden folders.

- **Library** (left of the web page): every audio file is stored **once**, in `media/library/`. Upload with
  the orange upload button beside the library search box (choose Files or Folder) or by dragging files and folders together anywhere onto the library. A folder becomes a new library folder, keeping any folders inside it; wav, mp3, ogg and flac files are uploaded as they are; with ffmpeg installed, many more formats are accepted too (see **ffmpeg (optional)** below). Hidden files are skipped. Drop a folder onto an existing library folder to put it inside that folder. Files being uploaded appear as rows at the top of the library with a progress bar (a failed one stays until you click it). Each file in a playlist shows a small badge with the number of playlists using it; click the badge to jump to the track in each of those playlists in turn (the reverse of the coloured flag on a playlist row, which jumps to the track in the library). The cross on a folder deletes it; if it is not empty you are asked to confirm, and everything in it is deleted and removed from the playlists.
  Uploading a file whose contents are already in the library reuses the existing file instead of storing a copy.
- **Playlists** (right): lists of references to library files, so the same track can sit in several playlists.
  Create playlists in the web page (the Create button, or drop tracks or a folder on the dashed box beside it; a green confirmation appears at the bottom right, and clicking it scrolls to the new playlist). Playlists are what Companion sees: `/0/1` = second track of the first playlist.
- **Add tracks to a playlist:** drag a track from the library onto a playlist (between two rows to choose the
  position), or use the "Add to…" menu on the library row. Dropping audio files from your computer onto a playlist
  uploads them to the library and adds them to that playlist.
- **Reorder:** drag a track by its ⠿ handle, or use ▲ ▼. To send a track to another playlist, drag it onto that playlist.
- **Remove** (in a playlist) takes the track out of that playlist only. The file stays in the library.
- **Delete** (in the library) permanently deletes the file, after a confirmation that lists the playlists it will
  be removed from. It is not moved to a trash folder, so the space is freed immediately.
- **Delete playlist** removes the playlist only; its tracks stay in the library.
- A playing track keeps playing when it is moved, removed or deleted, and the focus cursor stays on the same track.
- **Offline changes:** files you copy into `media/library/` while the player is stopped (sub-folders are fine)
  appear in the library on the next start, and a notice lists what was found or is gone. While the player is running,
  use **⚙ Settings > System > Rescan** (or send `/rescan`). If a playlist points at a file that no longer exists, the track is shown
  in red and kept in place, so the IDs of the other tracks don't shift. Remove it from the playlist when you're ready.
- Companion IDs (`/0/1`) follow playlist order. Reordering or removing tracks changes which track an ID points at,
  so check your buttons after reorganising. Adding a track at the end never changes existing IDs.

### Renaming and reordering playlists

In the web page, each playlist header has a **✎** rename button (or double-click the name; Enter saves, Esc cancels), a **⠿** handle to drag it to a new position,
and a chevron to **collapse** it to just its header (remembered per browser). Playing and focused tracks follow their playlist, and each playlist keeps its
own end-of-track mode.

**Companion buttons use the playlist number** (`/2/0` means the third playlist), so moving a playlist changes which buttons
trigger it. Reorder before programming buttons, or re-check them afterwards. Renaming does not affect any button.

## Folders and renaming in the library

The library follows the real folders under `media/library/`. Make folders in the web page (**＋ Folder** at the top of the
Library, or ＋ on a folder for a sub-folder) or in the file manager, and press **Rescan library** to pick up changes made
outside the page.

- **Move a track:** drag its ⠿ handle onto a folder (a "top level" row appears at the bottom of the list while dragging), or press ✎ and choose a folder.
- **Rename:** ✎ on a track or folder. The window opens right next to the button you pressed, with the name selected, so you can type and press Enter. A track keeps its file type. Playlists, the sound cache and a track that is playing
  follow the new name, so nothing in your playlists breaks.
- **Upload into a folder:** drop audio files from your computer onto a folder row.
- **Delete a folder:** only empty folders can be deleted (✕ is greyed out otherwise).
- Folders whose name starts with `.` or `_` are ignored by the library, so the page will not create them. Use them for files you want kept out of the library.
- Playlists refer to tracks by their path, so moving or renaming a file *outside* the page (in the file manager) shows up as a missing track until you re-add it.
- Searching shows a flat list of matches with their folder.

### Favorite and hidden folders, Collapse all
- **Collapse all / Expand all** are the two plain icon buttons in the Library header (Expand all: chevron down; Collapse all: two arrows pointing inward). The header stays on one row at every width; on a phone the storage text is shortened. They skip hidden folders. Which folders are open or closed is remembered **per browser**.
- **Favorites:** the star on a folder row (filled yellow = favorite; titles *Favorite* / *Unfavorite*). Favorite folders move to a **Favorites** group at the top of the tree (alphabetical), above **All folders** (alphabetical). With no favorites there is no Favorites heading.
- **Hide:** the eye-off button hides a folder (and everything inside it) from the library **tree** only. Its tracks stay in playlists and keep playing, and the search still finds them (see below). Hidden folders are also left out of the track picker of a trigger point.
- **Hidden:** a crossed-out eye with the number of hidden folders (no text; title and label *Hidden folders: N*). It appears in the Library header only while something is hidden. Switch it on to see hidden folders, dimmed and striped, with a *hidden* badge and a blue crossed-out eye (*Hidden. Click to unhide*). Whether it is on is remembered per browser, and it switches itself off when the last folder is unhidden.
- **Search and hidden folders:** matches in visible folders show as before. If some matches are in hidden folders, a message row says *N tracks found in hidden folders · click to show* (also under *No tracks found* when nothing visible matches). Clicking it shows only the matching hidden folders, dimmed, each with the unhide eye, and a *Hide these again* row; it does not switch the Hidden toggle, and clearing the search puts them away again.
