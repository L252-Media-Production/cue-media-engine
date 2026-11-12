import { combineRgb } from '@companion-module/base'
import { trackChoices } from './actions.js'
import { SLOTS, END_CHOICES } from './consts.js'

const GREEN = combineRgb(0, 140, 60)
const RED = combineRgb(200, 20, 20)
const AMBER = combineRgb(210, 130, 0)
const BLUE = combineRgb(30, 90, 200)
const ARMED_RED = combineRgb(204, 0, 0)       // the armed look of the Input armed button
const WHITE = combineRgb(255, 255, 255)
const HEALTH_AMBER = combineRgb(255, 191, 0)  // degraded: amber with dark text (about 12:1)
const HEALTH_RED = combineRgb(204, 0, 0)      // problem: red with white text (about 6:1)
const BLACK = combineRgb(0, 0, 0)

const st = (self, k) => self.state?.[k]

export function getFeedbacks(self) {
	const bool = (name, defaultStyle, options, callback) => ({ type: 'boolean', name, defaultStyle, options, callback })
	const trackOpt = {
		type: 'dropdown',
		id: 'track',
		label: 'Track',
		default: trackChoices(self)[0].id,
		choices: trackChoices(self),
		allowCustom: true,
	}
	const trackOf = (fb) => String(fb.options.track).trim()
	const find = (id) => {
		const [p, t] = id.split('/').map(Number)
		return self.playlists[p]?.tracks[t]
	}
	const flag = (k, v = '1') => ({ options: [], callback: () => String(st(self, k)) === v })

	return {
		live_state: bool(
			'Live: transport state',
			{ bgcolor: GREEN, color: WHITE },
			[{ type: 'dropdown', id: 's', label: 'State', default: 'playing', choices: [{ id: 'playing', label: 'Playing' }, { id: 'paused', label: 'Paused' }, { id: 'fading', label: 'Fading out' }, { id: 'stopped', label: 'Stopped' }] }],
			(fb) => st(self, 'state') === fb.options.s,
		),
		slot_state: bool(
			'Cued-playlist track slot state',
			{ bgcolor: AMBER, color: WHITE },
			[
				{ type: 'number', id: 'slot', label: 'Slot (1 = first track of the cued playlist)', default: 1, min: 1, max: SLOTS },
				{ type: 'dropdown', id: 'what', label: 'When the track is', default: 'cued', choices: [{ id: 'cued', label: 'Cued' }, { id: 'live', label: 'Live' }, { id: 'previewing', label: 'In preview' }, { id: 'loop', label: 'Looping forever' }, { id: 'once', label: 'Loop once' }, { id: 'stop', label: 'Stops at this track' }, { id: 'trim', label: 'Trimmed (A/B)' }, { id: 'missing', label: 'Missing file' }, { id: 'empty', label: 'Empty slot (no track)' }] },
			],
			(fb) => {
				const k = Number(fb.options.slot) - 1
				const pn = String(self.state?.focus_playlist_num)
				const tr = self.playlists[Number(pn)]?.tracks[k]
				switch (fb.options.what) {
					case 'cued': return !!tr && self.state?.focus_id === `${pn}/${k}`
					case 'live': return !!tr && self.state?.live_id === `${pn}/${k}`
					case 'previewing': {
						const pv = self.state?.preview
						return !!tr && !!pv && pv.fid === tr.id && ['playing', 'paused', 'loading'].includes(pv.state)
					}
					case 'loop': return !!tr?.loop
					case 'once': return tr?.end === 'once'
					case 'stop': return tr?.end === 'stop'
					case 'trim': return !!tr?.trim
					case 'missing': return !!tr?.missing
					case 'empty': return !tr
				}
				return false
			},
		),
		track_live: bool('Track is live', { bgcolor: RED, color: WHITE }, [trackOpt], (fb) => st(self, 'live_id') === trackOf(fb)),
		track_cued: bool('Track is cued', { bgcolor: AMBER, color: WHITE }, [trackOpt], (fb) => st(self, 'focus_id') === trackOf(fb)),
		track_end: bool(
			'Track end action is',
			{ bgcolor: AMBER, color: WHITE },
			[trackOpt, { type: 'dropdown', id: 'v', label: 'End action', default: 'once', choices: END_CHOICES }],
			(fb) => (find(trackOf(fb))?.end || 'default') === fb.options.v,
		),
		live_end: bool(
			'Live track end action is',
			{ bgcolor: AMBER, color: WHITE },
			[{ type: 'dropdown', id: 'v', label: 'End action', default: 'once', choices: END_CHOICES }],
			(fb) => (st(self, 'live_end') || 'default') === fb.options.v,
		),
		track_loop: bool('Track loop forever is on', { bgcolor: BLUE, color: WHITE }, [trackOpt], (fb) => !!find(trackOf(fb))?.loop),
		track_trim: bool('Track has A/B trim', { bgcolor: combineRgb(90, 40, 140), color: WHITE }, [trackOpt], (fb) => !!find(trackOf(fb))?.trim),
		track_missing: bool('Track file is missing', { bgcolor: combineRgb(60, 60, 60), color: combineRgb(255, 80, 80) }, [trackOpt], (fb) => !!find(trackOf(fb))?.missing),
		track_previewing: bool('Track is loaded in preview', { bgcolor: GREEN, color: WHITE }, [trackOpt], (fb) => {
			const t = find(trackOf(fb))
			const pv = self.state?.preview
			return !!t && !!pv && pv.fid === t.id && (pv.state === 'playing' || pv.state === 'paused' || pv.state === 'loading')
		}),
		on_top: bool('Playing on top (ducking active)', { bgcolor: RED, color: WHITE }, [], () => st(self, 'on_top') === '1'),
		ducking: bool('Gain reduction above (dB)', { bgcolor: AMBER, color: WHITE }, [{ type: 'number', id: 'db', label: 'dB', default: 1, min: 0, max: 60 }], (fb) => Number(st(self, 'duck_gr')) >= Number(fb.options.db)),
		input_armed: bool('Input armed', { bgcolor: ARMED_RED, color: WHITE }, [], () => st(self, 'input_armed') === '1'),      // no state yet (the player not reached) = unarmed look, never an error
		input_duck_now: bool('Live input: Duck now is on', { bgcolor: RED, color: WHITE }, [], () => st(self, 'input_duck_now') === '1'),
		input_signal: bool('Live input has signal', { bgcolor: GREEN, color: WHITE }, [], () => st(self, 'input_signal') === '1'),
		input_ducking: bool('Live input is ducking the playlist audio', { bgcolor: AMBER, color: WHITE }, [], () => st(self, 'input_ducking') === '1'),
		health_state: bool(
			'Player health',
			{ bgcolor: HEALTH_AMBER, color: BLACK },
			[{ type: 'dropdown', id: 'which', label: 'Reacts to', default: 'either', choices: [{ id: 'degraded', label: 'Degraded' }, { id: 'problem', label: 'Problem' }, { id: 'either', label: 'Degraded or problem' }] }],
			(fb) => {
				const h = self.healthState ? self.healthState() : ''      // a player without a health state: the feedback never fires
				return fb.options.which === 'either' ? h === 'degraded' || h === 'problem' : h === fb.options.which
			},
		),
		duck_hold: bool('Ducking hold mode is on', { bgcolor: BLUE, color: WHITE }, [], () => st(self, 'duck_hold') === '1'),
		solo: bool('Preview solo is on', { bgcolor: AMBER, color: WHITE }, [], () => st(self, 'preview_solo') === '1'),
		preview_state: bool(
			'Preview state',
			{ bgcolor: GREEN, color: WHITE },
			[{ type: 'dropdown', id: 's', label: 'State', default: 'playing', choices: [{ id: 'playing', label: 'Playing' }, { id: 'paused', label: 'Paused' }, { id: 'off', label: 'Off' }] }],
			(fb) => {
				if (fb.options.s === 'playing') return st(self, 'preview_playing') === '1'
				return st(self, 'preview_state') === fb.options.s
			},
		),
		muted: bool('Live volume is 0 (muted)', { bgcolor: RED, color: WHITE }, [], () => Number(st(self, 'live_volume')) === 0),
		go_transition: bool(
			'Web page Go button mode is',
			{ bgcolor: AMBER, color: WHITE },
			[{ type: 'dropdown', id: 'v', label: 'Go does', default: 'crossfade', choices: [{ id: 'cut', label: 'Cut (take)' }, { id: 'crossfade', label: 'Crossfade' }] }],
			(fb) => (st(self, 'go_transition') || 'cut') === fb.options.v,
		),
		play_mode: bool(
			'Playlist behavior (of cued playlist)',
			{ bgcolor: BLUE, color: WHITE },
			[{ type: 'dropdown', id: 'm', label: 'Mode', default: 'loop_playlist', choices: [{ id: 'stop', label: 'Stop' }, { id: 'loop_playlist', label: 'Loop Playlist' }, { id: 'next_playlist', label: 'Next Playlist' }, { id: 'shuffle', label: 'Shuffle' }] }],
			(fb) => st(self, 'play_mode') === fb.options.m,
		),
		ending: bool('Live track ends within (seconds)', { bgcolor: RED, color: WHITE }, [{ type: 'number', id: 's', label: 'Seconds', default: 10, min: 1, max: 600 }], (fb) => {
			const d = Number(self.state?.live_dur), p = Number(self.state?.live_pos), o = Number(self.state?.live_out)
			if (!(d > 0) || st(self, 'state') !== 'playing') return false
			const end = o > 0 ? o : d
			return end - p <= Number(fb.options.s)
		}),
		health: bool('Player has a problem', { bgcolor: RED, color: WHITE }, [], () => {
			const h = self.state?.health?.status
			return h === 'error'
		}),
	}
}

