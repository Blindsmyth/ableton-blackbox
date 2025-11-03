# Ableton Live .als to 1010music Blackbox .xml Converter (v0.3)

> **Credits**: This project is based on the original work by **Maximilian Karlander** (pro424).  
> See [CREDITS.md](CREDITS.md) for full attribution details.

## 🎉 What's New in v0.3

**NOW WORKS WITH ABLETON LIVE 12!** 🚀

**NEW: DRUM RACK WORKFLOW!** 🥁

This version is **exclusively focused on the Drum Rack workflow**:
- ✅ **Drum Rack workflow only** - Clean, simple codebase
- ✅ **16-pad drum rack mapping** - 1:1 pad mapping  
- ✅ **Choke group support** - Extract choke groups from Drum Pads
- ✅ **Warped stem detection** - Auto-enable loop mode for stems
- ✅ **Multi-layer sequences** - Up to 4 sub-layers (A/B/C/D) per pad
- ✅ Full compatibility with Ableton Live 10, 11, and **12**
- ✅ Robust XML navigation (no more hardcoded indices)
- ✅ Comprehensive error handling and logging
- ✅ Python 3.7+ compatibility
- ✅ 300+ lines of legacy code removed for simplicity

**👉 See [DRUM_RACK_WORKFLOW.md](DRUM_RACK_WORKFLOW.md) for the complete workflow guide!**

**⚠️ IMPORTANT**: This script **requires** a Drum Rack in the first track. Legacy workflows are no longer supported.

## What This Script Does

This script converts an Ableton Live Drum Rack project to a 1010music Blackbox preset, with full support for:
- 16 drum pads → 16 Blackbox pads (1:1 mapping)
- Sample extraction from Simplers
- Choke groups
- Warped stems with loop mode
- Multi-layer MIDI sequences

## Requirements

Your Ableton project **must** be structured as follows:
- **Track 1**: Drum Rack with up to 16 Simplers (pads 0-15)
- **Tracks 2-17** (optional): MIDI tracks for sequences

If your project doesn't have a Drum Rack in track 1, the script will show a clear error message.

### Currently Extracts:

**From Simpler/Sampler:**
- Play start and end points
- ADSR envelope settings
- Multisample mappings with key ranges
- Root key information

**From MIDI Tracks:**
- Clip sequences from Simpler/Sampler tracks
- Clip sequences from Analog synth tracks
- Note data with timing and velocity
- Automatic division detection (1/16, 1/32, 1/64)

**From Audio Tracks:**
- Audio clips as loop pads
- Loop start/end points
- Beat count information

**Other:**
- Project tempo
- Sample file references
- Basic FX setup (Delay, Reverb, EQ)

### Limitations

- Simpler/Sampler must be standalone (not in groups)
- Samples must be in `.wav` format
- Sample rate is assumed to be 48kHz for audio clips
- Some advanced features may not transfer perfectly
- MIDI clips in Session View only (not Arrangement View clips yet)

## Installation

### Requirements
- Python 3.7 or higher (Python 3.9+ recommended)
- Ableton Live project file (`.als`)
- All samples must be `.wav` files

### Python Installation (macOS)

If you need to upgrade Python:

```bash
# Using Homebrew (recommended)
brew install python3

# Verify installation
python3 --version
```

## Usage

### Basic Usage

```bash
# Navigate to the script directory
cd "/path/to/ableton_blackbox/code"

# Convert an Ableton project
python3 xml_read_v2.py -i "/path/to/project.als" -o "/path/to/output_folder"
```

### Command Line Arguments

```bash
python3 xml_read_v2.py [options]

Required Arguments:
  -i, --Input PATH     Path to your Ableton Live .als file
  -o, --Output PATH    Path where the Blackbox project folder will be created

Optional Arguments:
  -m, --Manual         Skip automatic sample copying (useful if samples are missing)
  -v, --verbose        Show detailed debugging information
  -h, --help           Show help message
```

### Examples

#### Example 1: Full Conversion with Sample Copying
```bash
python3 xml_read_v2.py \
  -i "~/Music/Ableton/My Project.als" \
  -o "~/Desktop/BB_MyProject"
```
This will:
- Read your Ableton project
- Extract all settings
- Copy all referenced samples to the output folder
- Create a `preset.xml` file

#### Example 2: Manual Mode (Don't Copy Samples)
```bash
python3 xml_read_v2.py \
  -i "~/Music/Ableton/My Project.als" \
  -o "~/Desktop/BB_MyProject" \
  -m
```
Useful when:
- Sample file paths are incorrect
- You want to manually organize samples
- Samples are on a different computer

#### Example 3: Verbose Output for Debugging
```bash
python3 xml_read_v2.py \
  -i "~/Music/Ableton/My Project.als" \
  -o "~/Desktop/BB_MyProject" \
  -v
```
Shows detailed information about what's being extracted.

### Output Structure

After conversion, you'll have a folder like this:

```
BB_MyProject/
├── preset.xml              # Main Blackbox preset file
├── sample1.wav            # Copied samples
├── sample2.wav
└── multisample_folder/    # Multisample mappings
    ├── sample1_C3.wav
    ├── sample2_D3.wav
    └── sample3_E3.wav
```

### Transferring to Blackbox

1. Copy the entire output folder to your Blackbox SD card's `Presets` directory
2. On the Blackbox, navigate to the preset browser
3. Load your converted preset
4. All samples and settings should be in place!

## Understanding the Output

### What Gets Mapped

**Layer 0 (Pads):**
- Pad 1-16: Your Simpler/Sampler instruments
- Additional pads: Audio loop clips

**Layer 1 (Sequences):**
- Sequence 1-N: MIDI patterns from your clips
- Each sequence corresponds to a pad

**Layer 2 (Song Mode):**
- 16 empty sections (8 bars each)

**Layer 3 (FX):**
- FX1: Delay (default settings)
- FX2: Reverb (default settings)
- FX3: EQ (4-band, bypassed)

## Troubleshooting

### "Could not find tempo"
- The script will use 120 BPM as default
- Your project structure may be non-standard
- Enable verbose mode (`-v`) to see what's happening

### "Could not find tracks"
- Your `.als` file may be corrupted
- Try opening and re-saving in Ableton
- Check file permissions

### "Failed to read project file"
- Make sure the file is actually an `.als` file
- The file might be from a much older Ableton version
- Try decompressing manually: `gzip -cd project.als > project.xml`

### Samples Not Copying
- Use `-m` flag to skip sample copying
- Manually copy samples to the output folder
- Ensure samples are `.wav` format
- Check file paths and permissions

### Empty Preset on Blackbox
- Check that all samples are `.wav` format
- Verify sample file names don't have special characters
- Try using shorter file paths
- Check sample rate (48kHz is standard for Blackbox)

## Technical Details

### How It Works

1. **Decompress**: `.als` files are gzip-compressed XML
2. **Parse**: Extract project structure using XML ElementTree
3. **Navigate**: Use tag-based navigation to find relevant elements
4. **Extract**: Pull out tempo, tracks, devices, clips, samples
5. **Convert**: Map Ableton parameters to Blackbox equivalents
6. **Generate**: Create Blackbox-compatible XML structure
7. **Copy**: Transfer referenced samples to output folder

### Parameter Conversions

Some parameters need mathematical conversion:

```python
# Attack time (ms to Blackbox units)
bb_attack = 109.83 * log(ableton_attack)

# Decay/Release time
bb_decay = 94.83 * log(ableton_decay)

# Sustain level (0-1 to dB)
bb_sustain = 8.69 * log(ableton_sustain) dB
```

These coefficients may need tweaking based on your perception!

### Ableton Version Differences

| Element | Live 10/11 | Live 12 |
|---------|-----------|---------|
| Master Track | `MasterTrack` | `MainTrack` |
| Tempo Path | `MasterTrack/DeviceChain/Mixer/Tempo/Manual` | `MainTrack/DeviceChain/Mixer/Tempo/Manual` |
| File Format | Same core structure | Enhanced with new features |

## Comparison: v0.2 vs v0.3

### v0.2 (Original)
- ❌ Hardcoded array indices (`root[0][i][19][7]`)
- ❌ Breaks with Live 12 file format changes
- ❌ Limited error messages
- ❌ Crashes on unexpected structure
- ❌ Python 3.9+ required

### v0.3 (Enhanced)
- ✅ Tag-based XML navigation
- ✅ Works with Live 10, 11, and 12
- ✅ Detailed error messages and logging
- ✅ Graceful degradation on errors
- ✅ Python 3.7+ compatible

## Development

### File Structure
```
ableton_blackbox/
├── code/
│   ├── xml_read.py       # Original v0.2 script
│   └── xml_read_v2.py    # Enhanced v0.3 script
├── data/                 # Output and test data
├── README.md            # Original documentation
├── README_v2.md         # This file
└── CHANGELOG.md         # Version history
```

### Testing

Test with your own projects:

```bash
# Test with manual mode first
python3 xml_read_v2.py -i "path/to/test.als" -o "test_output" -m -v

# Check the output
cat test_output/preset.xml | head -50
```

### Contributing

Ideas for improvement:
- Better Simpler/Sampler parameter extraction
- Support for grouped instruments
- Extract send/return effect settings
- GUI version
- Batch conversion
- Preset templates

## Credits

- **Original Author**: Maximilian Karlander (pro424 on 1010music forum)
- **Enhanced Version**: Community contribution for Live 12 compatibility
- **Forum Thread**: [1010music Forum](https://forum.1010music.com/forum/products/blackbox/support-blackbox/43727-python-script-converting-an-ableton-live-project-to-blackbox-xml)

## License

This is community-developed software. Use at your own risk. No warranty provided.

## Support

For questions or issues:
1. Check the troubleshooting section above
2. Enable verbose mode (`-v`) for debugging
3. Post on the 1010music forum thread
4. Share your `.als` file structure (use `-m` flag and check logs)

## Credits & Attribution

This project builds upon the original work by **Maximilian Karlander** (pro424), who reverse-engineered the Blackbox XML format and created the initial converter.

- **Original Author**: Maximilian Karlander (pro424)
- **Original Forum Thread**: https://forum.1010music.com/forum/products/blackbox/support-blackbox/43727-python-script-converting-an-ableton-live-project-to-blackbox-xml
- **Enhancements** (v0.3): Simon (2024-2025) - Ableton 12 compatibility, Drum Rack workflow, unquantised MIDI

For full details, see [CREDITS.md](CREDITS.md).

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

---

**Happy music making! 🎵**

