// Unit tests of the Health variables, feedback and preset (module 2.8.0). Run:  npm test   (node --test test/)
import test from 'node:test'
import assert from 'node:assert/strict'
import { combineRgb } from '@companion-module/base'
import { getFeedbacks } from '../src/feedbacks.js'
import { getPresets } from '../src/presets.js'
import { MODULE_VERSION } from '../src/consts.js'
import ModuleInstance from '../src/main.js'

const AMBER = combineRgb(255, 191, 0)
const RED = combineRgb(204, 0, 0)
const BLACK = combineRgb(0, 0, 0)
const WHITE = combineRgb(255, 255, 255)

function lum(c) {
	const f = (v) => ((v /= 255) <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4))
	return 0.2126 * f((c >> 16) & 255) + 0.7152 * f((c >> 8) & 255) + 0.0722 * f(c & 255)
}
const contrast = (a, b) => (Math.max(lum(a), lum(b)) + 0.05) / (Math.min(lum(a), lum(b)) + 0.05)

// the real class with just enough around it: state is set by hand, no polling
function inst(state, prefix = 'mp_') {
	const m = Object.create(ModuleInstance.prototype)
	m.state = state
	m.playerPrefix = prefix
	m.config = {}
	Object.defineProperty(m, 'label', { value: 'cp' })      // a getter on the base class
	m.playlists = []
	return m
}
const health = (state, summary = '') => ({ health: { status: 'ready', detail: 'Ready', state, summary, checks: [] } })

test('the module is 2.8.0', () => assert.equal(MODULE_VERSION, '2.8.0'))

test('variables: health_state follows the player, health_text only while degraded or in a problem', () => {
	for (const [state, summary, text] of [['ready', '', ''], ['starting', '', ''], ['degraded', 'Disk space low', 'Disk space low'], ['problem', 'Live output problem', 'Live output problem'], ['ready', 'stale words', '']]) {
		const m = inst(health(state, summary))
		assert.equal(m.healthState(), state)
		assert.equal(m.healthText(), text, `${state}/${summary}`)
	}
})

test('variables: a player without a health state leaves both empty', () => {
	for (const st of [{}, { health: { status: 'ready', detail: 'Ready' } }, { health: { state: 'weird', summary: 'x' } }, { health: null }, undefined]) {
		const m = inst(st)
		assert.equal(m.healthState(), '')
		assert.equal(m.healthText(), '')
	}
})

test('variables: they are declared and valued under the player prefix', async () => {
	for (const prefix of ['mp_', 'foh_']) {
		const m = inst(health('degraded', 'Companion not answering'), prefix)
		let defs = null
		m.varNames = []
		m.slotCache = {}
		m.setVariableDefinitions = (d) => (defs = d)
		m.setVariableValues = () => {}
		m.setActionDefinitions = m.setFeedbackDefinitions = m.applyPresets = m.checkAllFeedbacks = m.log = () => {}
		m.api = async (p) => (p === '/api/variables' ? { vars: [{ name: 'status', value: 'ready', info: '' }] } : [])
		await m.refreshStructure()
		const out = m.slotValues()
		assert.ok(defs[`${prefix}health_state`] && defs[`${prefix}health_text`], 'declared')
		assert.equal(out[`${prefix}health_state`], 'degraded')
		assert.equal(out[`${prefix}health_text`], 'Companion not answering')
	}
})

test('feedback: Degraded, Problem and Degraded-or-problem each react to the right state', () => {
	const cases = { degraded: { degraded: true, problem: false, either: true }, problem: { degraded: false, problem: true, either: true }, ready: { degraded: false, problem: false, either: false }, starting: { degraded: false, problem: false, either: false } }
	for (const [state, want] of Object.entries(cases)) {
		const fb = getFeedbacks(inst(health(state, 'x'))).health_state
		for (const which of ['degraded', 'problem', 'either']) assert.equal(fb.callback({ options: { which } }), want[which], `${state} / ${which}`)
	}
})

test('feedback: with a player that sends no health state it never fires', () => {
	const fb = getFeedbacks(inst({ health: { status: 'error', detail: 'x' } })).health_state
	for (const which of ['degraded', 'problem', 'either']) assert.equal(fb.callback({ options: { which } }), false)
	assert.equal(getFeedbacks(inst({})).health_state.callback({ options: { which: 'either' } }), false)
})

test('feedback: default style is amber with dark text; both looks pass 4.5:1', () => {
	const fb = getFeedbacks(inst({})).health_state
	assert.equal(fb.type, 'boolean')
	assert.deepEqual(fb.defaultStyle, { bgcolor: AMBER, color: BLACK })
	assert.ok(contrast(AMBER, BLACK) >= 4.5, `amber/dark ${contrast(AMBER, BLACK).toFixed(1)}`)
	assert.ok(contrast(RED, WHITE) >= 4.5, `red/white ${contrast(RED, WHITE).toFixed(1)}`)
	assert.deepEqual(fb.options[0].choices.map((c) => c.id), ['degraded', 'problem', 'either'])
})

test('preset: HEALTH with the health_text, amber for degraded, red for a problem, size 14, in its own category', () => {
	const p = getPresets(inst({}))
	const pr = p.presets.health
	assert.ok(pr)
	assert.equal(pr.style.text, 'HEALTH\\n$(cp:mp_health_text)')       // a literal \n, as Companion button text uses
	assert.strictEqual(pr.style.size, '14')
	assert.deepEqual(pr.feedbacks.map((f) => [f.feedbackId, f.options.which]), [['health_state', 'degraded'], ['health_state', 'problem']])
	assert.equal(pr.feedbacks[0].style.bgcolor, AMBER)
	assert.equal(pr.feedbacks[0].style.color, BLACK)
	assert.equal(pr.feedbacks[1].style.bgcolor, RED)
	assert.equal(pr.feedbacks[1].style.color, WHITE)
	assert.ok(p.structure.find((s) => s.definitions.includes('health')))
	assert.equal(p.structure.find((s) => s.definitions.includes('health')).name, 'Health')
})

test('preset: the variable follows a custom prefix', () => {
	assert.equal(getPresets(inst({}, 'foh_')).presets.health.style.text, 'HEALTH\\n$(cp:foh_health_text)')
})

test('requests carry the header the player uses to recognise Companion polls', async () => {
	const m = inst({})
	m.config = { host: '127.0.0.1', port: 1 }
	const seen = []
	const real = globalThis.fetch
	globalThis.fetch = async (url, opts) => (seen.push(opts.headers), { ok: true, json: async () => ({}) })
	try {
		await m.api('/api/state')
	} finally {
		globalThis.fetch = real
	}
	assert.equal(seen[0]['X-CompanionPlayer-Client'], 'companion-module')
})
