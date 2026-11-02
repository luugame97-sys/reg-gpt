// Short, distinct sounds synthesized locally; no downloads or audio polling.
export const upiSoundNotes = {
  scanning: [[660, 0, .13], [880, .17, .16]],
  completed: [[523.25, 0, .18], [659.25, .12, .18], [783.99, .24, .18], [1046.5, .38, .32]],
}

export function createUpiSounds(createContext = () => {
  const Audio = window.AudioContext || window.webkitAudioContext
  return new Audio()
}) {
  let context, nextStart = 0
  const pending = new Map()
  const sounds = {
    async enable() {
      try {
        context ||= createContext()
        const current = context
        await current.resume()
        return context === current && current.state === 'running'
      } catch (_) { return false }
    },
    listen(target, wanted) {
      // Autoplay restrictions are handled by ordinary page interaction, without
      // another preference/permission button. No context is made when disabled.
      const unlock = () => { if (wanted()) void sounds.enable() }
      const options = { capture: true }
      target.addEventListener('pointerdown', unlock, options)
      target.addEventListener('keydown', unlock, options)
      unlock()
      return () => {
        target.removeEventListener('pointerdown', unlock, options)
        target.removeEventListener('keydown', unlock, options)
      }
    },
    async notify(kind, allowed, now = Date.now) {
      if (!allowed() || !upiSoundNotes[kind]) return false
      if (sounds.play(kind)) return true
      if (pending.has(kind)) return false
      const ticket = {}, started = now()
      pending.set(kind, ticket)
      try {
        const ready = await sounds.enable()
        return pending.get(kind) === ticket && ready && allowed() && now() - started <= 30000 && sounds.play(kind)
      } finally {
        if (pending.get(kind) === ticket) pending.delete(kind)
      }
    },
    play(kind) {
      if (!context || context.state !== 'running' || !upiSoundNotes[kind]) return false
      const now = Math.max(context.currentTime, nextStart)
      const notes = upiSoundNotes[kind], last = notes[notes.length - 1]
      nextStart = now + last[1] + last[2] + .16
      for (const [frequency, offset, duration] of notes) {
        const oscillator = context.createOscillator(), gain = context.createGain()
        oscillator.type = kind === 'completed' ? 'sine' : 'triangle'
        oscillator.frequency.value = frequency
        gain.gain.setValueAtTime(0, now + offset)
        gain.gain.linearRampToValueAtTime(.1, now + offset + .015)
        gain.gain.exponentialRampToValueAtTime(.001, now + offset + duration)
        oscillator.connect(gain); gain.connect(context.destination)
        oscillator.onended = () => { oscillator.disconnect(); gain.disconnect() }
        oscillator.start(now + offset); oscillator.stop(now + offset + duration)
      }
      return true
    },
    close() {
      pending.clear()
      if (context) context.close().catch(() => {})
      context = null
      nextStart = 0
    },
  }
  return sounds
}
