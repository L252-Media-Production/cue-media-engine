import { combineRgb } from '@companion-module/base'
import { SLOTS, METER_AMBER_DB, METER_RED_DB, taperPct } from './consts.js'

const W = combineRgb(255, 255, 255)
const K = combineRgb(0, 0, 0)
const DK = combineRgb(30, 30, 30)
const RED = combineRgb(200, 20, 20)
const GREEN = combineRgb(0, 140, 60)
const AMBER = combineRgb(210, 130, 0)
const BLUE = combineRgb(30, 90, 200)
const UNARMED_GREEN = combineRgb(0, 153, 0)   // the Input armed toggle: unarmed is green, armed is red
const ARMED_RED = combineRgb(204, 0, 0)
const HEALTH_AMBER = combineRgb(255, 191, 0)
const HEALTH_RED = combineRgb(204, 0, 0)
const ARMED_TEXT_SIZE = '14'                  // the Input armed toggle's text size, in both looks (the string, like the other presets; tested on a real Companion button)

// gauge colour stops: amber from -17 dBFS and red from -6 dBFS, placed through the player's taper (about 65 and 86)
const AMBER_AT = Math.round(taperPct(METER_AMBER_DB) * 10) / 10
const RED_AT = Math.round(taperPct(METER_RED_DB) * 10) / 10

export function getPresets(self) {
	const P = {}
	const cats = new Map()
	const reg = (id, cat) => {
		if (!cats.has(cat)) cats.set(cat, [])
		cats.get(cat).push(id)
	}
	const px = self.prefix
	const v = (n) => `$(${self.label}:${px}${n})`

	const btn = (id, category, name, text, actions, feedbacks = [], style = {}, extraDown = []) => {
		reg(id, category)
		P[id] = {
			type: 'simple',
			name,
			style: { text, size: 'auto', color: W, bgcolor: DK, ...style },
			steps: [{ down: actions.map((a) => ({ actionId: a[0], options: a[1] || {} })).concat(extraDown), up: [] }],
			feedbacks,
		}
	}
	const act = (id, options) => [id, options]
	const fb = (feedbackId, options, style) => ({ feedbackId, options: options || {}, style })

	// Transport
	const T = 'Transport'
	btn('stopall', T, 'STOP ALL', 'STOP\\nALL', [act('stopall')], [], { bgcolor: RED, size: '18', color: W })
	btn('playpause', T, 'Play / Pause', 'PLAY\\n/PAUSE', [act('playpause')], [fb('live_state', { s: 'playing' }, { bgcolor: GREEN }), fb('live_state', { s: 'paused' }, { bgcolor: AMBER })])
	btn('stop', T, 'Stop', 'STOP', [act('stop')])
	btn('fadeout', T, 'Fade out', 'FADE\\nOUT', [act('fadeout', { ms: 0 })], [fb('live_state', { s: 'fading' }, { bgcolor: AMBER })])
	btn('loop', T, 'Loop live track forever', 'LOOP', [act('loop', { v: 'toggle' })], [fb('live_end', { v: 'loop' }, { bgcolor: AMBER })])
	btn('live_end', T, 'End action of the live track (press to cycle: next, once, loop, stop)', `END\\n${v('live_end')}\\n${v('live_pass')}`, [act('live_end', { v: 'cycle' })],
		[fb('live_end', { v: 'once' }, { bgcolor: AMBER }), fb('live_end', { v: 'loop' }, { bgcolor: AMBER }), fb('live_end', { v: 'stop' }, { bgcolor: RED })], { size: '14' })

	// Cue
	const C = 'Cue'
	btn('take', C, 'Take', 'TAKE', [act('take', { ms: 0 })], [], { bgcolor: GREEN })
	btn('xfade', C, 'Crossfade', 'XFADE', [act('xfade', { ms: 0 })])
	btn('cut', C, 'Cut', 'CUT', [act('cut')])
	btn('top', C, 'Play on top', 'PLAY\\nON TOP', [act('top', { ms: 0 })], [fb('on_top', {}, { bgcolor: RED })])
	btn('toggle', C, 'Toggle', 'TOGGLE', [act('toggle', { ms: 0 })])
	btn('next', C, 'Next track', 'NEXT\\n▶', [act('next')])
	btn('prev', C, 'Previous track', '◀\\nPREV', [act('prev')])
	btn('nextlist', C, 'Next playlist', 'NEXT\\nLIST', [act('nextlist')])
	btn('prevlist', C, 'Previous playlist', 'PREV\\nLIST', [act('prevlist')])
	btn('clear', C, 'Clear cue', 'CLEAR\\nCUE', [act('clear')])
	btn('go_mode', C, 'Go button mode (press to switch cut / crossfade)', `GO\\n${v('go_transition')}`, [act('go_transition', { v: 'toggle' })], [fb('go_transition', { v: 'crossfade' }, { bgcolor: AMBER })], { size: '14' })
	btn('play_cued_list', C, 'Play the cued playlist from its first track', `PLAY\\n${v('focus_playlist')}`, [act('play_playlist', { playlist: 'cued' })], [], { size: '14', bgcolor: GREEN })
	reg('cue_rotary', C)
	P.cue_rotary = {
		type: 'simple',
		name: 'Cue rotary: turn = next / previous track, push = take',
		style: { text: `CUE\\n${v('focus_name')}`, size: '14', color: W, bgcolor: DK },
		steps: [
			{
				down: [{ actionId: 'take', options: { ms: 0 } }],
				up: [],
				rotate_left: [{ actionId: 'prev', options: {} }],
				rotate_right: [{ actionId: 'next', options: {} }],
			},
		],
		feedbacks: [],
	}
	btn('cue_info', C, 'Cue / live info', `CUE\\n${v('focus_name')}\\nLIVE\\n${v('live_name')}`, [], [], { size: '14' })

	// Live info
	const L = 'Live info'
	btn('live_name', L, 'Live track name', `${v('live_name')}\\n${v('remaining')}`, [], [fb('live_state', { s: 'playing' }, { bgcolor: GREEN }), fb('ending', { s: 10 }, { bgcolor: RED })], { size: '14' })
	btn('remaining', L, 'Time remaining', v('remaining'), [], [fb('ending', { s: 10 }, { bgcolor: RED })], { size: '24' })
	btn('state', L, 'State', `${v('state')}\\n${v('status')}`, [], [fb('health', {}, { bgcolor: RED })], { size: '14' })
	btn('meter', L, 'Meter (text bars, console taper)', `L ${v('live_meter_l')}\\nR ${v('live_meter_r')}`, [], [], { size: '14' })
	btn('meter_db', L, 'Meter in dBFS', `L ${v('live_db_l')}\\nR ${v('live_db_r')}\\ndBFS`, [], [], { size: '14' })
	btn('output', L, 'Output device', v('output'), [], [], { size: '14' })

	// Volume
	const V = 'Volume'
	const vup = [act('volume', { op: 'up', n: 5 })]
	btn('vol_info', V, 'Volume (rotary push = mute)', `VOL\\n${v('live_volume')}%`, [act('volume', { op: 'mute', n: 0 })], [fb('muted', {}, { bgcolor: RED })], { size: '18' })
	btn('vol_up', V, 'Volume up', 'VOL\\n▲', vup)
	btn('vol_down', V, 'Volume down', 'VOL\\n▼', [act('volume', { op: 'down', n: 5 })])
	reg('vol_rotary', V)
	P.vol_rotary = {
		type: 'simple',
		name: 'Volume rotary (Stream Deck+)',
		style: { text: `VOL\\n${v('live_volume')}%`, size: '18', color: W, bgcolor: DK },
		steps: [
			{
				down: [act('volume', { op: 'mute', n: 0 })].map((a) => ({ actionId: a[0], options: a[1] })),
				up: [],
				rotate_left: [{ actionId: 'volume', options: { op: 'down', n: 2 } }],
				rotate_right: [{ actionId: 'volume', options: { op: 'up', n: 2 } }],
			},
		],
		feedbacks: [fb('muted', {}, { bgcolor: RED })],
	}

	// Preview
	const R = 'Preview'
	btn('pv_focus', R, 'Preview cued track', 'PREVIEW\\nCUE', [act('preview', { op: 'focus' })], [fb('preview_state', { s: 'playing' }, { bgcolor: GREEN })])
	btn('pv_focus_name', R, 'Preview the cued track (shows its name)', `PREVIEW\\n${v('focus_name')}`, [act('preview', { op: 'focus' })], [fb('preview_state', { s: 'playing' }, { bgcolor: GREEN })], { size: '14' })
	btn('pv_pp', R, 'Preview play / pause', 'PV\\n▶/❚❚', [act('preview', { op: 'playpause' })], [fb('preview_state', { s: 'playing' }, { bgcolor: GREEN }), fb('preview_state', { s: 'paused' }, { bgcolor: AMBER })])
	btn('pv_stop', R, 'Preview stop', 'PV\\nSTOP', [act('preview', { op: 'stop' })])
	btn('pv_solo', R, 'Preview solo (listen to the live output)', 'SOLO\\nLIVE', [act('solo', { v: 'toggle' })], [fb('solo', {}, { bgcolor: AMBER })])
	btn('pv_vol_info', R, 'Preview volume (with Solo live, what you hear)', `PV VOL\\n${v('preview_volume')}%`, [], [fb('solo', {}, { bgcolor: AMBER })], { size: '14' })
	btn('pv_vol_up', R, 'Preview volume up', 'PV VOL\\n▲', [act('preview_volume', { op: 'up', n: 5 })])
	btn('pv_vol_down', R, 'Preview volume down', 'PV VOL\\n▼', [act('preview_volume', { op: 'down', n: 5 })])
	reg('pv_vol_rotary', R)
	P.pv_vol_rotary = {
		type: 'simple',
		name: 'Preview volume rotary (Stream Deck+)',
		style: { text: `PV VOL\\n${v('preview_volume')}%`, size: '14', color: W, bgcolor: DK },
		steps: [{ down: [], up: [], rotate_left: [{ actionId: 'preview_volume', options: { op: 'down', n: 2 } }], rotate_right: [{ actionId: 'preview_volume', options: { op: 'up', n: 2 } }] }],
		feedbacks: [fb('solo', {}, { bgcolor: AMBER })],
	}
	btn('pv_name', R, 'Preview info', `PV\\n${v('preview_name')}\\n${v('preview_remaining')}`, [], [], { size: '14' })

	// Ducking
	const D = 'Ducking'
	const rot = (id, name, param, label, fmtVar, step) => {
		reg(id, D)
		P[id] = {
			type: 'simple',
			name,
			style: { text: `${label}\\n${v(fmtVar)}`, size: '18', color: W, bgcolor: DK },
				steps: [
				{
					down: [],
					up: [],
					rotate_left: [{ actionId: 'duck', options: { param, op: 'dec', value: 0, step } }],
					rotate_right: [{ actionId: 'duck', options: { param, op: 'inc', value: 0, step } }],
				},
			],
			feedbacks: [],
		}
	}
	rot('duck_thr_rot', 'Threshold rotary', 'threshold', 'THRESH', 'duck_threshold', 0)
	rot('duck_ratio_rot', 'Ratio rotary', 'ratio', 'RATIO', 'duck_ratio', 0)
	rot('duck_att_rot', 'Attack rotary', 'attack', 'ATTACK', 'duck_attack', 0)
	rot('duck_rel_rot', 'Release rotary', 'release', 'RELEASE', 'duck_release', 0)
	rot('duck_level_rot', 'Input Gain rotary', 'level', 'INPUT\\nGAIN', 'top_level', 0)
	for (const [p, label, vn] of [['threshold', 'THRESH', 'duck_threshold'], ['ratio', 'RATIO', 'duck_ratio'], ['attack', 'ATTACK', 'duck_attack'], ['release', 'RELEASE', 'duck_release'], ['level', 'INPUT', 'top_level']]) {
		btn(`duck_${p}_up`, D, `${label} up`, `${label}\\n${v(vn)}\\n▲`, [act('duck', { param: p, op: 'inc', value: 0, step: 0 })], [], { size: '14' })
		btn(`duck_${p}_dn`, D, `${label} down`, `${label}\\n${v(vn)}\\n▼`, [act('duck', { param: p, op: 'dec', value: 0, step: 0 })], [], { size: '14' })
	}
	const LIN = 'Live input'
	// text size 14 in BOTH looks (the preset's own style = unarmed, and the feedback style = armed), so neither wraps: one constant, set in both places
	btn('liveinput_armed', LIN, 'Input armed toggle', 'INPUT\\nUNARMED', [act('input_armed', { v: 'toggle' })],
		[fb('input_armed', {}, { bgcolor: ARMED_RED, color: W, text: 'INPUT\\nARMED', size: ARMED_TEXT_SIZE })], { size: ARMED_TEXT_SIZE, bgcolor: UNARMED_GREEN, color: W })
	btn('liveinput_duck_now', LIN, 'Live input: Duck now (manual override, press again to release)', 'DUCK\\nNOW', [act('input_duck_now', { v: 'toggle' })], [fb('input_duck_now', {}, { bgcolor: RED })], { size: '14' })
	btn('liveinput_status', LIN, 'Live input: signal and ducking', `INPUT\\n${v('input_signal')}/${v('input_ducking')}`, [], [fb('input_signal', {}, { bgcolor: GREEN }), fb('input_ducking', {}, { bgcolor: AMBER })], { size: '14' })
	btn('duck_hold', D, 'Hold mode', `HOLD\\n${v('duck_hold')}`, [act('duck_hold', { v: 'toggle' })], [fb('duck_hold', {}, { bgcolor: BLUE })])
	btn('duck_gr', D, 'Gain reduction', `GR\\n${v('duck_gr')} dB`, [], [fb('ducking', { db: 1 }, { bgcolor: AMBER })], { size: '14' })
	btn('input_gain', D, 'Input gain', `INPUT\\n${v('top_level')}`, [], [], { size: '14' })

	const H = 'Health'
	btn('health', H, 'Player health (amber when degraded, red on a problem)', `HEALTH\\n${v('health_text')}`, [],
		[fb('health_state', { which: 'degraded' }, { bgcolor: HEALTH_AMBER, color: K }), fb('health_state', { which: 'problem' }, { bgcolor: HEALTH_RED, color: W })], { size: '14' })

	// Modes
	const M = 'Playlist behavior'
	btn('mode_next', M, 'Cycle mode', `MODE\\n${v('play_mode')}`, [act('mode', { mode: 'next' })], [], { size: '14' })
	for (const [id, label] of [['stop', 'STOP'], ['loop_playlist', 'LOOP\\nLIST'], ['next_playlist', 'NEXT\\nLIST'], ['shuffle', 'SHUFFLE']]) {
		btn(`mode_${id}`, M, `Mode: ${id}`, label, [act('mode', { mode: id })], [fb('play_mode', { m: id }, { bgcolor: BLUE })])
	}


	// Monitor buttons: time, name and L/R meters (layered presets, Companion 5)
	const ex = (value) => ({ isExpression: true, value })
	const meter = (id, x, variable) => ({
		type: 'gauge',
		id,
		x,
		y: 6,
		width: 8,
		height: 88,
		orientation: 'vertical',
		min: 0,
		max: 100,
		value: ex(`$(${self.label}:${px}${variable})`),
		fillEnabled: true,
		multiColour: true,
		trackStyle: 'dimmed',
		stops: [
			{ value: 0, color: combineRgb(0, 200, 70), gradient: false },
			{ value: AMBER_AT, color: combineRgb(240, 200, 0), gradient: false },
			{ value: RED_AT, color: combineRgb(230, 30, 30), gradient: false },
		],
	})
	const monitor = (id, category, name, title, key, nameVar, timeVar, press, activeFb, activeColor) => {
		reg(id, category)
		P[id] = {
			type: 'layered',
			name,
			elements: [
				{ type: 'box', id: 'bg', x: 0, y: 0, width: 100, height: 100, color: combineRgb(0, 0, 0) },
				{ type: 'text', id: 'time', x: 0, y: 2, width: 78, height: 20, fontsize: 85, halign: 'center', valign: 'center', color: W, text: ex(`$(${self.label}:${px}${timeVar})`) },
				{ type: 'text', id: 'title', x: 2, y: 24, width: 76, height: 14, fontsize: 80, halign: 'center', valign: 'center', color: W, text: `${title}:` },
				{ type: 'text', id: 'name', x: 2, y: 38, width: 76, height: 58, fontsize: 40, fontsizeAllowShrink: true, halign: 'center', valign: 'top', color: W, text: ex(`$(${self.label}:${px}${nameVar})`) },
				meter('meter_l', 80, `${key}_fader_l`),
				meter('meter_r', 90, `${key}_fader_r`),
			],
			steps: [{ down: press.map((a) => ({ actionId: a[0], options: a[1] || {} })), up: [] }],
			feedbacks: [{ feedbackId: activeFb[0], options: activeFb[1], styleOverrides: [{ elementId: 'bg', elementProperty: 'color', override: { isExpression: false, value: activeColor } }] }],
		}
	}
	monitor('monitor_live', L, 'Live monitor: time, name and meters', 'Live', 'live', 'live_name', 'remaining', [act('playpause')], ['live_state', { s: 'playing' }], RED)
	monitor('monitor_preview', R, 'Preview monitor: time, name and meters', 'Preview', 'preview', 'preview_name', 'preview_remaining', [act('preview', { op: 'playpause' })], ['preview_state', { s: 'playing' }], combineRgb(0, 110, 50))


	// Cued playlist page: button N is always track N of whichever playlist holds the cue
	const SL = 'Cued playlist: Cue track 1-' + SLOTS
	const SP = 'Cued playlist: Preview track 1-' + SLOTS
	btn('slot_title', SL, 'Cued playlist name', `${v('focus_playlist')}\\n${v('slot_count')} tracks`, [act('nextlist')], [], { size: '14', bgcolor: combineRgb(60, 0, 0) })
	for (let n = 1; n <= SLOTS; n++) {
		const grey = { bgcolor: combineRgb(8, 8, 8), color: combineRgb(60, 60, 60) }
		btn(`slot_cue_${n}`, SL, `Cue track ${n} of the cued playlist`, `${n}\\n${v(`slot${n}_name`)}`, [act('slot', { slot: n, method: 'cue', ms: 0 })],
			[fb('slot_state', { slot: n, what: 'empty' }, grey), fb('slot_state', { slot: n, what: 'missing' }, { bgcolor: combineRgb(60, 60, 60), color: RED }), fb('slot_state', { slot: n, what: 'cued' }, { bgcolor: AMBER }), fb('slot_state', { slot: n, what: 'live' }, { bgcolor: RED })], { size: '14' })
		btn(`slot_pv_${n}`, SP, `Preview track ${n} of the cued playlist`, `${n}\\n${v(`slot${n}_name`)}\\nPREVIEW`, [act('slot', { slot: n, method: 'preview', ms: 0 })],
			[fb('slot_state', { slot: n, what: 'empty' }, grey), fb('slot_state', { slot: n, what: 'missing' }, { bgcolor: combineRgb(60, 60, 60), color: RED }), fb('slot_state', { slot: n, what: 'previewing' }, { bgcolor: GREEN })], { size: '14' })
	}

	// Playlist tracks (generated from the player)
	self.playlists.forEach((pl, pi) => {
		const cat = `${pi}: ${pl.name}`
		btn(`play_${pi}`, cat, `PLAY ${pl.name}`, `PLAY\\n${pl.name}`, [act('play_playlist', { playlist: String(pi) })], [], { size: '14', bgcolor: GREEN })
		pl.tracks.forEach((tr, ti) => {
			const id = `${pi}/${ti}`
			btn(
				`cue_${pi}_${ti}`,
				cat,
				`CUE ${pl.name} / ${tr.name}`,
				`${ti + 1}\\n${tr.name}\\nCUE`,
				[act('cue_track', { track: id })],
				[
					fb('track_live', { track: id }, { bgcolor: RED }),
					fb('track_cued', { track: id }, { bgcolor: AMBER }),
					fb('track_missing', { track: id }, { bgcolor: combineRgb(60, 60, 60), color: RED }),
				],
				{ size: '14' },
			)
			btn(
				`end_${pi}_${ti}`,
				cat,
				`END ACTION ${pl.name} / ${tr.name} (press to cycle)`,
				`${ti + 1}\\n${tr.name}\\nEND`,
				[act('track_end', { track: id, v: 'cycle' })],
				[fb('track_end', { track: id, v: 'once' }, { bgcolor: AMBER }), fb('track_end', { track: id, v: 'loop' }, { bgcolor: AMBER }), fb('track_end', { track: id, v: 'stop' }, { bgcolor: RED })],
				{ size: '14' },
			)
			btn(
				`pv_${pi}_${ti}`,
				cat,
				`PREVIEW ${pl.name} / ${tr.name}`,
				`${ti + 1}\\n${tr.name}\\nPREVIEW`,
				[act('preview_track', { track: id })],
				[fb('track_previewing', { track: id }, { bgcolor: GREEN }), fb('track_missing', { track: id }, { bgcolor: combineRgb(60, 60, 60), color: RED })],
				{ size: '14' },
			)
		})
	})
	const structure = [...cats.entries()].map(([name, ids], i) => ({ id: `sec${i}`, name, definitions: ids }))
	return { structure, presets: P }
}
