import { InstanceBase, InstanceStatus } from '@companion-module/base'
import { getActions } from './actions.js'
import { getFeedbacks } from './feedbacks.js'
import { getPresets } from './presets.js'
import { SLOTS, END_SHORT, MODULE_VERSION } from './consts.js'

export default class CueMediaEngineInstance extends InstanceBase {
	constructor(internal) {
		super(internal)
		this.state = {}
		this.playlists = []
		this.varNames = []
		this.rev = -1
		this.timer = null
		this.busy = false
		this.fails = 0
		this.lastPresetKey = ''
		this.versionWarned = null
	}

	async init(config, _isFirstInit, _secrets) {
		this.config = config
		this.setActionDefinitions(getActions(this))
		this.setFeedbackDefinitions(getFeedbacks(this))
		this.applyPresets()
		this.updateStatus(InstanceStatus.Connecting)
		this.startPolling()
	}

	async destroy() {
		this.stopPolling()
	}

	async configUpdated(config) {
		this.config = config
		this.stopPolling()
		this.rev = -1
		this.varNames = []
		this.setVariableDefinitions({})
		this.updateStatus(InstanceStatus.Connecting)
		this.startPolling()
	}

	getConfigFields() {
		return [
			{ type: 'static-text', id: 'info', width: 12, label: 'Cue Media Engine', value: 'Enter the address of the machine running the player (the same one you open in a browser).' },
			{ type: 'textinput', id: 'host', label: 'IP address', width: 8, default: '127.0.0.1', regex: '/^[A-Za-z0-9._-]+$/' },
			{ type: 'number', id: 'port', label: 'Port', width: 4, default: 8080, min: 1, max: 65535 },
			{ type: 'textinput', id: 'prefix', label: 'Variable prefix (fallback)', width: 6, default: 'mp_', regex: '/^[A-Za-z0-9_]*$/', tooltip: 'Used only when the player does not report its own prefix (a player older than 2.7.5 rc3). Newer players tell the module which prefix they send under; change it in the player at Settings > Companion.' },
			{ type: 'number', id: 'poll', label: 'Poll interval (ms)', width: 6, default: 250, min: 100, max: 5000 },
		]
	}

	applyPresets() {
		const { structure, presets } = getPresets(this)
		this.setPresetDefinitions(structure, presets)
	}

	get base() {
		const host = (this.config?.host || '127.0.0.1').trim()
		return `http://${host}:${this.config?.port || 8080}`
	}

	/**
	 * The prefix of every variable ID. The player says which prefix it sends under (variable_prefix in /api/state, changed in its Settings > Companion), and
	 * this module declares its variables with that one. Fallbacks, for a player that does not report one (older than 2.7.5 rc3): the prefix in this
	 * module's own configuration, then 'mp_'.
	 */
	get prefix() {
		return this.playerPrefix ?? this.config?.prefix ?? 'mp_'
	}

	/** Takes the player's reported prefix; true when it is a new valid one (the variables and presets must then be declared again). */
	adoptPrefix(reported) {
		if (typeof reported !== 'string' || !/^[A-Za-z][A-Za-z0-9_]{0,15}$/.test(reported)) return false
		if (reported === this.playerPrefix) return false
		this.playerPrefix = reported
		return true
	}

	async api(path, opts) {
		const ctl = new AbortController()
		const t = setTimeout(() => ctl.abort(), 3000)
		try {
			const r = await fetch(this.base + path, { ...opts, headers: { 'X-CompanionPlayer-Client': 'companion-module', ...(opts?.headers || {}) }, signal: ctl.signal })      // the player tells this module's polls from a browser's by this header (its Health panel: "Companion not answering")
			if (!r.ok) throw new Error(`HTTP ${r.status}`)
			return await r.json()
		} finally {
			clearTimeout(t)
		}
	}

	/** Run a player command, e.g. cmd('/volume/up/5') or cmd('/0/1', 500) */
	async cmd(path, ms) {
		let p = '/api' + (path.startsWith('/') ? path : '/' + path)
		if (ms !== undefined && ms !== null && ms !== '' && !isNaN(Number(ms))) p += `?ms=${Math.round(Number(ms))}`
		try {
			const res = await this.api(p)
			if (res && res.result && typeof res.result === 'string' && /^(error|bad|unknown)/i.test(res.result)) {
				this.log('warn', `${path}: ${res.result}`)
			}
			this.applyState(res)
			return res
		} catch (e) {
			this.log('error', `Command ${path} failed: ${e.message}`)
		}
	}

	startPolling() {
		const every = Math.max(100, Number(this.config?.poll) || 250)
		const tick = async () => {
			if (this.busy) return
			this.busy = true
			try {
				const st = await this.api('/api/state')
				if (this.fails > 0 || this.status !== 'ok') {
					this.status = 'ok'
					this.updateStatus(InstanceStatus.Ok)
				}
				this.fails = 0
				if (this.adoptPrefix(st.variable_prefix)) {
					this.varNames = []                // the prefix changed: declare every variable (and every preset that uses one) again under it
					this.lastPresetKey = null
				}
				if (st.rev !== this.rev || !this.varNames.length) {
					await this.refreshStructure()
					this.rev = st.rev
				}
				this.applyState(st)
			} catch (e) {
				this.fails++
				if (this.fails >= 3) {
					this.status = 'down'
					this.updateStatus(InstanceStatus.ConnectionFailure, `Cannot reach ${this.base}`)
				}
			} finally {
				this.busy = false
			}
		}
		this.timer = setInterval(tick, every)
		tick()
	}

	stopPolling() {
		if (this.timer) clearInterval(this.timer)
		this.timer = null
	}

	async refreshStructure() {
		const [vars, pls] = await Promise.all([this.api('/api/variables'), this.api('/api/playlists')])
		const list = vars.vars || []
		const names = list.map((v) => v.name)
		if (names.join(',') !== this.varNames.join(',')) {
			this.varNames = names
			const defs = {}
			for (const v of list) defs[this.prefix + v.name] = { name: v.info || v.name }
			for (let n = 1; n <= SLOTS; n++) defs[`${this.prefix}slot${n}_name`] = { name: `Track ${n} of the cued playlist (blank when there is none)` }
			defs[`${this.prefix}slot_count`] = { name: 'Number of tracks in the cued playlist' }
			defs[`${this.prefix}live_end`] = { name: 'End action of the live track: NEXT, ONCE, LOOP or STOP' }
			defs[`${this.prefix}version_match`] = { name: 'Player and module versions: ok when major.minor are equal, mismatch when they differ, unknown when the player reports no version' }
			defs[`${this.prefix}test`] = { name: 'Test message' }
			defs[`${this.prefix}health_state`] = { name: 'Player health: starting, ready, degraded or problem (blank when the player does not report it)' }
			defs[`${this.prefix}health_text`] = { name: 'Player health in words, e.g. "Disk space low" (blank when ready)' }
			defs[`${this.prefix}live_pass`] = { name: 'Pass of a live loop-once track, e.g. "1 of 2" (blank otherwise)' }
			this.slotCache = {}
			this.setVariableDefinitions(defs)
			const initial = {}
			for (const v of list) initial[this.prefix + v.name] = String(v.value)
			initial[`${this.prefix}test`] = ''
			this.setVariableValues(initial)
		}
		this.playlists = Array.isArray(pls) ? pls : []
		const key = JSON.stringify(this.playlists.map((p) => [p.name, p.tracks.map((t) => t.name)]))
		if (key !== this.lastPresetKey) {
			this.lastPresetKey = key
			this.setActionDefinitions(getActions(this))
			this.setFeedbackDefinitions(getFeedbacks(this))
			this.applyPresets()
		}
		this.checkAllFeedbacks()
	}

	applyState(st) {
		if (!st || typeof st !== 'object') return
		const { result, ...rest } = st
		const prev = this.state
		this.state = rest
		const vals = {}
		for (const n of this.varNames) {
			if (n in rest && rest[n] !== undefined && rest[n] !== prev[n]) vals[this.prefix + n] = String(rest[n])
		}
		Object.assign(vals, this.slotValues())
		if (Object.keys(vals).length) this.setVariableValues(vals)
		this.checkAllFeedbacks()
	}

	/** The health state the player reports (/api/state health.state), or '' when it reports none (a player older than 2.8: its health block has no state). */
	healthState() {
		const s = this.state?.health?.state
		return ['starting', 'ready', 'degraded', 'problem'].includes(s) ? s : ''
	}

	/** The short health summary while degraded or in a problem; blank otherwise. */
	healthText() {
		const s = this.healthState()
		return (s === 'degraded' || s === 'problem') && typeof this.state?.health?.summary === 'string' ? this.state.health.summary : ''
	}

	/** 'ok' | 'mismatch' | 'unknown': compares the player's major.minor with this module's. Logs one warning per distinct player version. */
	checkVersion(playerVersion) {
		const mm = (v) => String(v || '').match(/^(\d+)\.(\d+)/)?.slice(1, 3).join('.') || null
		const mine = mm(MODULE_VERSION)
		const theirs = mm(playerVersion)
		const result = !theirs ? 'unknown' : theirs === mine ? 'ok' : 'mismatch'
		const key = `${result}:${playerVersion || ''}`
		if (result !== 'ok' && this.versionWarned !== key) {
			this.log(
				'warn',
				result === 'unknown'
					? `The player did not report a version (older than 2.7?). This module is ${MODULE_VERSION}; update the player or use a matching module.`
					: `Version mismatch: the player is ${playerVersion}, this module is ${MODULE_VERSION} (major.minor must match). Some actions or variables may not work.`,
			)
		}
		this.versionWarned = result === 'ok' ? null : key
		return result
	}

	/**
	 * mp_test, the value of the player's last Settings > Companion > Send test. This module cannot receive OSC (it polls HTTP), so it reads
	 * test_message and test_sent_at from /api/state. A value counts as a (new) test only when test_sent_at is present and differs from the one
	 * seen before; while test_sent_at stays the same the value is kept as it is. When the player reports nothing (no test yet, a restart, or the
	 * 120 s after which it clears the message) mp_test is empty, so an old time can never pass for a fresh test.
	 */
	testValue() {
		const at = this.state?.test_sent_at
		const msg = this.state?.test_message
		if (at === null || at === undefined || at === '' || !msg) {
			this.testSeenAt = null
			this.testShown = ''
		} else if (at !== this.testSeenAt) {
			this.testSeenAt = at
			this.testShown = String(msg)
		}
		return this.testShown || ''
	}

	/** The tracks of the playlist that holds the cue, as slot1_name ... slotN_name */
	slotValues() {
		if (!this.varNames.length) return {}
		this.slotCache = this.slotCache || {}
		const pl = this.playlists[Number(this.state?.focus_playlist_num)]
		const tracks = pl ? pl.tracks : []
		const out = {}
		const put = (id, v) => {
			if (this.slotCache[id] !== v) {
				this.slotCache[id] = v
				out[id] = v
			}
		}
		for (let n = 1; n <= SLOTS; n++) put(`${this.prefix}slot${n}_name`, tracks[n - 1] ? tracks[n - 1].name : '')
		put(`${this.prefix}slot_count`, String(tracks.length))
		const end = this.state?.live_end || 'default'
		put(`${this.prefix}live_end`, END_SHORT[end] || 'NEXT')
		put(`${this.prefix}version_match`, this.checkVersion(this.state?.player_version))
		put(`${this.prefix}test`, this.testValue())
		put(`${this.prefix}health_state`, this.healthState())
		put(`${this.prefix}health_text`, this.healthText())
		put(`${this.prefix}live_pass`, Number(this.state?.live_passes) > 1 ? `${this.state.live_pass} of ${this.state.live_passes}` : '')
		return out
	}
}

export const UpgradeScripts = []
