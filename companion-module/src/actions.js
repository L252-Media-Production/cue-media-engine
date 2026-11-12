import { END_CHOICES } from './consts.js'

const num = (id, label, def, min, max, extra = {}) => ({ type: 'number', id, label, default: def, min, max, ...extra })

export function trackChoices(self) {
	const out = []
	self.playlists.forEach((p, pi) => {
		p.tracks.forEach((t, ti) => out.push({ id: `${pi}/${ti}`, label: `${pi}: ${p.name} / ${ti + 1}: ${t.name}` }))
	})
	return out.length ? out : [{ id: '0/0', label: '0/0 (no tracks yet)' }]
}

export function playlistChoices(self) {
	const out = self.playlists.map((p, i) => ({ id: String(i), label: `${i}: ${p.name}` }))
	return out.length ? out : [{ id: '0', label: '0' }]
}

const trackField = (self) => ({
	type: 'dropdown',
	id: 'track',
	label: 'Track',
	default: trackChoices(self)[0].id,
	choices: trackChoices(self),
	allowCustom: true,
	tooltip: 'Pick a track, or type playlist/track numbers such as 0/2 (variables allowed)',
})

const fadeField = { type: 'number', id: 'ms', label: 'Fade time (ms), 0 = use player default', default: 0, min: 0, max: 60000 }
const ms = (o) => (Number(o.ms) > 0 ? Number(o.ms) : undefined)

const DUCK = [
	['threshold', 'Threshold (dB)', 0.5],
	['ratio', 'Ratio', 0.5],
	['attack', 'Attack (ms)', 5],
	['release', 'Release (ms)', 10],
	['level', 'Level', 1],
]

export function getActions(self) {
	const run = (path) => async () => {
		await self.cmd(path)
	}
	const simple = (name, path, extra = {}) => ({ name, options: [], callback: run(path), ...extra })
	const withFade = (name, path) => ({
		name,
		options: [fadeField],
		callback: async (a) => {
			await self.cmd(path, ms(a.options))
		},
	})

	const a = {}

	// Playing tracks
	a.play = {
		name: 'Play track',
		options: [
			trackField(self),
			{
				type: 'dropdown',
				id: 'method',
				label: 'How',
				default: 'play',
				choices: [
					{ id: 'play', label: 'Play (default fade)' },
					{ id: 'cut', label: 'Cut' },
					{ id: 'xfade', label: 'Crossfade' },
					{ id: 'top', label: 'Play on top (ducks the live track)' },
					{ id: 'toggle', label: 'Toggle (play, or stop if live)' },
					{ id: 'cue', label: 'Cue only' },
				],
			},
			fadeField,
		],
		callback: async (e) => {
			const t = String(e.options.track).trim()
			const m = e.options.method
			await self.cmd(`/${t}${m === 'play' ? '' : '/' + m}`, ms(e.options))
		},
	}
	a.play_playlist = {
		name: 'Play playlist (from its first track; Shuffle = random)',
		options: [
			{
				type: 'dropdown',
				id: 'playlist',
				label: 'Playlist',
				default: 'cued',
				choices: [{ id: 'cued', label: 'The cued playlist' }, ...playlistChoices(self)],
				allowCustom: true,
				tooltip: 'Starts it like Go on its first track (a random track when its behavior is Shuffle), then the playlist behavior applies',
			},
		],
		callback: async (e) => {
			let p = String(e.options.playlist).trim()
			if (p === 'cued') p = String(self.state?.focus_playlist_num)
			if (!/^\d+$/.test(p)) return
			await self.cmd(`/${p}/play`)
		},
	}
	a.track_end = {
		name: 'Track end action (next / loop once / loop forever / stop)',
		options: [
			trackField(self),
			{ type: 'dropdown', id: 'v', label: 'End action', default: 'cycle', choices: [{ id: 'cycle', label: 'Cycle to the next setting' }, ...END_CHOICES] },
		],
		callback: async (e) => {
			const t = String(e.options.track).trim()
			await self.cmd(`/${t}/end${e.options.v === 'cycle' ? '' : '/' + e.options.v}`)
		},
	}
	a.loop_track = {
		name: 'Track loop forever on/off',
		options: [
			trackField(self),
			{ type: 'dropdown', id: 'v', label: 'Loop', default: 'toggle', choices: [{ id: 'toggle', label: 'Toggle' }, { id: '1', label: 'On' }, { id: '0', label: 'Off' }] },
		],
		callback: async (e) => {
			const t = String(e.options.track).trim()
			await self.cmd(`/${t}/loop${e.options.v === 'toggle' ? '' : '/' + e.options.v}`)
		},
	}

	a.slot = {
		name: 'Cued playlist: track by position',
		options: [
			{ type: 'number', id: 'slot', label: 'Position (1 = first track of the cued playlist)', default: 1, min: 1, max: 999 },
			{
				type: 'dropdown',
				id: 'method',
				label: 'Send it to',
				default: 'cue',
				choices: [
					{ id: 'cue', label: 'Cue' },
					{ id: 'preview', label: 'Preview' },
					{ id: 'play', label: 'Play now' },
					{ id: 'top', label: 'Play on top' },
				],
			},
			fadeField,
		],
		callback: async (e) => {
			const pn = String(self.state?.focus_playlist_num)
			if (!/^\d+$/.test(pn)) return
			const t = `${pn}/${Number(e.options.slot) - 1}`
			const m = e.options.method
			if (m === 'cue') return self.cmd(`/${t}/cue`)
			if (m === 'preview') return self.cmd(`/preview/${t}`)
			await self.cmd(`/${t}${m === 'play' ? '' : '/top'}`, ms(e.options))
		},
	}

	// Cue
	a.go_transition = {
		name: 'Web page Go button: cut or crossfade',
		options: [{ type: 'dropdown', id: 'v', label: 'Go does', default: 'toggle', choices: [{ id: 'toggle', label: 'Switch between cut and crossfade' }, { id: 'cut', label: 'Cut (take)' }, { id: 'crossfade', label: 'Crossfade' }] }],
		callback: async (e) => self.cmd(`/go_transition/${e.options.v}`),
	}
	a.take = withFade('Cue: Take', '/take')
	a.xfade = withFade('Cue: Crossfade', '/xfade')
	a.cut = simple('Cue: Cut', '/cut')
	a.top = withFade('Cue: Play on top', '/top')
	a.toggle = withFade('Cue: Toggle', '/toggle')
	a.next = simple('Cue: Next track', '/next')
	a.prev = simple('Cue: Previous track', '/prev')
	a.nextlist = simple('Cue: Next playlist', '/nextlist')
	a.prevlist = simple('Cue: Previous playlist', '/prevlist')
	a.clear = simple('Cue: Clear', '/clear')
	a.cue_track = {
		name: 'Cue: Set cue to track',
		options: [trackField(self)],
		callback: async (e) => {
			const t = String(e.options.track).trim()
			await self.cmd(`/${t}/cue`)
		},
	}

	// Transport
	a.pause = simple('Live: Pause', '/pause')
	a.resume = simple('Live: Resume', '/resume')
	a.playpause = simple('Live: Play / Pause', '/playpause')
	a.fadeout = withFade('Live: Fade out', '/fadeout')
	a.stop = simple('Live: Stop', '/stop')
	a.stopall = simple('STOP ALL (live, preview and cue)', '/stopall')
	a.live_end = {
		name: 'Live: End action of the live track',
		options: [{ type: 'dropdown', id: 'v', label: 'End action', default: 'cycle', choices: [{ id: 'cycle', label: 'Cycle to the next setting' }, ...END_CHOICES] }],
		callback: async (e) => {
			const id = String(self.state?.live_id)
			if (!/^\d+\/\d+$/.test(id)) return
			await self.cmd(`/${id}/end${e.options.v === 'cycle' ? '' : '/' + e.options.v}`)
		},
	}
	a.loop = {
		name: 'Live: Loop forever on/off',
		options: [{ type: 'dropdown', id: 'v', label: 'Loop', default: 'toggle', choices: [{ id: 'toggle', label: 'Toggle' }, { id: '1', label: 'On' }, { id: '0', label: 'Off' }] }],
		callback: async (e) => self.cmd(e.options.v === 'toggle' ? '/loop' : `/loop/${e.options.v}`),
	}
	a.seek = {
		name: 'Live: Seek to (seconds)',
		options: [num('sec', 'Seconds', 0, 0, 86400, { range: false })],
		callback: async (e) => self.cmd(`/seek/${Number(e.options.sec)}`),
	}
	a.mode = {
		name: 'Playlist behavior (what follows a track)',
		options: [
			{
				type: 'dropdown',
				id: 'mode',
				label: 'Mode',
				default: 'next',
				choices: [{ id: 'next', label: 'Cycle to next mode' }, { id: 'stop', label: 'Stop' }, { id: 'loop_playlist', label: 'Loop Playlist' }, { id: 'next_playlist', label: 'Next Playlist' }, { id: 'shuffle', label: 'Shuffle' }],
				allowCustom: true,
			},
		],
		callback: async (e) => self.cmd(`/mode/${e.options.mode}`),
	}

	// Volume
	a.volume = {
		name: 'Live volume',
		options: [
			{
				type: 'dropdown',
				id: 'op', disableAutoExpression: true,
				label: 'Action',
				default: 'set',
				choices: [{ id: 'set', label: 'Set to' }, { id: 'up', label: 'Up by' }, { id: 'down', label: 'Down by' }, { id: 'mute', label: 'Mute / unmute' }],
			},
			num('n', 'Amount (%)', 5, 0, 100, { isVisibleExpression: '$(options:op) != "mute"' }),
		],
		callback: async (e) => {
			const { op, n } = e.options
			await self.cmd(op === 'mute' ? '/volume/mute' : op === 'set' ? `/volume/${n}` : `/volume/${op}/${n}`)
		},
	}

	// Preview
	a.preview = {
		name: 'Preview (headphones)',
		options: [
			{
				type: 'dropdown',
				id: 'op', disableAutoExpression: true,
				label: 'Action',
				default: 'playpause',
				choices: [
					{ id: 'focus', label: 'Preview the cued track' },
					{ id: 'playpause', label: 'Play / Pause' },
					{ id: 'pause', label: 'Pause' },
					{ id: 'resume', label: 'Resume' },
					{ id: 'stop', label: 'Stop' },
				],
			},
		],
		callback: async (e) => self.cmd(`/preview/${e.options.op}`),
	}
	a.preview_volume = {
		name: 'Preview volume (with Solo live, what you hear)',
		options: [
			{ type: 'dropdown', id: 'op', disableAutoExpression: true, label: 'Action', default: 'up', choices: [{ id: 'set', label: 'Set to' }, { id: 'up', label: 'Up by' }, { id: 'down', label: 'Down by' }] },
			num('n', 'Amount (%)', 5, 0, 100),
		],
		callback: async (e) => {
			const { op, n } = e.options
			await self.cmd(op === 'set' ? `/preview/volume/${n}` : `/preview/volume/${op}/${n}`)
		},
	}
	a.preview_track = {
		name: 'Preview: specific track',
		options: [trackField(self)],
		callback: async (e) => {
			const t = String(e.options.track).trim()
			await self.cmd(`/preview/${t}`)
		},
	}
	a.solo = {
		name: 'Preview: Solo',
		options: [{ type: 'dropdown', id: 'v', label: 'Solo', default: 'toggle', choices: [{ id: 'toggle', label: 'Toggle' }, { id: '1', label: 'On' }, { id: '0', label: 'Off' }] }],
		callback: async (e) => self.cmd(e.options.v === 'toggle' ? '/solo' : `/solo/${e.options.v}`),
	}

	// Ducking
	a.duck = {
		name: 'Ducking: adjust value',
		options: [
			{ type: 'dropdown', id: 'param', label: 'Parameter', default: 'threshold', choices: DUCK.map(([id, label]) => ({ id, label })) },
			{
				type: 'dropdown',
				id: 'op', disableAutoExpression: true,
				label: 'Action',
				default: 'inc',
				choices: [{ id: 'inc', label: 'Increase' }, { id: 'dec', label: 'Decrease' }, { id: 'set', label: 'Set to value' }],
			},
			num('value', 'Value (for Set)', 0, -200, 100000, { isVisibleExpression: '$(options:op) == "set"', range: false, step: 0.1 }),
			num('step', 'Step override (0 = default)', 0, 0, 1000, { isVisibleExpression: '$(options:op) != "set"', step: 0.1 }),
		],
		callback: async (e) => {
			const { param, op, value, step } = e.options
			if (op === 'set') return self.cmd(`/duck/${param}/${value}`)
			await self.cmd(`/duck/${param}/${op}${Number(step) > 0 ? '/' + step : ''}`)
		},
	}
	// Live input (Duck only): the player listens to one input channel and ducks the playlist audio while someone talks
	const onOff = [{ type: 'dropdown', id: 'v', label: 'Set', default: 'toggle', choices: [{ id: 'toggle', label: 'Toggle' }, { id: 'on', label: 'On' }, { id: 'off', label: 'Off' }] }]
	a.input_armed = {
		name: 'Input arm / disarm',
		options: [{ type: 'dropdown', id: 'v', label: 'Set', default: 'toggle', choices: [{ id: 'toggle', label: 'Toggle' }, { id: 'on', label: 'Arm' }, { id: 'off', label: 'Disarm' }] }],
		callback: async (e) => self.cmd(`/input/armed/${e.options.v}`),
	}
	a.input_duck_now = {
		name: 'Live input: Duck now (manual override: holds the playlist audio down with or without an input, until switched off)',
		options: onOff,
		callback: async (e) => self.cmd(`/input/ducknow/${e.options.v}`),
	}
	a.duck_hold = {
		name: 'Ducking: Hold mode',
		options: [{ type: 'dropdown', id: 'v', label: 'Hold', default: 'toggle', choices: [{ id: 'toggle', label: 'Toggle' }, { id: '1', label: 'On' }, { id: '0', label: 'Off' }] }],
		callback: async (e) => self.cmd(e.options.v === 'toggle' ? '/duck/hold' : `/duck/hold/${e.options.v}`),
	}

	// Trim
	a.trim = {
		name: 'Trim (A/B) on a track',
		options: [
			trackField(self),
			{
				type: 'dropdown',
				id: 'op', disableAutoExpression: true,
				label: 'Action',
				default: 'clear',
				choices: [
					{ id: 'clear', label: 'Clear trim' },
					{ id: 'in', label: 'Set A (start) in seconds' },
					{ id: 'out', label: 'Set B (end) in seconds' },
					{ id: 'fade', label: 'At B: fade out' },
					{ id: 'cut', label: 'At B: cut' },
				],
			},
			num('sec', 'Seconds', 0, 0, 86400, { isVisibleExpression: '$(options:op) == "in" || $(options:op) == "out"', range: false, step: 0.1 }),
		],
		callback: async (e) => {
			const t = String(e.options.track).trim()
			const { op, sec } = e.options
			if (op === 'clear') return self.cmd(`/${t}/trim/clear`)
			if (op === 'in' || op === 'out') return self.cmd(`/${t}/${op}/${sec}`)
			await self.cmd(`/${t}/end/${op}`)
		},
	}

	// Output / maintenance
	a.device = {
		name: 'Output device',
		options: [
			{ type: 'dropdown', id: 'op', disableAutoExpression: true, label: 'Action', default: 'next', choices: [{ id: 'next', label: 'Next device' }, { id: 'default', label: 'System default' }, { id: 'n', label: 'Device number' }] },
			num('n', 'Device number', 0, 0, 99, { isVisibleExpression: '$(options:op) == "n"' }),
		],
		callback: async (e) => self.cmd(e.options.op === 'n' ? `/device/${e.options.n}` : `/device/${e.options.op}`),
	}
	a.rescan = simple('Rescan library', '/rescan')
	a.resend = simple('Resend variables to Companion (OSC)', '/resend')
	a.raw = {
		name: 'Raw command',
		options: [{ type: 'textinput', id: 'path', label: 'Command path (e.g. /volume/up/5)', default: '/' }],
		callback: async (e) => self.cmd(String(e.options.path)),
	}

	return a
}

