#!/usr/bin/env python3
"""AVAudioPlayer не отпускаем во время звучания: 1.0 (23) падал на finishedPlaying: после dealloc."""
import pathlib, re, sys

src = (pathlib.Path(__file__).resolve().parent.parent / "Postman/Services/SoundPlayback.swift").read_text()
errors = []
if "private func retire(_ player: AVAudioPlayer)" not in src:
    errors.append("нет retire(_:)")
body = src.split("private func retire(_ player: AVAudioPlayer)", 1)[-1].split("\n    }\n", 1)[0]
if "player.stop()" not in body or "retired.append(player)" not in body:
    errors.append("retire должен остановить плеер и подержать его")
if re.search(r"effects\[slot\] = fresh\n(?!\s*retire\(player\))", src):
    errors.append("замена плеера в слоте без retire(player)")
if "old?.stop()" in src or "{ player.stop() }" in src:
    errors.append("отложенный stop без retire")
m = re.search(r"retireHold: TimeInterval = ([0-9.]+)", src)
if not m or float(m.group(1)) < 1:
    errors.append("retireHold должен быть >= 1 с")
if errors:
    print("FAIL:", "; ".join(errors)); sys.exit(1)
print("OK audio player lifetime")
