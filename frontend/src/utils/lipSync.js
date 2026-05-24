/**
 * Volume-based lip sync using Web Audio API AnalyserNode.
 * Maps RMS volume to a 0-1 mouth openness value.
 */

export class LipSync {
  constructor() {
    this.audioContext = null
    this.analyser = null
    this.source = null
    this.audio = null
    this.running = false
    this.onUpdate = null // callback(mouthOpenValue)
  }

  /**
   * Start analysing an Audio element.
   * @param {HTMLAudioElement} audio
   * @param {(value: number) => void} onUpdate - called each frame with 0-1 mouth openness
   */
  start(audio, onUpdate) {
    this.stop()

    if (!this.audioContext) {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)()
    }

    this.audio = audio
    this.onUpdate = onUpdate
    this.analyser = this.audioContext.createAnalyser()
    this.analyser.fftSize = 256
    this.analyser.smoothingTimeConstant = 0.3

    this.source = this.audioContext.createMediaElementSource(audio)
    this.source.connect(this.analyser)
    this.analyser.connect(this.audioContext.destination)

    this.running = true
    this._tick()
  }

  stop() {
    this.running = false
    if (this.source) {
      try { this.source.disconnect() } catch (_) { /* already disconnected */ }
      this.source = null
    }
    this.analyser = null
    this.audio = null
    this.onUpdate = null
  }

  _tick() {
    if (!this.running || !this.analyser) return

    const data = new Uint8Array(this.analyser.frequencyBinCount)
    this.analyser.getByteFrequencyData(data)

    // RMS volume → map to 0-1
    let sum = 0
    for (let i = 0; i < data.length; i++) {
      sum += data[i] * data[i]
    }
    const rms = Math.sqrt(sum / data.length) / 255
    // Amplify and clamp for better mouth visibility
    const value = Math.min(1, rms * 3.0)

    if (this.onUpdate) {
      this.onUpdate(value)
    }

    if (this.running) {
      requestAnimationFrame(() => this._tick())
    }
  }
}
