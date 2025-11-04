# Ableton to Blackbox Converter - Roadmap

## Current Status

The converter currently supports:
- ✅ Drum Rack workflow with Simplers → 16 Blackbox pads
- ✅ MIDI sequences in **Pads Mode** (trigger multiple pads from one sequence)
- ✅ Sequence length detection from MIDI clip length
- ✅ Automatic step length adjustment (default 1/16, scales up when needed)
- ✅ Beat count calculation for clip mode samples
- ✅ Choke group mapping
- ✅ Chain order-based pad mapping

## Planned Features

### 1. Keys Mode Sequences 🎹
**Priority**: High  
**Status**: Planned

#### Description
Convert MIDI tracks that are routed to a specific pad in the drum rack to Keys mode sequences in Blackbox.

#### How it works in Ableton
- A MIDI track is routed to a specific pad in the drum rack
- The MIDI clip contains notes that trigger that pad chromatically
- Example: A bassline MIDI track routed to Pad 5 (Kick) plays different pitches of the kick sample

#### How it should work in Blackbox
- Create a Keys mode sequence (`seqstepmode="0"`)
- Set `seqpadmapdest` to the target pad number
- Extract MIDI notes from the clip
- `pitch` values should be the actual MIDI note numbers (0-127)
- `chan` should be standard MIDI channel (not 256+pad)

#### Implementation Requirements
1. Detect if a MIDI track is routed to a specific drum rack pad
2. Extract the target pad number from routing information
3. Convert sequence to Keys mode with correct pitch values
4. Set `seqpadmapdest` to link sequence to the target pad

#### Technical Details
From the manual:
- Keys sequences have a chromatic keyboard along the left side of piano roll
- Each Keys sequence can record keys input for only one pad
- The pad is selected using the selection grid at top right in Keys mode
- Pitch values represent MIDI notes (0-127), not pad numbers

---

### 2. MIDI Mode Sequences 🎛️
**Priority**: High  
**Status**: Planned

#### Description
Convert MIDI tracks that route to external MIDI devices (like IAC Driver) to MIDI mode sequences in Blackbox.

#### How it works in Ableton
- A MIDI track is routed to an external MIDI device (e.g., IAC Driver)
- The routing specifies a MIDI channel (1-16)
- The MIDI clip contains notes to be sent externally
- Example in screenshot: "IAC Driver" with "Ch. 1"

#### How it should work in Blackbox
- Create a MIDI mode sequence
- Set `midioutchan` to the correct MIDI channel (0-15, where 0=Ch1, 15=Ch16)
- Extract MIDI notes from the clip
- `pitch` values should be MIDI note numbers (0-127)
- Sequence sends MIDI notes to external devices via Blackbox MIDI Out

#### Implementation Requirements
1. Detect if a MIDI track routes to external MIDI device
2. Extract the MIDI channel from routing information
3. Convert sequence to MIDI mode
4. Set correct `midioutchan` parameter (0-15)
5. Extract notes with actual MIDI pitch values

#### Technical Details
From the manual:
- MIDI mode sends MIDI notes to external MIDI devices
- `midioutchan`: MIDI Channel for output (None, Ch1-Ch16)
- MIDI sequences have same piano roll as Keys mode
- Pitch values represent MIDI notes (0-127)

---

### 3. Unquantised Sequences ⏱️
**Priority**: Medium  
**Status**: Planned

#### Description
Detect if MIDI content is quantised to the grid and preserve unquantised timing in Blackbox.

#### How it works in Ableton
- MIDI clips can have quantised notes (aligned to grid) or unquantised notes (free timing)
- Quantisation can be visually detected by checking if notes align to grid positions

#### How it should work in Blackbox
- If notes are unquantised: Set `StepMode` to OFF in Blackbox
- If notes are quantised: Keep `StepMode` to ON (default)
- Preserve exact timing information using `strtks` and `lentks` (tick-based timing)

#### Implementation Requirements
1. Analyze MIDI clip notes to detect if they're quantised to grid
2. Algorithm to determine quantisation:
   - Check if note start times align to 16th/8th/4th note grid (straight)
   - Check if note start times align to triplet grid
   - Calculate deviation from nearest grid position
   - If deviation exceeds threshold (e.g., > 10 ticks), mark as unquantised
   - **If both triplet and straight timing detected, mark as unquantised**
3. Set `StepMode` parameter accordingly
4. Ensure tick-based timing (`strtks`, `lentks`) is precise

#### Technical Details
- Blackbox supports both quantised (step mode ON) and unquantised (step mode OFF) sequences
- The converter already uses tick-based timing (1 beat = 3840 ticks)
- Need to add quantisation detection and `StepMode` parameter

#### Notes
- The current converter already supports `unquantised` flag but doesn't auto-detect
- May want to add a command-line option: `--auto-detect-quantization`

---

### 4. Intelligent Step Length Detection 🎼
**Priority**: Low  
**Status**: Planned (May Break Current Workflow)

#### Description
Automatically detect the finest note resolution in MIDI clips (e.g., 1/32 notes, triplets) and choose appropriate step length and count accordingly.

#### How it works currently
- Default to 1/16 step length (`notesteplen=10`)
- Only scale up to coarser resolutions (1/8, 1/4, etc.) when step count exceeds 256
- Does not detect finer resolutions like 1/32 or 1/64
- Does not use triplet values

#### How it should work
- Analyze MIDI clip to detect the finest note resolution used
- If 1/32 notes are present: Use 1/32 step length (`notesteplen=12`) or 1/64 (`notesteplen=14`)
- If triplets are present: Use appropriate triplet step length (11, 9, 7, 5, or 13)
- Automatically adjust step count to match detected resolution
- Fall back to 1/16 if no specific pattern detected

#### Implementation Requirements
1. **Resolution Detection Algorithm**:
   - Calculate the minimum time difference between consecutive notes
   - Detect common note patterns (16ths, 32nds, triplets)
   - Check if notes align to triplet grid vs straight grid
   
2. **Triplet Detection**:
   - Check if notes are spaced at 1/3 beat intervals (triplets)
   - Examples:
     - 1/16 triplets: 3 notes per beat at 1/3 spacing
     - 1/8 triplets: 3 notes per 2 beats
     - 1/4 triplets: 3 notes per bar
   
3. **Step Length Selection**:
   ```python
   def detect_step_length(midi_notes):
       has_triplets = has_triplet_pattern(midi_notes)
       has_straight = has_straight_pattern(midi_notes)
       
       # Mixed triplet and straight → treat as unquantised
       if has_triplets and has_straight:
           return None, True  # None step_len, unquantised=True
       
       min_interval = calculate_min_note_interval(midi_notes)
       
       if has_triplets:
           if min_interval <= 1/32:
               return 13, False  # 1/32 triplet
           elif min_interval <= 1/16:
               return 11, False  # 1/16 triplet
           elif min_interval <= 1/8:
               return 9, False   # 1/8 triplet
           # ... etc
       else:
           if min_interval <= 1/64:
               return 14, False  # 1/64
           elif min_interval <= 1/32:
               return 12, False  # 1/32
           elif min_interval <= 1/16:
               return 10, False  # 1/16 (default)
           # ... etc
   ```

4. **Step Count Adjustment**:
   - After selecting step length, recalculate step count
   - Ensure step count stays within 1-256 limit
   - May need to compromise between resolution and length

#### Potential Issues

1. **Breaking Current Workflow**:
   - Current default of 1/16 works well for most use cases
   - Auto-detection might choose unexpected resolutions
   - Could make sequences harder to edit in Blackbox

2. **Ambiguous Patterns**:
   - Some MIDI might have mixed resolutions (16ths + 32nds)
   - Hard to decide which resolution to prioritize
   - Unquantised MIDI might give false positives
   - **Mixed triplet and straight notes → Should be treated as unquantised**

3. **Step Count Limitations**:
   - 1/32 resolution uses twice as many steps as 1/16
   - 1/64 uses four times as many steps
   - Long sequences might exceed 256 step limit

4. **User Expectations**:
   - Users might expect 1/16 by default
   - Auto-detection could be surprising
   - May need manual override option

#### Recommendations

1. **Make it Optional**:
   - Add command-line flag: `--detect-resolution` or `--smart-step-length`
   - Keep current behavior as default
   - Let users opt-in to intelligent detection

2. **Provide Fallback**:
   - If detected resolution causes step count > 256, fall back to coarser resolution
   - Log a warning when this happens
   - Show detected vs actual resolution in verbose mode

3. **Add Configuration**:
   ```yaml
   sequences:
     step_length:
       mode: auto              # auto, fixed, smart
       default: 1/16           # Default when mode=fixed
       detect_triplets: false  # Enable triplet detection
       detect_32nds: false     # Enable 1/32 detection
       max_resolution: 1/16    # Finest resolution to use
   ```

4. **Testing Strategy**:
   - Test with sequences containing only 16th notes → Should use 1/16
   - Test with sequences containing 32nd notes → Should detect 1/32
   - Test with triplet patterns → Should detect triplet step length
   - Test with mixed patterns → Should handle gracefully
   - Test with very long sequences → Should not exceed 256 steps

#### Examples

**Example 1: 1/32 Note Detection**
```
MIDI: [0.0, 0.125, 0.25, 0.375, 0.5]  # 32nd notes
Detection: min_interval = 0.125 beats (1/32 of a bar)
Result: notesteplen=12 (1/32), notestepcount=128 for 4 bars
```

**Example 2: Triplet Detection**
```
MIDI: [0.0, 0.333, 0.667, 1.0, 1.333]  # 8th note triplets
Detection: Notes at 1/3 beat intervals
Result: notesteplen=9 (1/8T), notestepcount=24 for 4 bars
```

**Example 3: Mixed Resolution (Fallback)**
```
MIDI: Mix of 16th and 32nd notes (both straight)
Detection: Conflicting straight-note resolutions
Result: Fall back to 1/16 (safe default)
Warning: "Mixed note resolutions detected, using 1/16"
```

**Example 4: Mixed Triplet and Straight (Unquantised)**
```
MIDI: Some notes on triplet grid, some on straight 16th grid
Detection: Both triplet and straight timing detected
Result: Treat as unquantised (StepMode OFF)
Reason: Likely intentional expressive timing
```

#### Related Features
- Works well with **Unquantised Sequences** feature
- Both analyze note timing in detail
- Could share detection algorithms
- Might want to combine into one analysis pass
- **Key Integration**: If pattern uses both triplets and straight notes, treat as unquantised rather than choosing one grid

---

### 5. Song Mode (Arrangement View) 🎵
**Priority**: Low  
**Status**: Planned (Requires Refinement)

#### Description
Extract information from Ableton's Arrangement View and convert to Blackbox Song Mode.

#### How it works in Ableton
- Arrangement View has a timeline with locators
- Locators mark sections/scenes (e.g., Intro, Verse, Chorus)
- MIDI and audio clips are arranged on the timeline
- Clips can be referenced by name

#### How it should work in Blackbox
- Ableton Locators → Blackbox Song Mode Scenes
- MIDI clips with same name as session clips → Set to play in that scene
- Each scene triggers specific sequences/pads

#### Implementation Requirements (Needs Refinement)

##### Phase 1: Locator Extraction
1. Parse Arrangement View from `.als` file
2. Extract locator positions and names
3. Create Blackbox Song Mode scenes for each locator
4. Calculate scene length (distance between locators)

##### Phase 2: MIDI Clip Mapping
1. Extract MIDI clips from Arrangement View
2. Match MIDI clip names to session view sequences
3. Set sequences to play in corresponding scenes
4. Handle timing and quantization

##### Phase 3: Audio Clip Handling (Challenging)
- **Problem**: Audio clips are currently only supported in drum rack
- **Options**:
  - A) Skip audio clips in song mode for now
  - B) Require audio clips to be in drum rack first
  - C) Add new audio clip handling for arrangement view
- **Decision needed**: How to handle audio that's not in drum rack?

#### Technical Details
From the manual:
- Song Mode has scenes that can trigger sequences
- Each scene can have different active sequences
- Scenes can loop or play linearly
- Scene length is defined in bars/beats

#### Open Questions
1. How to handle audio clips that aren't in drum rack?
2. Should we require users to organize arrangement before conversion?
3. What happens if multiple clips have the same name?
4. How to handle overlapping clips in arrangement?
5. Should we support automation from arrangement view?

#### Recommendations
- Start with locator extraction only (Phase 1)
- Add MIDI clip mapping second (Phase 2)
- Defer audio clip handling until drum rack workflow is mature
- Consider a separate command-line flag: `--arrangement` or `--song-mode`

---

## Implementation Priority

### Immediate (Next Release)
1. **Keys Mode Sequences** - High value, relatively straightforward
2. **MIDI Mode Sequences** - High value, complements Keys mode

### Short Term
3. **Unquantised Sequences** - Medium complexity, nice-to-have for precise timing

### Long Term (Lower Priority)
4. **Intelligent Step Length Detection** - Auto-detect 1/32 notes and triplets
5. **Song Mode (Phase 1)** - Locator extraction
6. **Song Mode (Phase 2)** - MIDI clip mapping
7. **Song Mode (Phase 3)** - Audio clip handling (if feasible)

---

## Technical Considerations

### Keys Mode vs Pads Mode vs MIDI Mode

| Feature | Pads Mode | Keys Mode | MIDI Mode |
|---------|-----------|-----------|-----------|
| `seqstepmode` | `1` | `0` | `0` |
| `pitch` | Always `0` | MIDI note (0-127) | MIDI note (0-127) |
| `chan` | `256 + pad_number` | Standard MIDI | Standard MIDI |
| Target | Multiple pads | One specific pad | External MIDI |
| Use Case | Drum patterns | Melodic sequences | External synths |

### Detection Logic

```python
def detect_sequence_mode(midi_track, drum_rack):
    """Determine if sequence should be Pads, Keys, or MIDI mode"""
    
    # Check routing
    if routes_to_external_midi(midi_track):
        return 'MIDI', extract_midi_channel(midi_track)
    
    if routes_to_drum_rack_pad(midi_track, drum_rack):
        target_pad = extract_target_pad(midi_track, drum_rack)
        return 'Keys', target_pad
    
    # Default: Pads mode (current behavior)
    return 'Pads', None
```

### XML Structure Changes

#### Current (Pads Mode):
```xml
<params seqstepmode="1" seqpadmapdest="0" midioutchan="0" .../>
<seqevent chan="256" pitch="0" .../>  <!-- Triggers pad 0 -->
<seqevent chan="257" pitch="0" .../>  <!-- Triggers pad 1 -->
```

#### Proposed (Keys Mode):
```xml
<params seqstepmode="0" seqpadmapdest="5" midioutchan="0" .../>
<seqevent chan="256" pitch="36" .../>  <!-- C2 on pad 5 -->
<seqevent chan="256" pitch="38" .../>  <!-- D2 on pad 5 -->
```

#### Proposed (MIDI Mode):
```xml
<params seqstepmode="0" seqpadmapdest="0" midioutchan="0" .../>
<seqevent chan="0" pitch="60" .../> <!-- C3 on MIDI Ch1 -->
<seqevent chan="0" pitch="64" .../> <!-- E3 on MIDI Ch1 -->
```

---

## User Experience Improvements

### Command Line Flags
```bash
# Current
python3 xml_read_v2.py -i project.als -o output/

# Proposed additions
python3 xml_read_v2.py -i project.als -o output/ \
  --keys-mode           # Enable Keys mode detection
  --midi-mode           # Enable MIDI mode detection
  --auto-quantize       # Auto-detect quantization
  --arrangement         # Include song mode from arrangement
  --verbose             # Show detection details
```

### Configuration File
Consider adding a config file (e.g., `converter.yaml`):
```yaml
sequences:
  pads_mode: auto        # auto, always, never
  keys_mode: auto        # auto, always, never
  midi_mode: auto        # auto, always, never
  auto_quantize: true
  
song_mode:
  enabled: false
  include_audio: false
  
output:
  format: blackbox_v3
  copy_samples: true
```

---

## Testing Strategy

### Keys Mode Tests
- [ ] MIDI track routed to drum rack pad → Keys sequence
- [ ] Correct pad number in `seqpadmapdest`
- [ ] Pitch values match MIDI notes
- [ ] Multiple notes per step

### MIDI Mode Tests
- [ ] MIDI track routed to IAC Driver → MIDI sequence
- [ ] Correct MIDI channel extracted
- [ ] External routing preserved
- [ ] MIDI CC/automation (future)

### Unquantised Tests
- [ ] Quantised MIDI (straight grid) → `StepMode` ON
- [ ] Quantised MIDI (triplet grid) → `StepMode` ON
- [ ] Unquantised MIDI (off-grid) → `StepMode` OFF
- [ ] Mixed triplet + straight notes → `StepMode` OFF (treat as unquantised)
- [ ] Timing precision preserved
- [ ] Mixed quantization in same project

### Intelligent Step Length Tests
- [ ] Only straight 16th notes → Use 1/16
- [ ] Only straight 32nd notes → Detect and use 1/32
- [ ] Only triplet pattern → Detect and use triplet step length
- [ ] Mixed straight resolutions (16ths + 32nds) → Fall back to safe default
- [ ] Mixed triplet + straight → Treat as unquantised (StepMode OFF)
- [ ] Long sequences with fine resolution → Handle 256 step limit

### Song Mode Tests
- [ ] Locators extracted correctly
- [ ] Scene names match locator names
- [ ] MIDI clips mapped to scenes
- [ ] Scene lengths calculated properly

---

## Documentation Updates Needed

1. Update `README.md` with new features
2. Update `QUICKSTART.md` with Keys/MIDI mode examples
3. Create `KEYS_MODE_GUIDE.md` for melodic sequence workflow
4. Create `SONG_MODE_GUIDE.md` when implemented
5. Update `BLACKBOX_TECHNICAL_REFERENCE.md` with Keys/MIDI mode details

---

## Questions for User

1. **Keys Mode Priority**: Should this be the next feature implemented?
2. **MIDI Channel Detection**: How is MIDI channel info stored in Ableton's XML?
3. **Song Mode Scope**: Should we focus on MIDI-only first, or tackle audio too?
4. **Testing**: Do you have example projects for Keys and MIDI mode testing?
5. **Configuration**: Would you prefer command-line flags or a config file?

---

## Related Issues

- [KNOWN_ISSUES.md](../KNOWN_ISSUES.md): Pad mapping uses chain order
- [PAD_MAPPING.md](../PAD_MAPPING.md): Current pad mapping documentation
- [DRUM_RACK_WORKFLOW.md](../DRUM_RACK_WORKFLOW.md): Current workflow guide

---

*Last Updated: 2025-11-04*  
*Status: Planning Phase*

