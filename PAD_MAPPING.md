# Blackbox Pad Mapping - How Ableton Tracks Map to Blackbox Pads

## Visual Layout

The Blackbox has 16 pads in a 4x4 grid. **Pads are numbered 1-16, starting from bottom-left.**

```
Blackbox Pad Layout (1-indexed):
┌────┬────┬────┬────┐
│ 13 │ 14 │ 15 │ 16 │  Row 0 (top)
├────┼────┼────┼────┤
│ 9  │ 10 │ 11 │ 12 │  Row 1
├────┼────┼────┼────┤
│ 5  │ 6  │ 7  │ 8  │  Row 2
├────┼────┼────┼────┤
│ 1  │ 2  │ 3  │ 4  │  Row 3 (bottom)
└────┴────┴────┴────┘
Col:  0    1    2    3

Note: Internally, the code uses 0-15 (0-indexed), which maps to:
- Internal pad 0 → Blackbox pad 1 (bottom-left)
- Internal pad 15 → Blackbox pad 16 (top-right)
```

## Mapping Logic

### Step 1: Simpler/Sampler Instruments → Pads 1-16

**The first up to 16 Simpler/Sampler tracks** in your Ableton project get mapped to pads 1-16 in order:

```
Ableton Track Order:        Blackbox Pad (1-indexed):
─────────────────────────────────────────────────────
Simpler Track 1      →      Pad 1 (bottom-left)
Simpler Track 2      →      Pad 2
Simpler Track 3      →      Pad 3
Simpler Track 4      →      Pad 4 (bottom-right)
Simpler Track 5      →      Pad 5
...                  →      ...
Simpler Track 16     →      Pad 16 (top-right)
```

**Note**: The code uses 0-15 internally, but Blackbox displays pads as 1-16.

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
Simpler Track 1      →      Pad 1 (bottom-left)
Simpler Track 2      →      Pad 2
Simpler Track 3      →      Pad 3
Simpler Track 4      →      Pad 4
Simpler Track 5      →      Pad 5
Audio Track 1        →      Pad 6  ← Audio clips start here
Audio Track 2        →      Pad 7
Audio Track 3        →      Pad 8
...
```

**Example 2:** If you have 16 Simpler tracks (max):
```
Simpler Track 1-16   →      Pads 1-16 (fills all 16 pads)
```

**Example 3:** If you have 0 Simpler tracks (audio clips only):
```
Audio Track 1        →      Pad 1 (bottom-left)
Audio Track 2        →      Pad 2
Audio Track 3        →      Pad 3
...
Audio Track 16       →      Pad 16 (top-right)
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
    for i in range(current_pad, 16):
        # ... create empty pads ...
```

## Important Details

### Pad Numbering
The internal pad numbering (0-15) maps to physical Blackbox layout like this:

```python
row_column(pad):
    # Internal pad → [row, col] → Blackbox pad (1-indexed)
    0:[3,0]   1:[3,1]   2:[3,2]   3:[3,3]   # Row 3 (bottom) → Pads 1-4
    4:[2,0]   5:[2,1]   6:[2,2]   7:[2,3]   # Row 2 → Pads 5-8
    8:[1,0]   9:[1,1]  10:[1,2]  11:[1,3]   # Row 1 → Pads 9-12
   12:[0,0]  13:[0,1]  14:[0,2]  15:[0,3]   # Row 0 (top) → Pads 13-16
```

**Note**: Row 3 is the bottom row (pads 1-4), Row 0 is the top row (pads 13-16).

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
2. **Max 16 pads total** - Blackbox has 16 pads, so if you have 16 Simpler tracks, there's no room for additional audio clips
3. **Order matters** - Tracks are processed in the order they appear in Ableton

## Practical Examples

### Stem-Based Project
```
Your Ableton project:
- Audio Track "Kick"       →  Pad 1 (bottom-left, loop)
- Audio Track "Bass"       →  Pad 2 (loop)
- Audio Track "Synth"      →  Pad 3 (loop)
- Audio Track "Vocals"     →  Pad 4 (bottom-right, loop)
- Audio Track "FX"         →  Pad 5 (loop)

All pads will be in loop mode, ready to trigger your stems!
```

### Drum Machine Project
```
Your Ableton project:
- Simpler "Kick"           →  Pad 1 (bottom-left, one-shot)
- Simpler "Snare"          →  Pad 2 (one-shot)
- Simpler "Hihat Closed"   →  Pad 3 (one-shot)
- Simpler "Hihat Open"     →  Pad 4 (bottom-right, one-shot)
- Simpler "Clap"           →  Pad 5 (one-shot)
- Simpler "Tom 1"          →  Pad 6 (one-shot)
- Simpler "Tom 2"          →  Pad 7 (one-shot)
- Simpler "Crash"          →  Pad 8 (one-shot)

Perfect for finger drumming on the Blackbox!
```

### Hybrid Project
```
Your Ableton project:
- Simpler "Kick"           →  Pad 1 (bottom-left, one-shot)
- Simpler "Snare"          →  Pad 2 (one-shot)
- Simpler "Hihat"          →  Pad 3 (one-shot)
- Simpler "Bass Sample"    →  Pad 4 (one-shot)
- Audio "Synth Loop"       →  Pad 5 (loop)
- Audio "Vocal Loop"       →  Pad 6 (loop)
- Audio "FX Loop"          →  Pad 7 (loop)

Mix of one-shots and loops!
```

## Checking Your Mapping

After conversion, you can check the mapping by looking at the generated `preset.xml`:

```bash
# View the cell mappings
cat output/preset.xml | grep '<cell' | grep 'layer="0"' | head -16

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
2. Max 16 total tracks (Simpler + Audio clips combined)
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

**Yes, Simpler instruments 1-16 map to pads 1-16** (or however many you have up to 16).

**Audio tracks map sequentially AFTER** the Simpler/Sampler pads, continuing from wherever those left off.

The script fills pads in order: **Simpler/Sampler first, then Audio clips, then empty pads** to fill all 16 pads.

**Important**: Blackbox pads are numbered 1-16, with pad 1 at bottom-left. The code uses 0-15 internally, but the output matches Blackbox's 1-indexed display.

---

*See `xml_read_v2.py` lines 584-720 for the exact implementation.*


