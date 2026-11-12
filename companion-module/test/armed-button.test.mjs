// Unit tests of the "Input armed toggle" button (preset, feedback, action). Run:  npm test   (node --test test/)
// Not covered here (needs a real Companion): how the two colours look on a real button.
import test from 'node:test'
import assert from 'node:assert/strict'
import { combineRgb } from '@companion-module/base'
import { getActions } from '../src/actions.js'
import { getFeedbacks } from '../src/feedbacks.js'
import { getPresets } from '../src/presets.js'

const GREEN = combineRgb(0, 153, 0)
const RED = combineRgb(204, 0, 0)
const WHITE = combineRgb(255, 255, 255)

function mock(state) {
	const sent = []
	return { sent, playlists: [], state, prefix: 'mp_', label: 'cp', cmd: async (c) => sent.push(c) }
}
const preset = (self) => getPresets(self).presets.liveinput_armed

test('preset: named "Input armed toggle", in the Live input category', () => {
	const p = getPresets(mock({}))
	assert.equal(p.presets.liveinput_armed.name, 'Input armed toggle')
	const sec = p.structure.find((s) => s.definitions.includes('liveinput_armed'))
	assert.equal(sec.name, 'Live input')
})

test('preset: default look is unarmed, green with white INPUT / UNARMED', () => {
	const st = preset(mock({})).style
	assert.equal(st.text, 'INPUT\\nUNARMED')       // a literal \n, as Companion button text uses
	assert.equal(st.bgcolor, GREEN)
	assert.equal(st.color, WHITE)
	assert.strictEqual(st.size, '14', 'text size 14 (the string, like the other presets) in the default (unarmed) look')
})

test('preset: the feedback look is armed, red with white INPUT / ARMED', () => {
	const fbs = preset(mock({})).feedbacks
	assert.equal(fbs.length, 1)
	assert.equal(fbs[0].feedbackId, 'input_armed')
	assert.equal(fbs[0].style.bgcolor, RED)
	assert.equal(fbs[0].style.color, WHITE)
	assert.equal(fbs[0].style.text, 'INPUT\\nARMED')
	assert.strictEqual(fbs[0].style.size, '14', 'text size 14 in the feedback (armed) look too')
})

test('preset: both looks have the same size, and nothing else of the looks changed (texts, colours, step, feedback id)', () => {
	const p = preset(mock({}))
	assert.strictEqual(p.style.size, p.feedbacks[0].style.size)
	assert.deepEqual(Object.keys(p.feedbacks[0].style).sort(), ['bgcolor', 'color', 'size', 'text'])
	assert.deepEqual({ ...p.style, size: 0 }, { text: 'INPUT\\nUNARMED', size: 0, color: WHITE, bgcolor: GREEN })
	assert.deepEqual({ ...p.feedbacks[0].style, size: 0 }, { bgcolor: RED, color: WHITE, text: 'INPUT\\nARMED', size: 0 })
	assert.equal(p.feedbacks[0].feedbackId, 'input_armed')
})

test('preset: the press action is Toggle on the existing action id', () => {
	const steps = preset(mock({})).steps
	assert.equal(steps.length, 1)
	assert.deepEqual(steps[0].down, [{ actionId: 'input_armed', options: { v: 'toggle' } }])
	assert.deepEqual(steps[0].up, [])
})

test('the texts are fixed strings, not variables', () => {
	const p = preset(mock({}))
	assert.ok(!/\$\(/.test(p.style.text) && !/\$\(/.test(p.feedbacks[0].style.text))
})

test('feedback: armed, unarmed, and no state yet (the unarmed look, no error)', () => {
	const cases = [[{ input_armed: '1' }, true], [{ input_armed: '0' }, false], [undefined, false], [{}, false], [{ input_armed: undefined }, false]]
	for (const [state, want] of cases) {
		const fb = getFeedbacks(mock(state)).input_armed
		assert.equal(fb.type, 'boolean')
		assert.equal(fb.callback({ options: {} }), want, JSON.stringify(state))
	}
})

test('feedback: its default style is the red look', () => {
	const fb = getFeedbacks(mock({})).input_armed
	assert.equal(fb.name, 'Input armed')
	assert.equal(fb.defaultStyle.bgcolor, RED)
	assert.equal(fb.defaultStyle.color, WHITE)
})

test('feedback follows the state it is given at every poll (also when the web page changed it)', () => {
	const self = mock({ input_armed: '0' })
	const fb = getFeedbacks(self).input_armed
	assert.equal(fb.callback({ options: {} }), false)
	self.state = { input_armed: '1' }
	assert.equal(fb.callback({ options: {} }), true)
})

test('action: "Input arm / disarm" with Toggle, Arm, Disarm calls the same endpoint as the web switch', async () => {
	const self = mock({})
	const a = getActions(self).input_armed
	assert.equal(a.name, 'Input arm / disarm')
	assert.deepEqual(a.options[0].choices.map((c) => c.label), ['Toggle', 'Arm', 'Disarm'])
	for (const v of ['toggle', 'on', 'off']) await a.callback({ options: { v } })
	assert.deepEqual(self.sent, ['/input/armed/toggle', '/input/armed/on', '/input/armed/off'])
})

test('no existing action or feedback id was renamed', () => {
	const a = getActions(mock({}))
	for (const id of ['input_armed', 'input_duck_now', 'duck', 'duck_hold', 'take']) assert.ok(a[id], id)
	const f = getFeedbacks(mock({}))
	for (const id of ['input_armed', 'input_duck_now', 'input_signal', 'input_ducking', 'duck_hold']) assert.ok(f[id], id)
})
