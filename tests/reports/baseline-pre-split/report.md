# CompanionPlayer API test report

- **Started:** 2026-11-03 10:09:47  (98.8 s)
- **Platform:** macOS-26.6.2-arm64-arm-64bit (arm64), Python 3.12.14, pygame 2.6.1
- **ffmpeg (harness machine):** ffmpeg version 8.1.1 Copyright (c) 2000-2026 the FFmpeg developers
- **player.py:** sha256 `f6469695b1b934b5`, 538179 bytes, modified 2026-11-03 10:02:01; git: 68fb05e
- **Target:** {"netloc": "127.0.0.1:18833", "harness_owned": true, "loopback": true, "looks_like_production": false, "config_file": "/private/var/folders/br/dspmm8h96_5bg_srj8mslf840000gn/T/cptest-hmn_93ne/config.json", "managed": true}
- **Instance (as reported by the player):** {"ffmpeg": {"ok": true, "version": "8.1.1", "ffprobe": true}, "devices": ["System audio output device"], "state_health": {"status": "ready", "detail": "Ready"}}

## Summary

| total | passed | failed | errors | skipped |
|---|---|---|---|---|
| 367 | 328 | 38 | 0 | 1 |

Failed tests by severity (1 = no audio/crash/stuck/wrong track on air, 2 = wrong behaviour, 3 = UI/usability glitch, 4 = cosmetic):

| 1 | 2 | 3 | 4 |
|---|---|---|---|
| 0 | 1 | 36 | 1 |

## Failures (most severe first)

### S2 `tests/api/test_ducking.py::test_stopall_while_ducked_does_not_leak_the_duck_into_the_next_play_on_top`

```
AssertionError: the background dipped to 0.1698 although the threshold is 0 dB
assert ([0.1698, 0.2414, 0.319, 0.3989, 0.4774, 0.5462, ...] and 0.1698 > 0.9)
 +  where 0.1698 = min([0.1698, 0.2414, 0.319, 0.3989, 0.4774, 0.5462, ...])
```

### S3 `tests/api/test_fuzz_commands.py::test_odd_values_in_commands_never_cause_a_server_error[0/0/xftime/{v}]`

```
AssertionError: /0/0/xftime/{v}: [('inf', 500), ('-inf', 500), ('1e999', 500)]
assert not [('inf', 500), ('-inf', 500), ('1e999', 500)]
```

### S3 `tests/api/test_fuzz_commands.py::test_odd_values_in_commands_never_cause_a_server_error[0/norm/ref/{v}]`

```
AssertionError: /0/norm/ref/{v}: [('²', 500)]
assert not [('²', 500)]
```

### S3 `tests/api/test_fuzz_commands.py::test_odd_values_in_commands_never_cause_a_server_error[0/norm/track/{v}]`

```
AssertionError: /0/norm/track/{v}: [('²', 500)]
assert not [('²', 500)]
```

### S3 `tests/api/test_fuzz_commands.py::test_odd_values_in_commands_never_cause_a_server_error[0/{v}]`

```
AssertionError: /0/{v}: [('²', 500)]
assert not [('²', 500)]
```

### S3 `tests/api/test_fuzz_commands.py::test_odd_values_in_commands_never_cause_a_server_error[device/{v}]`

```
AssertionError: /device/{v}: [('²', 500)]
assert not [('²', 500)]
```

### S3 `tests/api/test_fuzz_commands.py::test_odd_values_in_commands_never_cause_a_server_error[volume/down/{v}]`

```
AssertionError: /volume/down/{v}: [('²', 500)]
assert not [('²', 500)]
```

### S3 `tests/api/test_fuzz_commands.py::test_odd_values_in_commands_never_cause_a_server_error[volume/up/{v}]`

```
AssertionError: /volume/up/{v}: [('²', 500)]
assert not [('²', 500)]
```

### S3 `tests/api/test_fuzz_commands.py::test_odd_values_in_commands_never_cause_a_server_error[volume/{v}]`

```
AssertionError: /volume/{v}: [('²', 500)]
assert not [('²', 500)]
```

### S3 `tests/api/test_fuzz_commands.py::test_odd_values_in_commands_never_cause_a_server_error[{v}/0]`

```
AssertionError: /{v}/0: [('²', 500)]
assert not [('²', 500)]
```

### S3 `tests/api/test_fuzz_commands.py::test_odd_values_in_commands_never_cause_a_server_error[{v}/mode/stop]`

```
AssertionError: /{v}/mode/stop: [('²', 500)]
assert not [('²', 500)]
```

### S3 `tests/api/test_fuzz_commands.py::test_odd_values_in_commands_never_cause_a_server_error[{v}/play]`

```
AssertionError: /{v}/play: [('²', 500)]
assert not [('²', 500)]
```

### S3 `tests/api/test_fuzz_commands.py::test_odd_values_in_commands_never_cause_a_server_error[{v}/{v}]`

```
AssertionError: /{v}/{v}: [('²', 500)]
assert not [('²', 500)]
```

### S3 `tests/api/test_library.py::test_upload_with_no_file_part_is_harmless`

```
AssertionError: 500 Internal Server Error
  
  Server got itself in trouble
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_playlists.py::test_create_playlist_name_length_is_limited_like_rename`

```
AssertionError: a 5000 character name was accepted (rename limits it to 80)
assert 5000 <= 80
 +  where 5000 = len('xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx...xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
```

### S3 `tests/api/test_playlists.py::test_malformed_bodies_never_cause_a_server_error[/api/playlists/0/add-body0]`

```
AssertionError: /api/playlists/0/add {'files': None} -> HTTP 500 500 Internal Server Error
  
  Server got itself in trouble
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_playlists.py::test_malformed_bodies_never_cause_a_server_error[/api/playlists/0/add-body1]`

```
AssertionError: /api/playlists/0/add {'files': 5} -> HTTP 500 500 Internal Server Error
  
  Server got itself in trouble
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_playlists.py::test_malformed_bodies_never_cause_a_server_error[/api/playlists/0/add-body3]`

```
AssertionError: /api/playlists/0/add {'files': ['tone_a.wav'], 'index': 'x'} -> HTTP 500 500 Internal Server Error
  
  Server got itself in trouble
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_playlists.py::test_non_numeric_playlist_id_in_the_url_is_a_client_error[DELETE-/api/playlists/0/def]`

```
AssertionError: DELETE /api/playlists/0/def -> HTTP 500 (a server error for a typo in the URL)
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_playlists.py::test_non_numeric_playlist_id_in_the_url_is_a_client_error[DELETE-/api/playlists/abc/def]`

```
AssertionError: DELETE /api/playlists/abc/def -> HTTP 500 (a server error for a typo in the URL)
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_playlists.py::test_non_numeric_playlist_id_in_the_url_is_a_client_error[DELETE-/api/playlists/abc]`

```
AssertionError: DELETE /api/playlists/abc -> HTTP 500 (a server error for a typo in the URL)
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_playlists.py::test_non_numeric_playlist_id_in_the_url_is_a_client_error[GET-/api/playlists/abc/triggers]`

```
AssertionError: GET /api/playlists/abc/triggers -> HTTP 500 (a server error for a typo in the URL)
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_playlists.py::test_non_numeric_playlist_id_in_the_url_is_a_client_error[POST-/api/playlists/1.5/rename]`

```
AssertionError: POST /api/playlists/1.5/rename -> HTTP 500 (a server error for a typo in the URL)
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_playlists.py::test_non_numeric_playlist_id_in_the_url_is_a_client_error[POST-/api/playlists/abc/add]`

```
AssertionError: POST /api/playlists/abc/add -> HTTP 500 (a server error for a typo in the URL)
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_playlists.py::test_non_numeric_playlist_id_in_the_url_is_a_client_error[POST-/api/playlists/abc/norm]`

```
AssertionError: POST /api/playlists/abc/norm -> HTTP 500 (a server error for a typo in the URL)
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_playlists.py::test_non_numeric_playlist_id_in_the_url_is_a_client_error[POST-/api/playlists/abc/rename]`

```
AssertionError: POST /api/playlists/abc/rename -> HTTP 500 (a server error for a typo in the URL)
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_playlists.py::test_non_numeric_playlist_id_in_the_url_is_a_client_error[POST-/api/playlists/abc/triggers]`

```
AssertionError: POST /api/playlists/abc/triggers -> HTTP 500 (a server error for a typo in the URL)
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_playlists.py::test_non_numeric_playlist_id_in_the_url_is_a_client_error[POST-/api/playlists/abc/trim]`

```
AssertionError: POST /api/playlists/abc/trim -> HTTP 500 (a server error for a typo in the URL)
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_preview.py::test_preview_ctl_bad_numbers_are_client_errors[body0]`

```
AssertionError: {'cmd': 'seek', 'pos': 'abc'} -> HTTP 500
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_preview.py::test_preview_ctl_bad_numbers_are_client_errors[body1]`

```
AssertionError: {'cmd': 'seek', 'pos': None} -> HTTP 500
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_preview.py::test_preview_ctl_bad_numbers_are_client_errors[body2]`

```
AssertionError: {'cmd': 'seek', 'pos': [1]} -> HTTP 500
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_preview.py::test_preview_ctl_bad_numbers_are_client_errors[body3]`

```
AssertionError: {'cmd': 'vol', 'v': 'abc'} -> HTTP 500
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_preview.py::test_preview_ctl_bad_numbers_are_client_errors[body4]`

```
AssertionError: {'cmd': 'vol', 'v': None} -> HTTP 500
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_preview.py::test_preview_ctl_bad_numbers_are_client_errors[body5]`

```
AssertionError: {'cmd': 'vol', 'v': [1]} -> HTTP 500
assert 500 < 500
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_trim_xfade.py::test_xftime_infinite_value_is_refused_not_a_server_error[-inf]`

```
AssertionError: HTTP 500: 500 Internal Server Error
  
  Server got itself in trouble
assert 500 == 200
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_trim_xfade.py::test_xftime_infinite_value_is_refused_not_a_server_error[1e999]`

```
AssertionError: HTTP 500: 500 Internal Server Error
  
  Server got itself in trouble
assert 500 == 200
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S3 `tests/api/test_trim_xfade.py::test_xftime_infinite_value_is_refused_not_a_server_error[inf]`

```
AssertionError: HTTP 500: 500 Internal Server Error
  
  Server got itself in trouble
assert 500 == 200
 +  where 500 = <500 '500 Internal Server Error\n\nServer got itself in trouble'>.status
```

### S4 `tests/api/test_pages_state.py::test_variable_descriptions_are_complete`

```
AssertionError: ["focus_t0: 'Name of track  in the focused playlist (- when unused)' (a word is missing)", "focus_t1: 'Name of track  ...nused)' (a word is missing)", "focus_t4: 'Name of track  in the focused playlist (- when unused)' (a word is missing)"]
assert not ["focus_t0: 'Name of track  in the focused playlist (- when unused)' (a word is missing)", "focus_t1: 'Name of track  ...)' (a word is missing)", "focus_t5: 'Name of track  in the focused playlist (- when unused)' (a word is missing)", ...]
```

## Skipped

- `tests/api/test_lifecycle.py::test_health_is_ready_and_memory_is_reported`: Skipped: the memory readout is not implemented on macOS

## Timing per endpoint (ms)

| endpoint | calls | min | avg | p95 | max |
|---|---|---|---|---|---|
| `DELETE /api/library` | 16 | 1.4 | 2.0 | 2.6 | 2.9 |
| `DELETE /api/library/folder` | 9 | 1.4 | 2.5 | 4.0 | 4.0 |
| `DELETE /api/playlists/-1` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `DELETE /api/playlists/abc` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `DELETE /api/playlists/abc/def` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `DELETE /api/playlists/{n}` | 458 | 0.4 | 2.5 | 3.9 | 18.3 |
| `DELETE /api/playlists/{n}/-1` | 1 | 1.7 | 1.7 | 1.7 | 1.7 |
| `DELETE /api/playlists/{n}/def` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `DELETE /api/playlists/{n}/{n}` | 6 | 2.1 | 2.6 | 2.8 | 2.8 |
| `DELETE /api/settings` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `DELETE /api/state` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/%2520/%2520` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/%2520/mode/stop` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/%2520/play` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/%2520/{n}` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/%C2%B2/%C2%B2` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/%C2%B2/mode/stop` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `GET /api/%C2%B2/play` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/%C2%B2/{n}` | 1 | 3.3 | 3.3 | 3.3 | 3.3 |
| `GET /api/%C2%BD/%C2%BD` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/%C2%BD/mode/stop` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/%C2%BD/play` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/%C2%BD/{n}` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/%C3%A9/%C3%A9` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/%C3%A9/mode/stop` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/%C3%A9/play` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/%C3%A9/{n}` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/%D9%A3/%D9%A3` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/%D9%A3/mode/stop` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/%D9%A3/play` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/%D9%A3/{n}` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/-0/-0` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/-0/mode/stop` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/-0/play` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/-0/{n}` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/-1/-1` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/-1/mode/stop` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/-1/play` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/-1/{n}` | 2 | 0.4 | 0.5 | 0.6 | 0.6 |
| `GET /api/-inf/-inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/-inf/mode/stop` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/-inf/play` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/-inf/{n}` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/../../../..` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/../../mode/stop` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/../../play` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/../../{n}` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/0x10/0x10` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/0x10/mode/stop` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/0x10/play` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/0x10/{n}` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/1.5/1.5` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/1.5/mode/stop` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/1.5/play` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/1.5/{n}` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/1e999/1e999` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/1e999/mode/stop` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/1e999/play` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/1e999/{n}` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/a/b` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/mode/stop` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/play` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/{n}` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/bogus` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/bogus/{n}/{n}` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/clear` | 3 | 0.5 | 0.9 | 1.6 | 1.6 |
| `GET /api/cut` | 3 | 0.4 | 0.5 | 0.8 | 0.8 |
| `GET /api/definitely_not_a_command` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/device` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/device/%2520` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/device/%C2%B2` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/device/%C2%BD` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/device/%C3%A9` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/device/%D9%A3` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/device/-0` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/device/-1` | 2 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/device/-inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/device/../..` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/device/0x10` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/device/1.5` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/device/1e999` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/device/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/device/abc` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/device/default` | 2 | 63.0 | 63.7 | 64.3 | 64.3 |
| `GET /api/device/inf` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/device/nan` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/device/next` | 1 | 52.0 | 52.0 | 52.0 | 52.0 |
| `GET /api/device/null` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/device/true` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/device/{n}` | 3 | 0.3 | 28.2 | 83.1 | 83.1 |
| `GET /api/devices` | 25 | 0.3 | 1.6 | 3.3 | 22.0 |
| `GET /api/download` | 2 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/attack/%2520` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/attack/%C2%B2` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/attack/%C2%BD` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/attack/%C3%A9` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/attack/%D9%A3` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/duck/attack/-0` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/attack/-1` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/attack/-inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/attack/../..` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/attack/0x10` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/attack/1.5` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/duck/attack/1200.0` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/attack/1e999` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/attack/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/attack/dec` | 2 | 1.2 | 1.3 | 1.4 | 1.4 |
| `GET /api/duck/attack/dec/{n}` | 1 | 1.4 | 1.4 | 1.4 | 1.4 |
| `GET /api/duck/attack/down/{n}` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `GET /api/duck/attack/inc` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/duck/attack/inc/{n}` | 4 | 1.2 | 2.8 | 7.5 | 7.5 |
| `GET /api/duck/attack/inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/attack/nan` | 2 | 0.3 | 0.4 | 0.5 | 0.5 |
| `GET /api/duck/attack/null` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/attack/true` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/attack/up/{n}` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/duck/attack/{n}` | 4 | 0.5 | 0.8 | 1.1 | 1.1 |
| `GET /api/duck/bogus/{n}` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/duck/hold` | 2 | 1.0 | 1.5 | 2.0 | 2.0 |
| `GET /api/duck/hold/%2520` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/hold/%C2%B2` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/duck/hold/%C2%BD` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/hold/%C3%A9` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/hold/%D9%A3` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/hold/-0` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/duck/hold/-1` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/duck/hold/-inf` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/duck/hold/../..` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/hold/0x10` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/duck/hold/1.5` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/hold/1e999` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/duck/hold/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/hold/inf` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/duck/hold/nan` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/duck/hold/null` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/duck/hold/off` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/hold/on` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/duck/hold/true` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/duck/hold/{n}` | 3 | 0.8 | 0.9 | 0.9 | 0.9 |
| `GET /api/duck/level/%2520` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/level/%C2%B2` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/level/%C2%BD` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/level/%C3%A9` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/level/%D9%A3` | 1 | 1.3 | 1.3 | 1.3 | 1.3 |
| `GET /api/duck/level/-0` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/duck/level/-1` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/duck/level/-inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/level/../..` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/level/0x10` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/level/1.5` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/duck/level/1100.0` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/duck/level/1e999` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/level/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/level/dec` | 2 | 0.9 | 1.0 | 1.1 | 1.1 |
| `GET /api/duck/level/dec/{n}` | 1 | 1.5 | 1.5 | 1.5 | 1.5 |
| `GET /api/duck/level/down/{n}` | 1 | 4.6 | 4.6 | 4.6 | 4.6 |
| `GET /api/duck/level/inc` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/duck/level/inc/{n}` | 4 | 0.9 | 1.0 | 1.1 | 1.1 |
| `GET /api/duck/level/inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/level/nan` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/level/null` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/level/true` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/level/up/{n}` | 1 | 1.3 | 1.3 | 1.3 | 1.3 |
| `GET /api/duck/level/{n}` | 6 | 0.3 | 1.1 | 2.0 | 2.0 |
| `GET /api/duck/ratio/%2520` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/duck/ratio/%C2%B2` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/ratio/%C2%BD` | 1 | 0.2 | 0.2 | 0.2 | 0.2 |
| `GET /api/duck/ratio/%C3%A9` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/duck/ratio/%D9%A3` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/ratio/-0` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/ratio/-1` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/ratio/-inf` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/ratio/../..` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/ratio/0x10` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/ratio/1.5` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/ratio/1020.0` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/duck/ratio/1e999` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/ratio/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/duck/ratio/dec` | 2 | 1.1 | 1.2 | 1.2 | 1.2 |
| `GET /api/duck/ratio/dec/{n}` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/duck/ratio/down/{n}` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/duck/ratio/inc` | 1 | 1.3 | 1.3 | 1.3 | 1.3 |
| `GET /api/duck/ratio/inc/abc` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/ratio/inc/{n}` | 4 | 1.0 | 1.2 | 1.4 | 1.4 |
| `GET /api/duck/ratio/inf` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/ratio/nan` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/ratio/null` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/ratio/true` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/duck/ratio/up/{n}` | 1 | 1.5 | 1.5 | 1.5 | 1.5 |
| `GET /api/duck/ratio/{n}` | 5 | 0.4 | 0.9 | 1.3 | 1.3 |
| `GET /api/duck/release/%2520` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/duck/release/%C2%B2` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/duck/release/%C2%BD` | 1 | 7.0 | 7.0 | 7.0 | 7.0 |
| `GET /api/duck/release/%C3%A9` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/release/%D9%A3` | 1 | 6.6 | 6.6 | 6.6 | 6.6 |
| `GET /api/duck/release/-0` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/duck/release/-1` | 1 | 5.1 | 5.1 | 5.1 | 5.1 |
| `GET /api/duck/release/-5` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/duck/release/-inf` | 1 | 13.4 | 13.4 | 13.4 | 13.4 |
| `GET /api/duck/release/../..` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/release/0x10` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/release/1.5` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/release/1e999` | 1 | 6.7 | 6.7 | 6.7 | 6.7 |
| `GET /api/duck/release/4000.0` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/duck/release/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/release/dec` | 2 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/duck/release/dec/{n}` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/release/down/{n}` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/duck/release/inc` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/duck/release/inc/{n}` | 4 | 1.1 | 1.2 | 1.5 | 1.5 |
| `GET /api/duck/release/inf` | 1 | 38.6 | 38.6 | 38.6 | 38.6 |
| `GET /api/duck/release/nan` | 1 | 5.1 | 5.1 | 5.1 | 5.1 |
| `GET /api/duck/release/null` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/release/true` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/release/up/{n}` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/duck/release/{n}` | 4 | 1.1 | 2.5 | 6.1 | 6.1 |
| `GET /api/duck/threshold` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/threshold/%2520` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/duck/threshold/%C2%B2` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/duck/threshold/%C2%BD` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/duck/threshold/%C3%A9` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/threshold/%D9%A3` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/threshold/-0` | 1 | 1.4 | 1.4 | 1.4 | 1.4 |
| `GET /api/duck/threshold/-1` | 1 | 1.5 | 1.5 | 1.5 | 1.5 |
| `GET /api/duck/threshold/-40` | 2 | 1.2 | 1.4 | 1.6 | 1.6 |
| `GET /api/duck/threshold/-inf` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/duck/threshold/../..` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/threshold/0.0` | 1 | 1.3 | 1.3 | 1.3 | 1.3 |
| `GET /api/duck/threshold/0x10` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/duck/threshold/1.5` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `GET /api/duck/threshold/1000.0` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/threshold/1e999` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `GET /api/duck/threshold/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/duck/threshold/abc` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/duck/threshold/dec` | 2 | 1.1 | 1.2 | 1.3 | 1.3 |
| `GET /api/duck/threshold/dec/{n}` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/duck/threshold/down/{n}` | 1 | 1.4 | 1.4 | 1.4 | 1.4 |
| `GET /api/duck/threshold/inc` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/duck/threshold/inc/%2520` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/threshold/inc/%C2%B2` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/threshold/inc/%C2%BD` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/threshold/inc/%C3%A9` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/threshold/inc/%D9%A3` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/threshold/inc/-0` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/threshold/inc/-1` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/duck/threshold/inc/-inf` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/duck/threshold/inc/../..` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/threshold/inc/0x10` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/threshold/inc/1.5` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/threshold/inc/1e999` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/duck/threshold/inc/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/threshold/inc/inf` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/duck/threshold/inc/nan` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/duck/threshold/inc/null` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/threshold/inc/true` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/threshold/inc/{n}` | 5 | 0.8 | 1.3 | 2.2 | 2.2 |
| `GET /api/duck/threshold/inf` | 2 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/duck/threshold/nan` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `GET /api/duck/threshold/null` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/threshold/true` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/duck/threshold/up/{n}` | 1 | 1.3 | 1.3 | 1.3 | 1.3 |
| `GET /api/duck/threshold/{n}` | 2 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/fadeout` | 3 | 0.6 | 1.7 | 3.8 | 3.8 |
| `GET /api/fadeout/%2520` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/fadeout/%C2%B2` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/fadeout/%C2%BD` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/fadeout/%C3%A9` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/fadeout/%D9%A3` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/fadeout/-0` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/fadeout/-1` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/fadeout/-inf` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `GET /api/fadeout/../..` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/fadeout/0x10` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/fadeout/1.5` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/fadeout/1e999` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/fadeout/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/fadeout/inf` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `GET /api/fadeout/nan` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/fadeout/null` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/fadeout/true` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/fadeout/{n}` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/ffmpeg` | 3 | 32.7 | 36.6 | 44.0 | 44.0 |
| `GET /api/formats` | 3 | 0.5 | 0.5 | 0.6 | 0.6 |
| `GET /api/go_transition` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/go_transition/%2520` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/go_transition/%C2%B2` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/go_transition/%C2%BD` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/go_transition/%C3%A9` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/go_transition/%D9%A3` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/go_transition/-0` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/go_transition/-1` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/go_transition/-inf` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/go_transition/../..` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/go_transition/0x10` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/go_transition/1.5` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/go_transition/1e999` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/go_transition/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/go_transition/crossfade` | 2 | 1.1 | 1.1 | 1.2 | 1.2 |
| `GET /api/go_transition/cut` | 369 | 0.5 | 0.9 | 1.3 | 2.8 |
| `GET /api/go_transition/inf` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/go_transition/nan` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/go_transition/null` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/go_transition/toggle` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/go_transition/true` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/go_transition/wipe` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/go_transition/{n}` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/inf/inf` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/inf/mode/stop` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/inf/play` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/inf/{n}` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/library` | 18 | 0.5 | 0.9 | 1.1 | 5.4 |
| `GET /api/library/file` | 17 | 0.4 | 0.6 | 0.7 | 0.9 |
| `GET /api/library/info` | 3 | 0.4 | 2.1 | 5.2 | 5.2 |
| `GET /api/loop` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/loop/%2520` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/loop/%C2%B2` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/loop/%C2%BD` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/loop/%C3%A9` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/loop/%D9%A3` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/loop/-0` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/loop/-1` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/loop/-inf` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/loop/../..` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/loop/0x10` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/loop/1.5` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/loop/1e999` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/loop/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/loop/inf` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/loop/nan` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/loop/null` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/loop/on` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/loop/true` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/loop/{n}` | 2 | 0.4 | 1.0 | 1.6 | 1.6 |
| `GET /api/meters` | 33 | 0.4 | 2.3 | 1.9 | 43.8 |
| `GET /api/mode/%2520` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/mode/%C2%B2` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/mode/%C2%BD` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/mode/%C3%A9` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/mode/%D9%A3` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/mode/-0` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/mode/-1` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/mode/-inf` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/mode/../..` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/mode/0x10` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/mode/1.5` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/mode/1e999` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/mode/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/mode/bogus` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/mode/inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/mode/nan` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/mode/next` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/mode/null` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/mode/shuffle` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/mode/true` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/mode/{n}` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/monitor` | 61 | 0.4 | 1.8 | 4.0 | 8.6 |
| `GET /api/monitor/{n}` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/nan/mode/stop` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/nan/nan` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/nan/play` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/nan/{n}` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/next` | 5 | 0.5 | 0.6 | 0.7 | 0.7 |
| `GET /api/nextlist` | 3 | 0.4 | 0.5 | 0.5 | 0.5 |
| `GET /api/null/mode/stop` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/null/null` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/null/play` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/null/{n}` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/pause` | 13 | 0.5 | 0.8 | 0.9 | 1.5 |
| `GET /api/playlists` | 1442 | 0.2 | 0.5 | 0.8 | 13.5 |
| `GET /api/playlists/abc/triggers` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `GET /api/playlists/{n}/triggers` | 25 | 0.3 | 0.4 | 0.6 | 0.6 |
| `GET /api/playpause` | 2 | 1.2 | 1.5 | 1.8 | 1.8 |
| `GET /api/prev` | 2 | 0.4 | 0.5 | 0.6 | 0.6 |
| `GET /api/preview` | 2 | 0.5 | 0.7 | 0.9 | 0.9 |
| `GET /api/preview/%2520/%2520` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/preview/%C2%B2/%C2%B2` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/preview/%C2%BD/%C2%BD` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/preview/%C3%A9/%C3%A9` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/preview/%D9%A3/%D9%A3` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/preview/-0/-0` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/preview/-1/-1` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/preview/-inf/-inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/preview/../../../..` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/preview/0x10/0x10` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/preview/1.5/1.5` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/preview/1e999/1e999` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/preview/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/preview/bogus` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/preview/focus` | 4 | 0.4 | 1.0 | 1.9 | 1.9 |
| `GET /api/preview/inf/inf` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/preview/nan/nan` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/preview/null/null` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/preview/pause` | 2 | 0.4 | 0.6 | 0.8 | 0.8 |
| `GET /api/preview/playpause` | 3 | 0.4 | 0.9 | 1.7 | 1.7 |
| `GET /api/preview/resume` | 2 | 0.4 | 1.1 | 1.8 | 1.8 |
| `GET /api/preview/stop` | 3 | 0.3 | 0.8 | 1.4 | 1.4 |
| `GET /api/preview/true/true` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/preview/volume/%2520` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/preview/volume/%C2%B2` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/preview/volume/%C2%BD` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/preview/volume/%C3%A9` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/preview/volume/%D9%A3` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/preview/volume/-0` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/preview/volume/-1` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/preview/volume/-inf` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/preview/volume/../..` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `GET /api/preview/volume/0x10` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/preview/volume/1.5` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/preview/volume/1e999` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/preview/volume/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/preview/volume/abc` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/preview/volume/down/{n}` | 2 | 1.0 | 1.8 | 2.5 | 2.5 |
| `GET /api/preview/volume/inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/preview/volume/nan` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/preview/volume/null` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/preview/volume/true` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/preview/volume/up` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/preview/volume/up/{n}` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/preview/volume/{n}` | 5 | 0.3 | 0.7 | 1.2 | 1.2 |
| `GET /api/preview/{n}/x` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/preview/{n}/{n}` | 4 | 0.4 | 0.6 | 1.0 | 1.0 |
| `GET /api/previous` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/prevlist` | 2 | 0.4 | 0.5 | 0.5 | 0.5 |
| `GET /api/rescan` | 3 | 3.2 | 4.8 | 7.6 | 7.6 |
| `GET /api/resend` | 1 | 2.0 | 2.0 | 2.0 | 2.0 |
| `GET /api/resume` | 12 | 0.6 | 0.8 | 1.0 | 1.5 |
| `GET /api/scan` | 4 | 0.5 | 0.5 | 0.6 | 0.6 |
| `GET /api/seek` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/seek/%2520` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/seek/%C2%B2` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/seek/%C2%BD` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/seek/%C3%A9` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/seek/%D9%A3` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/seek/-0` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/seek/-1` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/seek/-5` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/seek/-inf` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/seek/../..` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/seek/0.5` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/seek/0x10` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/seek/1.5` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/seek/1e999` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/seek/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/seek/abc` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/seek/inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/seek/nan` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/seek/null` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/seek/true` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/seek/{n}` | 8 | 0.3 | 1.5 | 4.1 | 4.1 |
| `GET /api/settings` | 38 | 0.3 | 0.4 | 0.5 | 0.8 |
| `GET /api/settings/folders` | 4 | 0.4 | 0.4 | 0.5 | 0.5 |
| `GET /api/settings/top` | 57 | 0.3 | 0.6 | 1.0 | 2.7 |
| `GET /api/settings/transition` | 8 | 0.3 | 0.3 | 0.5 | 0.5 |
| `GET /api/settings/warning` | 24 | 0.3 | 0.4 | 0.5 | 0.5 |
| `GET /api/solo` | 3 | 0.3 | 0.6 | 0.8 | 0.8 |
| `GET /api/solo/%2520` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/solo/%C2%B2` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/solo/%C2%BD` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/solo/%C3%A9` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/solo/%D9%A3` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/solo/-0` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/solo/-1` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/solo/-inf` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/solo/../..` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/solo/0x10` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/solo/1.5` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/solo/1e999` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/solo/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/solo/inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/solo/nan` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/solo/null` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/solo/on` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/solo/true` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/solo/{n}` | 373 | 0.3 | 0.5 | 0.7 | 4.7 |
| `GET /api/state` | 1458 | 0.2 | 1.2 | 3.6 | 59.6 |
| `GET /api/stop` | 20 | 0.6 | 1.1 | 2.1 | 3.3 |
| `GET /api/stopall` | 376 | 0.3 | 0.8 | 1.5 | 24.7 |
| `GET /api/storage` | 2 | 0.4 | 0.5 | 0.6 | 0.6 |
| `GET /api/take` | 5 | 0.5 | 0.9 | 1.3 | 1.3 |
| `GET /api/toggle` | 3 | 0.4 | 0.5 | 0.5 | 0.5 |
| `GET /api/top` | 3 | 0.4 | 0.5 | 0.8 | 0.8 |
| `GET /api/triggers` | 2 | 0.4 | 0.5 | 0.6 | 0.6 |
| `GET /api/true/mode/stop` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/true/play` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/true/true` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/true/{n}` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/variables` | 8 | 0.5 | 0.7 | 1.0 | 1.0 |
| `GET /api/vol/{n}` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/volume` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/volume/%2520` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/volume/%C2%B2` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/volume/%C2%BD` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/volume/%C3%A9` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/volume/%D9%A3` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/volume/-0` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/volume/-1` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/volume/-5` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/volume/-inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/volume/../..` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/volume/0x10` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/volume/1.5` | 2 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/volume/1e999` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/volume/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/volume/abc` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/volume/down` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/volume/down/%2520` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/volume/down/%C2%B2` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/volume/down/%C2%BD` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/volume/down/%C3%A9` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/volume/down/%D9%A3` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/volume/down/-0` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/volume/down/-1` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/volume/down/-inf` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/volume/down/../..` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/volume/down/0x10` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/volume/down/1.5` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/volume/down/1e999` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/volume/down/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/volume/down/inf` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/volume/down/nan` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/volume/down/null` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/volume/down/true` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/volume/down/{n}` | 3 | 0.8 | 0.9 | 1.2 | 1.2 |
| `GET /api/volume/inf` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/volume/mute` | 5 | 1.0 | 1.7 | 3.4 | 3.4 |
| `GET /api/volume/nan` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/volume/null` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/volume/true` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/volume/up` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/volume/up/%2520` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/volume/up/%C2%B2` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/volume/up/%C2%BD` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/volume/up/%C3%A9` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/volume/up/%D9%A3` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/volume/up/-0` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `GET /api/volume/up/-1` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/volume/up/-inf` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `GET /api/volume/up/../..` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/volume/up/0x10` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `GET /api/volume/up/1.5` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/volume/up/1e999` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `GET /api/volume/up/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/volume/up/inf` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/volume/up/nan` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `GET /api/volume/up/null` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/volume/up/true` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/volume/up/x/y/z/w` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/volume/up/{n}` | 3 | 0.8 | 0.8 | 0.9 | 0.9 |
| `GET /api/volume/{n}` | 390 | 0.5 | 0.9 | 1.3 | 5.6 |
| `GET /api/waveform` | 4 | 0.3 | 0.5 | 0.9 | 0.9 |
| `GET /api/xfade` | 3 | 0.4 | 0.5 | 0.7 | 0.7 |
| `GET /api/{n}/%2520` | 2 | 0.3 | 0.4 | 0.5 | 0.5 |
| `GET /api/{n}/%C2%B2` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/{n}/%C2%BD` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/{n}/%C3%A9` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/%D9%A3` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/-0` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/-1` | 2 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/-inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/../..` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/0x10` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/1.5` | 2 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/1e999` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/bogus` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `GET /api/{n}/inf` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/mode` | 2 | 0.3 | 0.4 | 0.5 | 0.5 |
| `GET /api/{n}/mode/%2520` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/mode/%C2%B2` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/mode/%C2%BD` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/mode/%C3%A9` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/mode/%D9%A3` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/mode/-0` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/mode/-1` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/mode/-inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/mode/../..` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/mode/0x10` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/mode/1.5` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/mode/1e999` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/mode/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/mode/all` | 1 | 1.5 | 1.5 | 1.5 | 1.5 |
| `GET /api/{n}/mode/bogus` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/mode/chain` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/mode/continue` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/mode/inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/mode/loop` | 2 | 0.4 | 1.0 | 1.5 | 1.5 |
| `GET /api/{n}/mode/loop_playlist` | 4 | 0.9 | 1.3 | 2.0 | 2.0 |
| `GET /api/{n}/mode/loopall` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/mode/nan` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/mode/next` | 4 | 0.9 | 1.0 | 1.2 | 1.2 |
| `GET /api/{n}/mode/next_list` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/mode/next_playlist` | 2 | 1.1 | 1.1 | 1.2 | 1.2 |
| `GET /api/{n}/mode/nextplaylist` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/mode/null` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/mode/off` | 1 | 1.3 | 1.3 | 1.3 | 1.3 |
| `GET /api/{n}/mode/once` | 1 | 1.4 | 1.4 | 1.4 | 1.4 |
| `GET /api/{n}/mode/playlist` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/mode/random` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/mode/shuffle` | 7 | 1.0 | 1.3 | 1.5 | 1.5 |
| `GET /api/{n}/mode/stop` | 3 | 0.3 | 0.7 | 1.1 | 1.1 |
| `GET /api/{n}/mode/true` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/mode/{n}` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/nan` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/norm` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/norm/bogus` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/norm/lufs/%2520` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/norm/lufs/%C2%B2` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/norm/lufs/%C2%BD` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/norm/lufs/%C3%A9` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/norm/lufs/%D9%A3` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/{n}/norm/lufs/-0` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/norm/lufs/-1` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/{n}/norm/lufs/-18` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/norm/lufs/-99` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/norm/lufs/-inf` | 1 | 6.5 | 6.5 | 6.5 | 6.5 |
| `GET /api/{n}/norm/lufs/../..` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/{n}/norm/lufs/0x10` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/norm/lufs/1.5` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/{n}/norm/lufs/1e999` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/norm/lufs/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/norm/lufs/abc` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/norm/lufs/inf` | 1 | 1.5 | 1.5 | 1.5 | 1.5 |
| `GET /api/{n}/norm/lufs/nan` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/norm/lufs/null` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/norm/lufs/true` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/{n}/norm/lufs/{n}` | 2 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/norm/match` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/norm/off` | 2 | 0.5 | 0.9 | 1.4 | 1.4 |
| `GET /api/{n}/norm/ref` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/norm/ref/%2520` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/norm/ref/%C2%B2` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/norm/ref/%C2%BD` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/norm/ref/%C3%A9` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/norm/ref/%D9%A3` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/norm/ref/-0` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/norm/ref/-1` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/{n}/norm/ref/-inf` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/norm/ref/../..` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/norm/ref/0x10` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/norm/ref/1.5` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/{n}/norm/ref/1e999` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/norm/ref/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/norm/ref/inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/norm/ref/nan` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/norm/ref/null` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/norm/ref/true` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/norm/ref/{n}` | 3 | 0.5 | 0.8 | 1.3 | 1.3 |
| `GET /api/{n}/norm/track/%2520` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/norm/track/%C2%B2` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/norm/track/%C2%BD` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/norm/track/%C3%A9` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/norm/track/%D9%A3` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/norm/track/-0` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/{n}/norm/track/-1` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/norm/track/-inf` | 1 | 1.3 | 1.3 | 1.3 | 1.3 |
| `GET /api/{n}/norm/track/../..` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/norm/track/0x10` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/{n}/norm/track/1.5` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/norm/track/1e999` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/norm/track/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/norm/track/inf` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/norm/track/nan` | 1 | 1.4 | 1.4 | 1.4 | 1.4 |
| `GET /api/{n}/norm/track/null` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/norm/track/true` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/norm/track/{n}` | 2 | 0.4 | 0.8 | 1.2 | 1.2 |
| `GET /api/{n}/null` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/play` | 10 | 0.3 | 0.8 | 1.3 | 1.3 |
| `GET /api/{n}/true` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}` | 87 | 0.4 | 1.0 | 2.1 | 8.3 |
| `GET /api/{n}/{n}/%2520` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/%C2%B2` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/%C2%BD` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/{n}/%C3%A9` | 1 | 0.2 | 0.2 | 0.2 | 0.2 |
| `GET /api/{n}/{n}/%D9%A3` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/-0` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/{n}/{n}/-1` | 1 | 0.2 | 0.2 | 0.2 | 0.2 |
| `GET /api/{n}/{n}/-inf` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/../..` | 1 | 0.2 | 0.2 | 0.2 | 0.2 |
| `GET /api/{n}/{n}/0x10` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/1.5` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/1e999` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/bogus` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/{n}/{n}/crossfade` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/{n}/{n}/cue` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/{n}/{n}/cut` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/{n}/{n}/end` | 4 | 0.9 | 0.9 | 1.0 | 1.0 |
| `GET /api/{n}/{n}/end/%2520` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/end/%C2%B2` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/end/%C2%BD` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/end/%C3%A9` | 1 | 0.2 | 0.2 | 0.2 | 0.2 |
| `GET /api/{n}/{n}/end/%D9%A3` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/end/-0` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/end/-1` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/end/-inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/end/../..` | 1 | 0.2 | 0.2 | 0.2 | 0.2 |
| `GET /api/{n}/{n}/end/0x10` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/end/1.5` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/end/1e999` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/end/LOOP2` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/end/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.2 | 0.2 | 0.2 | 0.2 |
| `GET /api/{n}/{n}/end/bogus` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/end/cut` | 3 | 1.0 | 2.1 | 4.2 | 4.2 |
| `GET /api/{n}/{n}/end/default` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/{n}/end/fade` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/{n}/{n}/end/inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/end/loop` | 9 | 0.6 | 1.1 | 1.8 | 1.8 |
| `GET /api/{n}/{n}/end/nan` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/end/next` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/{n}/end/null` | 1 | 0.2 | 0.2 | 0.2 | 0.2 |
| `GET /api/{n}/{n}/end/once` | 2 | 0.9 | 1.1 | 1.2 | 1.2 |
| `GET /api/{n}/{n}/end/sideways` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/end/stop` | 4 | 0.9 | 1.0 | 1.0 | 1.0 |
| `GET /api/{n}/{n}/end/true` | 1 | 0.2 | 0.2 | 0.2 | 0.2 |
| `GET /api/{n}/{n}/end/{n}` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/focus` | 248 | 0.4 | 1.0 | 1.2 | 37.3 |
| `GET /api/{n}/{n}/in` | 2 | 0.4 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/{n}/in/%2520` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/in/%C2%B2` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/in/%C2%BD` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/in/%C3%A9` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/in/%D9%A3` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/{n}/in/-0` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/{n}/in/-1` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/{n}/in/-4` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/{n}/in/-inf` | 2 | 0.9 | 1.0 | 1.1 | 1.1 |
| `GET /api/{n}/{n}/in/../..` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/in/0.2` | 2 | 1.6 | 1.6 | 1.6 | 1.6 |
| `GET /api/{n}/{n}/in/0.5` | 11 | 1.0 | 1.2 | 1.5 | 1.5 |
| `GET /api/{n}/{n}/in/0x10` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/in/1.5` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/{n}/in/1e999` | 2 | 0.9 | 0.9 | 1.0 | 1.0 |
| `GET /api/{n}/{n}/in/2.9` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/{n}/in/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/in/abc` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/in/clear` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/{n}/in/inf` | 2 | 1.0 | 1.1 | 1.3 | 1.3 |
| `GET /api/{n}/{n}/in/nan` | 2 | 0.9 | 1.0 | 1.0 | 1.0 |
| `GET /api/{n}/{n}/in/null` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/in/true` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/in/{n}` | 6 | 0.6 | 1.1 | 1.6 | 1.6 |
| `GET /api/{n}/{n}/inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/loop` | 3 | 0.3 | 0.8 | 1.0 | 1.0 |
| `GET /api/{n}/{n}/loop/%2520` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/loop/%C2%B2` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/loop/%C2%BD` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/loop/%C3%A9` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/{n}/loop/%D9%A3` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/loop/-0` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/loop/-1` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/loop/-inf` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/loop/../..` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/{n}/loop/0x10` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/loop/1.5` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/loop/1e999` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/loop/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/loop/inf` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/{n}/loop/maybe/extra` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `GET /api/{n}/{n}/loop/nan` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/loop/null` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/{n}/loop/true` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/{n}/loop/{n}` | 4 | 0.3 | 0.7 | 1.2 | 1.2 |
| `GET /api/{n}/{n}/nan` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/null` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/out/%2520` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/out/%C2%B2` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |
| `GET /api/{n}/{n}/out/%C2%BD` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/{n}/out/%C3%A9` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/out/%D9%A3` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/{n}/out/-0` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/{n}/out/-1` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/{n}/out/-inf` | 1 | 1.3 | 1.3 | 1.3 | 1.3 |
| `GET /api/{n}/{n}/out/../..` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/out/0x10` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/{n}/out/1%2C5` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/out/1.4` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/out/1.5` | 2 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/{n}/out/1e999` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/{n}/out/2.4` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/{n}/{n}/out/2.5` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/{n}/out/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/out/inf` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/{n}/out/nan` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/{n}/out/null` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/out/off` | 1 | 1.4 | 1.4 | 1.4 | 1.4 |
| `GET /api/{n}/{n}/out/true` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/out/{n}` | 8 | 0.5 | 1.5 | 3.5 | 3.5 |
| `GET /api/{n}/{n}/toggle` | 3 | 0.5 | 0.6 | 0.7 | 0.7 |
| `GET /api/{n}/{n}/top` | 8 | 0.7 | 3.2 | 12.6 | 12.6 |
| `GET /api/{n}/{n}/trim` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/trim/clear` | 5 | 0.8 | 1.0 | 1.3 | 1.3 |
| `GET /api/{n}/{n}/trim/now` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/trim/reset` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/{n}/true` | 1 | 0.2 | 0.2 | 0.2 | 0.2 |
| `GET /api/{n}/{n}/xfade` | 4 | 0.7 | 1.6 | 3.4 | 3.4 |
| `GET /api/{n}/{n}/xfadetime/{n}` | 1 | 1.6 | 1.6 | 1.6 | 1.6 |
| `GET /api/{n}/{n}/xftime` | 2 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/{n}/xftime/%2520` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/xftime/%C2%B2` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/xftime/%C2%BD` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/xftime/%C3%A9` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/xftime/%D9%A3` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /api/{n}/{n}/xftime/-0` | 1 | 1.0 | 1.0 | 1.0 | 1.0 |
| `GET /api/{n}/{n}/xftime/-1` | 2 | 0.3 | 0.4 | 0.5 | 0.5 |
| `GET /api/{n}/{n}/xftime/-inf` | 2 | 0.7 | 0.9 | 1.0 | 1.0 |
| `GET /api/{n}/{n}/xftime/../..` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/xftime/0.25` | 1 | 1.3 | 1.3 | 1.3 | 1.3 |
| `GET /api/{n}/{n}/xftime/0.5` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/{n}/xftime/0x10` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/xftime/1.5` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `GET /api/{n}/{n}/xftime/1e999` | 2 | 0.6 | 0.7 | 0.8 | 0.8 |
| `GET /api/{n}/{n}/xftime/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/xftime/abc` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/{n}/xftime/clear` | 2 | 1.4 | 1.5 | 1.6 | 1.6 |
| `GET /api/{n}/{n}/xftime/inf` | 2 | 0.8 | 2.0 | 3.2 | 3.2 |
| `GET /api/{n}/{n}/xftime/master` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `GET /api/{n}/{n}/xftime/nan` | 2 | 0.4 | 0.5 | 0.5 | 0.5 |
| `GET /api/{n}/{n}/xftime/null` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /api/{n}/{n}/xftime/off` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/{n}/xftime/reset` | 1 | 1.2 | 1.2 | 1.2 | 1.2 |
| `GET /api/{n}/{n}/xftime/true` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /api/{n}/{n}/xftime/{n}` | 15 | 0.3 | 1.1 | 1.3 | 1.6 |
| `GET /api/{n}/{n}/{n}` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `GET /help` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /stage` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /stage/` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /stage/a` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /stage/b` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `GET /stage/c` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `GET /stage/zzz` | 1 | 0.9 | 0.9 | 0.9 | 0.9 |
| `GET /variables` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `OSC /` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC //0//1//` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC /0/1` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC /0/1/in/abc` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC /0/é/1` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC /1/2/xfade` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC /VOLUME/10` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC /a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC /fadeout` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC /mode/shuffle` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC /nonsense/zzz` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC /pause` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC /resume` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC /seek` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC /stop` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC /stop/` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/0` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/1` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/10` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/11` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/12` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/13` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/14` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/15` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/16` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/17` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/18` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/19` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/2` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/20` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/21` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/22` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/23` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/24` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/25` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/26` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/27` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/28` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/29` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/3` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/30` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/31` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/32` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/33` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/34` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/35` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/36` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/37` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/38` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/39` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/4` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/40` | 5 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/41` | 5 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/42` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/43` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/44` | 5 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/45` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/46` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/47` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/48` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/49` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/5` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/50` | 5 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/51` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/52` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/53` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/54` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/55` | 5 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/55.0` | 1 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/56` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/57` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/58` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/59` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/6` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/60` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/61` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/62` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/63` | 11 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/64` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/65` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/66` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/67` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/68` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/69` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/7` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/70` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/71` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/72` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/73` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/74` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/75` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/76` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/77` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/78` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/79` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/8` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/80` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/81` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/82` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/83` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/84` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/85` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/86` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/87` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/88` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/89` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/9` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/90` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/91` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/92` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/93` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/94` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/95` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/96` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/97` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/98` | 4 | 0 | 0.0 | 0 | 0 |
| `OSC /volume/99` | 4 | 0 | 0.0 | 0 | 0 |
| `PATCH /api/playlists` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `POST /` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `POST /api/device` | 5 | 0.3 | 48.9 | 63.8 | 63.8 |
| `POST /api/download` | 8 | 0.3 | 0.4 | 0.5 | 0.5 |
| `POST /api/download/clear` | 1 | 0.4 | 0.4 | 0.4 | 0.4 |
| `POST /api/library/folder` | 8 | 0.4 | 0.6 | 1.5 | 1.5 |
| `POST /api/library/folder/color` | 5 | 0.4 | 0.7 | 1.1 | 1.1 |
| `POST /api/library/rename` | 15 | 1.4 | 2.7 | 5.0 | 5.3 |
| `POST /api/library/upload` | 18 | 0.4 | 58.1 | 131.9 | 183.2 |
| `POST /api/mirror/device` | 3 | 0.4 | 0.5 | 0.6 | 0.6 |
| `POST /api/mirror/enable` | 2 | 0.6 | 0.7 | 0.8 | 0.8 |
| `POST /api/move` | 15 | 1.6 | 2.8 | 5.3 | 9.9 |
| `POST /api/playlists` | 458 | 1.6 | 2.4 | 3.3 | 12.3 |
| `POST /api/playlists/-1/rename` | 1 | 0.3 | 0.3 | 0.3 | 0.3 |
| `POST /api/playlists/1.5/rename` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `POST /api/playlists/abc/add` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `POST /api/playlists/abc/norm` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `POST /api/playlists/abc/rename` | 1 | 1.1 | 1.1 | 1.1 | 1.1 |
| `POST /api/playlists/abc/triggers` | 1 | 0.7 | 0.7 | 0.7 | 0.7 |
| `POST /api/playlists/abc/trim` | 1 | 0.8 | 0.8 | 0.8 | 0.8 |
| `POST /api/playlists/reorder` | 9 | 1.7 | 2.2 | 2.8 | 2.8 |
| `POST /api/playlists/{n}/add` | 464 | 0.8 | 2.6 | 3.4 | 54.8 |
| `POST /api/playlists/{n}/norm` | 19 | 0.3 | 1.2 | 2.0 | 5.3 |
| `POST /api/playlists/{n}/rename` | 7 | 0.3 | 1.5 | 3.9 | 3.9 |
| `POST /api/playlists/{n}/triggers` | 42 | 0.4 | 1.8 | 3.5 | 3.7 |
| `POST /api/playlists/{n}/trim` | 31 | 0.3 | 1.4 | 2.4 | 2.5 |
| `POST /api/preview/ctl` | 12 | 0.3 | 1.5 | 2.1 | 4.9 |
| `POST /api/preview/device` | 29 | 0.5 | 3.3 | 6.7 | 10.8 |
| `POST /api/preview/play` | 6 | 0.4 | 0.8 | 1.6 | 1.6 |
| `POST /api/restart` | 2 | 0.4 | 0.4 | 0.4 | 0.4 |
| `POST /api/settings` | 28 | 0.3 | 2.1 | 2.7 | 19.9 |
| `POST /api/settings/folders` | 3 | 0.5 | 0.8 | 1.1 | 1.1 |
| `POST /api/settings/top` | 395 | 0.4 | 1.1 | 1.5 | 24.8 |
| `POST /api/settings/transition` | 385 | 0.3 | 0.9 | 1.4 | 5.4 |
| `POST /api/settings/warning` | 384 | 0.3 | 0.8 | 1.2 | 6.0 |
| `POST /api/state` | 1 | 0.5 | 0.5 | 0.5 | 0.5 |
| `POST /api/triggers/arm` | 371 | 0.5 | 0.9 | 1.3 | 4.4 |
| `POST /api/triggers/skip` | 2 | 0.9 | 0.9 | 1.0 | 1.0 |
| `PUT /api/state` | 1 | 0.6 | 0.6 | 0.6 | 0.6 |

Slowest calls:

- 183.23 ms  POST /api/library/upload  (HTTP 200)  in `tests/api/test_library.py::test_upload_into_library_folder_and_playlist`
- 131.89 ms  POST /api/library/upload  (HTTP 200)  in `tests/api/test_library.py::test_deleting_the_live_file_does_not_cut_the_audio`
- 96.81 ms  POST /api/library/upload  (HTTP 200)  in `tests/api/test_library.py::test_rename_file_playlists_follow`
- 95.0 ms  POST /api/library/upload  (HTTP 200)  in `tests/api/test_library.py::test_missing_file_in_a_playlist_is_reported_and_play_fails_safely`
- 93.66 ms  POST /api/library/upload  (HTTP 200)  in `tests/api/test_library.py::test_rename_folder_moves_its_files_and_playlist_entries`
- 93.59 ms  POST /api/library/upload  (HTTP 200)  in `tests/api/test_library.py::test_delete_file_removes_it_from_every_playlist`
- 92.82 ms  POST /api/library/upload  (HTTP 200)  in `tests/api/test_library.py::test_folders_create_colour_icon_delete`
- 92.29 ms  POST /api/library/upload  (HTTP 200)  in `tests/api/test_library.py::test_rename_errors`
- 91.86 ms  POST /api/library/upload  (HTTP 200)  in `tests/api/test_library.py::test_rename_errors`
- 83.06 ms  GET /api/device/{n}  (HTTP 200)  in `tests/api/test_settings.py::test_output_device_selection`

## Controls exercised by passing tests: 111

