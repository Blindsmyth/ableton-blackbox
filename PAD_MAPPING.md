# Blackbox Pad Mapping - How Ableton Tracks Map to Blackbox Pads

## Visual Layout

The Blackbox has 20 pads total: a 4x4 grid (16 pads) + 4 extra pads in column 5.

```
Blackbox Pad Layout:
┌────┬────┬────┬────┬────┐
│ 0  │ 1  │ 2  │ 3  │ 16 │  Row 0
├────┼────┼────┼────┼────┤
│ 4  │ 5  │ 6  │ 7  │ 17 │  Row 1
├────┼────┼────┼────┼────┤
│ 8  │ 9  │ 10 │ 11 │ 18 │  Row 2
├────┼────┼────┼────┼────┤
│ 12 │ 13 │ 14 │ 15 │ 19 │  Row 3
└────┴────┴────┴────┴────┘
Col:  0    1    2    3    4
```

## Mapping Logic

### Step 1: Simpler/Sampler Instruments → Pads 0-15

**The first up to 16 Simpler/Sampler tracks** in your Ableton project get mapped to pads 0-15 in order:

```
Ableton Track Order:        Blackbox Pad:
─────────────────────────────────────────
Simpler Track 1      →      Pad 0
Simpler Track 2      →      Pad 1
Simpler Track 3      →      Pad 2
...                  →      ...
Simpler Track 16     →      Pad 15
```

**Settings for Simpler/Sampler pads:**
- Mode: One-shot sample
- Trigger: Note-on (`samtrigtype = 1`)
- Loop: OFF
- Polyphony: 4 voices (`polymode = 3`)
- ADSR: Extracted from Ableton
- Sample start/end: Extracted from Ableton

### Step 2: Audio Clips → Starting After Simpler/Sampler

**Audio clips are added AFTER** the Simpler/Sampler pads, continuing the count:

**Example 1:** If you have 5 Simpler tracks:
```
Simpler Track 1      →      Pad 0
Simpler Track 2      →      Pad 1
Simpler Track 3      →      Pad 2
Simpler Track 4      →      Pad 3
Simpler Track 5      →      Pad 4
Audio Track 1        →      Pad 5  ← Audio clips start here
Audio Track 2        →      Pad 6
Audio Track 3        →      Pad 7
...
```

**Example 2:** If you have 16 Simpler tracks (max):
```
Simpler Track 1-16   →      Pads 0-15 (fills main grid)
Audio Track 1        →      Pad 16  ← Spills into column 5
Audio Track 2        →      Pad 17
Audio Track 3        →      Pad 18
Audio Track 4        →      Pad 19
```

**Example 3:** If you have 0 Simpler tracks (stems only):
```
Audio Track 1        →      Pad 0
Audio Track 2        →      Pad 1
Audio Track 3        →      Pad 2
...
Audio Track 16       →      Pad 15
Audio Track 17       →      Pad 16 (column 5)
...
```

**Settings for Audio Clip pads:**
- Mode: Loop mode (`cellmode = 1`)
- Trigger: Loop trigger (`samtrigtype = 2`)
- Loop: ON (`loopmode = 1`)
- Polyphony: Mono (`polymode = 0`)
- Beat count: Extracted from clip length
- Sample rate: Assumed 48kHz

## The Code

Here's the relevant part from `xml_read_v2.py`:

```python
def make_pads(from_ableton, clips, tempo):
    current_pad = 0
    
    # STEP 1: Add Simpler/Sampler instruments (max 16)
    if len(from_ableton) > 0:
        preset = min(len(from_ableton), 16)  # Max 16
        for i in range(preset):
            row, column = row_column(current_pad)  # Maps to pad position
            # ... create sample pad ...
            current_pad += 1
    
    # STEP 2: Add audio clips AFTER Simpler/Sampler
    for track in clips:
        for clip in track:
            row, column = row_column(current_pad)  # Continues from where step 1 left off
            # ... create loop pad ...
            current_pad += 1
    
    # STEP 3: Fill remaining pads with empty templates
    for i in range(current_pad, 20):
        # ... create empty pads ...
```

## Important Details

### Pad Numbering
The internal pad numbering (0-19) maps to physical Blackbox layout like this:

```python
row_column(pad):
    0:[0,0]   1:[0,1]   2:[0,2]   3:[0,3]   # Row 0
    4:[1,0]   5:[1,1]   6:[1,2]   7:[1,3]   # Row 1
    8:[2,0]   9:[2,1]  10:[2,2]  11:[2,3]   # Row 2
   12:[3,0]  13:[3,1]  14:[3,2]  15:[3,3]   # Row 3
   16:[0,4]  17:[1,4]  18:[2,4]  19:[3,4]   # Column 5
```

### Track Filtering
Only certain Ableton track types are extracted:
- **Simpler tracks** (`OriginalSimpler` device) → Sample pads
- **Sampler tracks** (`MultiSampler` device) → Sample pads
- **Audio tracks** (with audio clips) → Loop pads
- ❌ MIDI tracks without Simpler/Sampler → NOT mapped to pads
- ❌ Return tracks → NOT mapped to pads
- ❌ Group tracks → NOT mapped to pads

### Limitations
1. **Max 16 Simpler/Sampler** - If you have more than 16, only the first 16 are used
2. **No overflow protection** - If you have 16 Simpler + 5 audio clips = 21 total, but Blackbox only has 20 pads, the 21st would cause issues
3. **Order matters** - Tracks are processed in the order they appear in Ableton

## Practical Examples

### Stem-Based Project
```
Your Ableton project:
- Audio Track "Kick"       →  Pad 0 (loop)
- Audio Track "Bass"       →  Pad 1 (loop)
- Audio Track "Synth"      →  Pad 2 (loop)
- Audio Track "Vocals"     →  Pad 3 (loop)
- Audio Track "FX"         →  Pad 4 (loop)

All pads will be in loop mode, ready to trigger your stems!
```

### Drum Machine Project
```
Your Ableton project:
- Simpler "Kick"           →  Pad 0 (one-shot)
- Simpler "Snare"          →  Pad 1 (one-shot)
- Simpler "Hihat Closed"   →  Pad 2 (one-shot)
- Simpler "Hihat Open"     →  Pad 3 (one-shot)
- Simpler "Clap"           →  Pad 4 (one-shot)
- Simpler "Tom 1"          →  Pad 5 (one-shot)
- Simpler "Tom 2"          →  Pad 6 (one-shot)
- Simpler "Crash"          →  Pad 7 (one-shot)

Perfect for finger drumming on the Blackbox!
```

### Hybrid Project
```
Your Ableton project:
- Simpler "Kick"           →  Pad 0 (one-shot)
- Simpler "Snare"          →  Pad 1 (one-shot)
- Simpler "Hihat"          →  Pad 2 (one-shot)
- Simpler "Bass Sample"    →  Pad 3 (one-shot)
- Audio "Synth Loop"       →  Pad 4 (loop)
- Audio "Vocal Loop"       →  Pad 5 (loop)
- Audio "FX Loop"          →  Pad 6 (loop)

Mix of one-shots and loops!
```

## Checking Your Mapping

After conversion, you can check the mapping by looking at the generated `preset.xml`:

```bash
# View the cell mappings
cat output/preset.xml | grep '<cell' | grep 'layer="0"' | head -20

# Example output:
# <cell column="0" filename=".\kick.wav" layer="0" row="0" type="sample">
# <cell column="1" filename=".\snare.wav" layer="0" row="0" type="sample">
# ...
```

Or use verbose mode to see what's being mapped:

```bash
python3 xml_read_v2.py -i "project.als" -o "output" -m -v
```

Look for lines like:
```
INFO: Track 1, track type: AudioTrack
INFO: Track 2, track type: MidiTrack
INFO:   Device 1: OriginalSimpler
```

## Tips for Best Results

### For Stem-Based Workflow:
1. Arrange your most important stems first in Ableton
2. Keep to 16 audio tracks or less for main grid
3. Use clear, descriptive track names

### For Sample-Based Workflow:
1. Place your most-used Simpler instruments first
2. Max 16 Simpler/Sampler tracks
3. Group less important samples in multisamples

### For Hybrid:
1. Put drums/one-shots (Simpler) first
2. Put loops/stems (Audio) after
3. Plan your layout for the 4x4 grid

## Summary

**Yes, Simpler instruments 1-16 map to pads 0-15** (or however many you have up to 16).

**Audio tracks map sequentially AFTER** the Simpler/Sampler pads, continuing from wherever those left off.

The script fills pads in order: **Simpler/Sampler first, then Audio clips, then empty pads** to fill up to 20 total.

---

*See `xml_read_v2.py` lines 584-720 for the exact implementation.*


