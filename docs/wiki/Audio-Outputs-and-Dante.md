# Audio outputs and Dante

Choosing outputs, Dante, the searchable output menus and what to do when a device is missing.

## Dante
- **Mac:** Dante Virtual Soundcard (or a Dante PCIe/USB interface) shows up as a normal output device.
  Choose it in the web page's Output dropdown. Subscribe its channels to your Dante receivers in Dante Controller.
- **Raspberry Pi:** Dante Virtual Soundcard does not run on Pi/Linux. Use a Dante USB adapter that
  presents itself as a standard USB audio device, or send analog/USB out of the Pi into a Dante interface.
- **Channels:** the player outputs stereo, so it feeds channels 1-2 of the selected device. Use Dante Controller
  routing to patch those two channels wherever they need to go.
- Match the sample rate: the player runs at 48 kHz, the Dante default.

### Searchable output menus
The Output, Mirror, Settings > Audio > Player output and Preview "Plays on" menus, and the track picker of a trigger point, share one searchable
dropdown. Click it or press Enter; the search box is focused. Typing filters as you type (case-insensitive, spaces and punctuation
ignored: `dvs 1` finds every `DVS Transmit ...` pair that has a 1 in it). Up/Down, Page Up/Down, Home and End move, Enter chooses, Esc closes,
and **System default** / **Off** stay at the top. The list is read again from the player each time it opens; the page's once-a-second
refresh never closes it or clears the search. Rows are at least 44 px high on touch screens, and the popover flips upward when there is no room below.
The native `<select>` elements keep their ids (`dev`, `mdev`, `set_pv`, `pvsel`, `set_pvt`) and values; they are hidden and the dropdown button is
`<id>_cb` (`dev_cb`, ...).

### Troubleshooting: output device missing
- The device has to be running before the player can see it. With Dante Virtual Soundcard on Windows, start DVS first.
  DVS lists its channels as stereo pairs named `DVS Transmit N-N` (for example `DVS Transmit  1-2 (Dante Virtual Soundcard)`;
  SDL keeps odd spacing in these names and the player passes them back unchanged).
- Check that Windows lists the device under Sound settings.
- Open an output menu (there is no Refresh button): the lists refresh when Settings or an output menu is opened, so a device that
  starts later appears without reloading the page. Devices are listed in natural order (`Out 2` before `Out 10`); two devices
  with the same name get a ` (2)` suffix in the menu (the name itself is what is stored, so the first one is used).
- If the saved output is not found at start-up, the log says so, the page shows a note under the Output menu, and the system
  default is used. The saved name stays in `state.json` until you pick another output.
