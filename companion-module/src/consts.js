export const SLOTS = 32

/** This module's version: keep it equal to "version" in package.json. The player's APP_VERSION must have the same major.minor. */
export const MODULE_VERSION = '2.8.0'

/** The player's level-meter taper (METER_STOPS in player.py): dBFS -> % of the meter height. Mirrored here only to place the gauge
 *  colour stops; the values themselves (live_fader_l/r ...) come from the player already on this scale. */
export const METER_STOPS = [[0, 100], [-5, 88], [-10, 76], [-20, 60], [-30, 46], [-40, 33], [-50, 21], [-60, 10], [-90, 0]]
export const METER_AMBER_DB = -17
export const METER_RED_DB = -6
export function taperPct(db) {
	if (db >= 0) return 100
	for (let i = 0; i < METER_STOPS.length - 1; i++) {
		const [d1, p1] = METER_STOPS[i], [d2, p2] = METER_STOPS[i + 1]
		if (db >= d2) return p2 + ((p1 - p2) * (db - d2)) / (d1 - d2)
	}
	return 0
}

/** What a track does when it ends (player: /<p>/<t>/end/<value>) */
export const END_CHOICES = [
	{ id: 'default', label: 'Then play the next track (follow the playlist)' },
	{ id: 'once', label: 'Loop once, then continue' },
	{ id: 'loop', label: 'Loop forever' },
	{ id: 'stop', label: 'Stop at this track' },
]
export const END_SHORT = { default: 'NEXT', once: 'ONCE', loop: 'LOOP', stop: 'STOP' }
