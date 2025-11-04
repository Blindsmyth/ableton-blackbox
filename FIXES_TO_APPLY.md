# Fixes To Apply - User Taking Break

## Issues Identified

### Issue 1: Track 1 (Seq2) Should Be MIDI Mode
**Status**: Needs Fix  
**Priority**: High

**Problem**:
- Track 1 has external MIDI output (IAC Driver Bus 1)
- Currently being detected correctly as MIDI mode
- But user says it's showing as Keys mode in Blackbox

**Investigation Needed**:
- Verify routing detection is working: `MidiOut/External.Dev:IAC Driver (Bus 1)/0`
- Check if `seqstepmode` is being set correctly (`0` for MIDI/Keys)
- Check if `midioutchan` is being set (should be `0` for MIDI channel 1)
- Check if `seqpadmapdest` is `0` for MIDI mode

---

### Issue 2: Warp Detection Broken - No Warped Samples Detected as Clips
**Status**: Critical Bug  
**Priority**: Critical

**Problem**:
- After fix for Issue #2 (pad 8 clip mode), warp detection stopped working
- Changed logic to: `if warp_info.get('is_warped', False) and beat_count >= 8:`
- Now NO warped samples are being detected, so `is_warped` is always False
- Warped samples (like HatLoop, percussion layers) should be in clip mode

**Current Code (lines 1145-1157)**:
```python
if warp_info.get('is_warped', False) and beat_count >= 8:
    cellmode = '1'  # Clip mode for warped longer samples
    loopmode = '1'  # Loop enabled
    logger.info(f'    → Warped sample: {beat_count} beats ({beat_count/4} bars), clip mode enabled')
else:
    # Unwarped or short sample - sampler mode
    if warp_info.get('is_warped', False):
        loopmode = '1'  # Loop enabled for warped samples
        logger.info(f'    → Warped sample: {beat_count} beats ({beat_count/4} bars), sampler mode with loop')
    else:
        # Unwarped sample - don't enable loop by default
        loopmode = '0'
        logger.info(f'    → Unwarped sample: {beat_count} beats ({beat_count/4} bars), sampler mode (no auto-loop)')
```

**Root Cause**:
- `detect_warped_stem()` (lines 552-676) is not correctly detecting warp status
- Need to check what XML elements actually indicate warping
- Possible locations:
  - `SampleWarpProperties/WarpMode` (should be > 0 if warped)
  - `SampleWarpProperties/IsWarped` (should be "true" if warped)
  - `SampleRef/Warp/Mode/WarpOn` (might be the actual flag)

**Investigation Steps**:
1. Check actual XML structure for known warped sample (HatLoop, percussion layers)
2. Identify correct XML path for warp detection
3. Update `detect_warped_stem()` to correctly extract warp status
4. Test with known warped and unwarped samples

**Expected Behavior**:
- Warped samples with >= 8 beats → `cellmode=1` (clip mode)
- Warped samples with < 8 beats → `cellmode=0`, `loopmode=1` (sampler with loop)
- Unwarped samples → `cellmode=0`, `loopmode=0` (sampler, no auto-loop)

---

## Debugging Commands

### Check Track 1 Routing
```bash
python3 -c "
import xml.etree.ElementTree as ET
import gzip

with gzip.open('../Ableton Files/An mir Vorbei Project/An mir Vorbei test unquantised.als', 'rb') as f:
    tree = ET.parse(f)
    root = tree.getroot()

tracks = root.findall('.//MidiTrack')
track_1 = tracks[1]
midi_out = track_1.find('.//MidiOutputRouting/Target')
if midi_out:
    routing = midi_out.attrib.get('Value', 'None')
    print(f'Track 1 routing: {routing}')
    print(f'Should detect as: MIDI mode')
"
```

### Check Warp Detection for Known Warped Sample
```bash
python3 -c "
import xml.etree.ElementTree as ET
import gzip

with gzip.open('../Ableton Files/An mir Vorbei Project/An mir Vorbei test unquantised.als', 'rb') as f:
    tree = ET.parse(f)
    root = tree.getroot()

# Check HatLoop (pad 3) - known warped sample
drum_rack = root.find('.//DrumGroupDevice')
branches = drum_rack.find('.//Branches')
branch_3 = list(branches)[3]
simpler = branch_3.find('.//OriginalSimpler')

if simpler:
    # Navigate to warp properties
    player = simpler.find('.//Player')
    if player:
        # Check multiple possible locations
        paths_to_check = [
            './/SampleWarpProperties/WarpMode',
            './/SampleWarpProperties/IsWarped',
            './/SampleRef/Warp/Mode/WarpOn',
            './/MultiSampleMap/SampleParts/MultiSamplePart/SampleRef/Warp/Mode/WarpOn'
        ]
        
        for path in paths_to_check:
            elem = simpler.find(path)
            if elem and 'Value' in elem.attrib:
                print(f'{path}: {elem.attrib[\"Value\"]}')
"
```

---

## Proposed Fixes

### Fix 1: Improve Warp Detection

**File**: `code/xml_read_v2.py`  
**Function**: `detect_warped_stem()` (lines 552-676)

**Change 1: Check WarpOn in SampleRef/Warp**
```python
# After checking SampleWarpProperties, also check SampleRef/Warp
sample_ref = find_element_by_tag(part, 'SampleRef')
if sample_ref:
    warp_container = find_element_by_tag(sample_ref, 'Warp')
    if warp_container:
        warp_mode_container = find_element_by_tag(warp_container, 'Mode')
        if warp_mode_container:
            warp_on = find_element_by_tag(warp_mode_container, 'WarpOn')
            if warp_on and 'Value' in warp_on.attrib:
                warp_on_val = warp_on.attrib['Value'].lower() == 'true'
                if warp_on_val:
                    result['is_warped'] = True
                    logger.debug(f'  detect_warped_stem: WarpOn = {warp_on_val}')
```

**Change 2: Add fallback for long samples**
```python
# If still not detected as warped, use heuristic:
# Samples longer than 4 bars (16 beats) are likely warped stems
if not result['is_warped'] and result['beat_count'] >= 16:
    logger.info(f'  detect_warped_stem: Long sample ({result["beat_count"]} beats), assuming warped')
    result['is_warped'] = True
```

### Fix 2: Verify MIDI Mode Detection

**File**: `code/xml_read_v2.py`  
**Function**: `make_drum_rack_sequences()` (lines 1623-1633)

**Verify these values for MIDI mode**:
```python
elif seq_mode == 'MIDI':
    seqstepmode_val = '0'  # MIDI mode (NOT step mode)
    seqpadmapdest_val = '0'  # No pad destination
    midioutchan_val = str(mode_target)  # MIDI channel (0-15)
```

---

## Test Plan

1. **Run conversion with verbose logging**
   ```bash
   python3 code/xml_read_v2.py -v -i "An mir Vorbei test unquantised.als" -o "test_output"
   ```

2. **Check warp detection output**
   - Look for "is warped" or "WarpOn" in logs
   - Verify HatLoop, percussion layers detected as warped
   - Verify Kick (pad 0) detected as warped

3. **Check preset.xml**
   - Warped samples >= 8 beats: `cellmode="1"`
   - Warped samples < 8 beats: `cellmode="0"`, `loopmode="1"`
   - Unwarped samples: `cellmode="0"`, `loopmode="0"`

4. **Check Track 1 (MIDI mode)**
   - `seqstepmode="0"`
   - `midioutchan="0"` (MIDI channel 1)
   - `seqpadmapdest="0"`

---

## Priority

1. **CRITICAL**: Fix warp detection (Issue #2)
2. **HIGH**: Verify MIDI mode parameters (Issue #1)

---

*User taking break - fixes prepared for implementation*  
*Last Updated: 2025-11-04*  
*Branch: experimental/keys-midi-mode*

