# Drum Rack Workflow Guide

## Overview

The enhanced `xml_read.py` script now supports a **Drum Rack workflow** specifically designed for converting Ableton projects with a Drum Rack containing 16 Simplers to a Blackbox preset.

## What's New

### Dual Workflow Support

The script automatically detects which workflow to use:

1. **Drum Rack Workflow** (NEW):
   - Detects if the first track contains a DrumGroupDevice
   - Maps 16 Drum Rack pads → 16 Blackbox pads (1:1 mapping)
   - Extracts samples from Simplers within each Drum Pad
   - Supports choke groups from Drum Rack pad settings
   - Detects warped stems and enables loop mode automatically
   - Extracts up to 4 MIDI clips per track as sub-layers (A/B/C/D)

2. **Legacy Workflow**:
   - Used when no Drum Rack is detected
   - Original behavior: Simpler/Sampler tracks → Sequential pad mapping
   - Audio clips → Sequential pad mapping

## Project Setup

### Recommended Structure

```
Track 1: MIDI Track with Drum Rack
  ├─ Drum Pad 0 (MIDI Note 36): Simpler with sample
  ├─ Drum Pad 1 (MIDI Note 37): Simpler with sample
  ├─ ...
  └─ Drum Pad 15 (MIDI Note 51): Simpler with sample

Track 2-17: MIDI Tracks (for sequences)
  ├─ Clip Slot 0: MIDI Clip for sub-layer A
  ├─ Clip Slot 1: MIDI Clip for sub-layer B
  ├─ Clip Slot 2: MIDI Clip for sub-layer C
  └─ Clip Slot 3: MIDI Clip for sub-layer D
```

### Pad Mapping

| Drum Rack Pad | Blackbox Pad | Default MIDI Note |
|---------------|--------------|-------------------|
| 0             | 0 (Row 0, Col 0) | 36 (C1) |
| 1             | 1 (Row 0, Col 1) | 37 (C#1) |
| 2             | 2 (Row 0, Col 2) | 38 (D1) |
| 3             | 3 (Row 0, Col 3) | 39 (D#1) |
| 4             | 4 (Row 1, Col 0) | 40 (E1) |
| 5             | 5 (Row 1, Col 1) | 41 (F1) |
| ...           | ...          | ... |
| 15            | 15 (Row 3, Col 3) | 51 (D#2) |

## Features

### 1. Sample Extraction
- Automatically extracts samples from Simplers in each Drum Pad
- Supports multisample mode
- Preserves ADSR envelope settings
- Copies samples to output directory (unless `-m` flag is used)

### 2. Choke Groups
- Extracts choke group settings from each Drum Pad
- Maps to Blackbox `chokegrp` parameter
- Enables hi-hat choke behavior, etc.

### 3. Warped Stem Detection
- Detects if a Simpler contains a warped audio sample
- Automatically enables loop mode for stems
- Useful for song arrangements with long loops (e.g., 64-bar stems)

### 4. MIDI Sequence Sub-Layers
- Extracts up to 4 MIDI clips per track
- Maps to Blackbox sequence sub-layers A/B/C/D
- Each sub-layer can have different patterns
- Enables complex, layered sequences

## Usage

### Basic Conversion

```bash
python3 code/xml_read.py -i "My Project.als" -o "output_folder"
```

### With Verbose Logging

```bash
python3 code/xml_read.py -i "My Project.als" -o "output_folder" -v
```

### Manual Sample Management

Use the `-m` flag to prevent automatic sample copying:

```bash
python3 code/xml_read.py -i "My Project.als" -o "output_folder" -m
```

This is useful if your samples are already organized or in a different location.

## Example: Converting Template.als

```bash
cd "/Users/simon/Dropbox/Blackbox Stuff/ableton_blackbox"
python3 code/xml_read.py \
  -i "../Ableton Files/Test Project/Template.als" \
  -o "output_drum_rack" \
  -v
```

**Expected Output:**
```
INFO: === Ableton to Blackbox Converter v0.3 (Drum Rack Edition) ===
INFO: Reading Ableton project...
INFO: DRUM RACK DETECTED - Using Drum Rack workflow
INFO: Extracted 16 drum pads and 16 MIDI tracks
INFO: Created 16 drum rack pads
INFO: === Conversion complete! ===
```

## Workflow Comparison

### Drum Rack Workflow vs. Legacy Workflow

| Feature | Drum Rack Workflow | Legacy Workflow |
|---------|-------------------|-----------------|
| Detection | DrumGroupDevice in Track 1 | No DrumGroupDevice |
| Pad Mapping | 1:1 (Drum Pad → Blackbox Pad) | Sequential |
| Choke Groups | Yes ✓ | No |
| Warped Stems | Auto-detected ✓ | Manual |
| Sequence Sub-layers | Yes (A/B/C/D) ✓ | No |
| MIDI Tracks | Dedicated (Tracks 2-17) | Mixed with instruments |

## Implementation Details

### Functions Added

1. **`drum_rack_extract(drum_rack_device)`**
   - Parses DrumGroupDevice
   - Extracts 16 Drum Pads with Simplers, MIDI notes, and choke groups
   - Returns list of pad info dictionaries

2. **`detect_warped_stem(device)`**
   - Checks if a Simpler contains warped audio
   - Extracts beat count and loop length
   - Returns dict with warp information

3. **`make_drum_rack_pads(session, pad_list, tempo)`**
   - Creates Blackbox cell elements for each pad
   - Sets loop mode for warped stems
   - Applies choke groups
   - Returns session element and asset list

4. **`make_drum_rack_sequences(session, midi_tracks, pad_list)`**
   - Extracts MIDI clips from tracks
   - Creates sequence elements with sub-layers
   - Maps notes to correct pads
   - Returns session element

5. **`track_iterator(tracks)` (updated)**
   - Detects DrumGroupDevice in first track
   - Routes to appropriate workflow
   - Returns data for both workflows

## Tips and Best Practices

### 1. Setting Up Your Drum Rack

- Use **16 pads** for full Blackbox compatibility
- Assign one Simpler per pad
- Set choke groups for hi-hats and cymbals
- Keep MIDI notes sequential (36-51)

### 2. Working with Stems

- Warp your stems to the project tempo
- The script will auto-enable loop mode
- Beat count detection is approximate - may need manual adjustment

### 3. Creating Sequences

- Use separate MIDI tracks for each pad's sequence
- Place up to 4 clips in the first 4 clip slots for sub-layers
- Each clip should trigger the corresponding Drum Pad note

### 4. Choke Groups

- Set choke groups in Drum Rack pad settings
- Common use: Group closed/open hi-hats together
- Blackbox supports 16 choke groups (0-15)

## Known Limitations

1. **MIDI Note Detection**: In some cases, MIDI notes may not be extracted correctly. Ensure Drum Pads have proper MIDI note assignments.

2. **Beat Count for Warped Stems**: The script attempts to detect loop lengths, but this may not always be accurate. You might need to manually adjust the `beatcount` parameter in the XML.

3. **Sequence Timing**: MIDI timing conversion assumes 16th note resolution. Complex polyrhythms may not translate perfectly.

4. **Sample Paths**: Samples must be accessible at their original paths for copying to work.

## Troubleshooting

### Issue: "MIDI note None" for all pads

**Cause**: Drum Pads may not have MIDI note assignments yet.

**Solution**: In Ableton, click on each Drum Pad and verify the "Receive" note is set.

### Issue: Samples not copying

**Cause**: Sample paths in Ableton project may be broken or inaccessible.

**Solution**: 
1. Check sample paths in the verbose output
2. Use `-m` flag and manually copy samples
3. Ensure samples exist at the specified paths

### Issue: No sequences generated

**Cause**: MIDI clips may not contain notes for the correct MIDI notes.

**Solution**:
1. Verify MIDI clips are triggering the Drum Rack pads (notes 36-51)
2. Check that clips are in the first 4 clip slots
3. Use verbose mode (`-v`) to see what's being extracted

## Next Steps

1. **Test with Real Projects**: Convert your Ableton projects and test on Blackbox hardware
2. **Refine Beat Count Detection**: For warped stems, you may need to manually adjust loop lengths
3. **Experiment with Sub-Layers**: Create complex patterns using multiple MIDI clips per pad
4. **Report Issues**: If you encounter problems, check the verbose logs and report specific errors

## Files Modified

- `code/xml_read.py`: Main script with drum rack support
- All changes are backward compatible with the legacy workflow

## Version

**Current Version**: 0.3 (Drum Rack Edition)

**Date**: November 2, 2025

**Python Compatibility**: 3.7+

---

For more information, see:
- `README_v2.md` - General usage and setup
- `QUICKSTART.md` - Getting started guide
- `CHANGELOG.md` - Version history

