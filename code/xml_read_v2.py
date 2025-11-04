#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ableton Live Drum Rack to 1010music Blackbox converter
Version 0.3 - Drum Rack Workflow

Converts Ableton Live projects with Drum Racks to Blackbox presets.

Based on the original work by Maximilian Karlander (pro424)
Original: https://forum.1010music.com/forum/products/blackbox/support-blackbox/43727-python-script-converting-an-ableton-live-project-to-blackbox-xml

Requirements:
- Track 1: Drum Rack with up to 16 Simplers
- Tracks 2-17: MIDI tracks for sequences (optional)

Features:
- 16-pad drum rack mapping
- Choke group support
- Warped stem detection
- Multi-layer sequences (A/B/C/D)
- Unquantised MIDI timing support
- Compatible with Ableton Live 10, 11, and 12

CREDITS:
- Original author: Maximilian Karlander (pro424) - Blackbox XML format reverse-engineering
- Enhanced by: Simon Schmidt (2024-2025) - Ableton 12 compatibility, Drum Rack workflow
"""
import argparse
from argparse import RawTextHelpFormatter
import xml.etree.ElementTree as ET
import math
import gzip
import os
import shutil
import logging
import sys
import struct

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def get_wav_info(filepath):
    """
    Read WAV file header and return sample information.
    Returns dict with {'sample_length_samples': int, 'sample_rate': int, 'duration_seconds': float}
    Returns None if file doesn't exist or isn't a valid WAV.
    """
    try:
        if not os.path.exists(filepath):
            return None
            
        with open(filepath, 'rb') as f:
            # Read RIFF header
            riff = f.read(4)
            if riff != b'RIFF':
                return None
            
            # Skip file size (4 bytes)
            f.read(4)
            
            # Check for WAVE format
            wave = f.read(4)
            if wave != b'WAVE':
                return None
            
            # Find fmt chunk
            while True:
                chunk_id = f.read(4)
                if not chunk_id:
                    return None
                    
                chunk_size = struct.unpack('<I', f.read(4))[0]
                
                if chunk_id == b'fmt ':
                    # Read fmt chunk
                    audio_format = struct.unpack('<H', f.read(2))[0]  # 1 = PCM
                    num_channels = struct.unpack('<H', f.read(2))[0]
                    sample_rate = struct.unpack('<I', f.read(4))[0]
                    byte_rate = struct.unpack('<I', f.read(4))[0]
                    block_align = struct.unpack('<H', f.read(2))[0]
                    bits_per_sample = struct.unpack('<H', f.read(2))[0]
                    
                    # Skip rest of fmt chunk
                    if chunk_size > 16:
                        f.read(chunk_size - 16)
                    
                    # Find data chunk
                    while True:
                        data_chunk_id = f.read(4)
                        if not data_chunk_id:
                            return None
                        data_chunk_size = struct.unpack('<I', f.read(4))[0]
                        
                        if data_chunk_id == b'data':
                            # Calculate sample length
                            bytes_per_sample = bits_per_sample // 8
                            total_samples = data_chunk_size // (num_channels * bytes_per_sample)
                            duration_seconds = total_samples / sample_rate
                            
                            return {
                                'sample_length_samples': total_samples,
                                'sample_rate': sample_rate,
                                'duration_seconds': duration_seconds,
                                'num_channels': num_channels,
                                'bits_per_sample': bits_per_sample
                            }
                        else:
                            # Skip this chunk
                            f.read(data_chunk_size)
                else:
                    # Skip this chunk
                    f.read(chunk_size)
                    
    except Exception as e:
        logger.debug(f"Error reading WAV file {filepath}: {e}")
        return None


def read_project(file):
    """Read and parse an Ableton Live .als file (handles both gzipped and plain XML)."""
    try:
        # Try to open as gzipped file first
        file_content = gzip.open(file, 'rb')
        tree = ET.parse(file_content)
        root = tree.getroot()
        
        # Log Ableton version info
        version_info = root.attrib
        logger.info(f"Ableton version: {version_info.get('Creator', 'Unknown')}")
        logger.info(f"Major version: {version_info.get('MajorVersion', 'Unknown')}")
        logger.info(f"Minor version: {version_info.get('MinorVersion', 'Unknown')}")
        
        return root
    except OSError as e:
        # If not gzipped, try as regular XML
        if 'Not a gzipped file' in str(e):
            logger.info('File is not gzipped, reading as plain XML')
            tree = ET.parse(file)
            root = tree.getroot()
            
            # Log Ableton version info
            version_info = root.attrib
            logger.info(f"Ableton version: {version_info.get('Creator', 'Unknown')}")
            logger.info(f"Major version: {version_info.get('MajorVersion', 'Unknown')}")
            logger.info(f"Minor version: {version_info.get('MinorVersion', 'Unknown')}")
            
            return root
        else:
            raise
    except Exception as e:
        logger.error(f"Failed to read project file: {e}")
        raise


def find_element_by_tag(parent, tag):
    """Find first child element with given tag."""
    for child in parent:
        if child.tag == tag:
            return child
    return None


def detect_sequence_mode(midi_track):
    """
    Detect the sequence mode for a MIDI track based on its routing.
    
    Returns:
        tuple: (mode, target)
        - mode: 'Keys', 'MIDI', or 'Pads'
        - target: For Keys mode: chain index (int), For MIDI mode: channel (int), For Pads mode: None
    
    Routing patterns:
        - Keys Mode: MidiOut/Track.XX/DeviceIn.Y.Z (routed to specific drum rack pad)
        - MIDI Mode: MidiOut/External.Dev:DeviceName/Channel (routed to external MIDI)
        - Pads Mode: MidiOut/Track.XX/TrackIn or MidiOut/None (routed to entire drum rack)
    """
    try:
        # Find MidiOutputRouting/Target element (search recursively)
        midi_output_routing = midi_track.find('.//MidiOutputRouting')
        if midi_output_routing is None:
            logger.debug('  No MidiOutputRouting found, defaulting to Pads mode')
            return 'Pads', None
        
        target_elem = find_element_by_tag(midi_output_routing, 'Target')
        if target_elem is None or 'Value' not in target_elem.attrib:
            logger.debug('  No routing Target found, defaulting to Pads mode')
            return 'Pads', None
        
        target = target_elem.attrib['Value']
        logger.debug(f'  Routing target: {target}')
        
        # Check for Keys mode: MidiOut/Track.XX/DeviceIn.Y.Z
        if '/DeviceIn.' in target:
            # Extract chain index from DeviceIn.Y.Z format
            device_part = target.split('/DeviceIn.')[-1]
            chain_index = int(device_part.split('.')[0])
            logger.info(f'  Detected Keys mode → Pad {chain_index}')
            return 'Keys', chain_index
        
        # Check for MIDI mode: MidiOut/External.Dev:
        if '/External.Dev:' in target or '/External/' in target:
            # Extract MIDI channel if present (usually ends with /Channel)
            channel = 0  # Default to channel 0 (Ch1)
            if '/' in target:
                parts = target.split('/')
                if parts[-1].isdigit():
                    channel = int(parts[-1])
            logger.info(f'  Detected MIDI mode → Channel {channel}')
            return 'MIDI', channel
        
        # Default to Pads mode (TrackIn or None)
        logger.debug('  Defaulting to Pads mode')
        return 'Pads', None
        
    except Exception as e:
        logger.warning(f'  Error detecting sequence mode: {e}, defaulting to Pads mode')
        return 'Pads', None


def find_tempo(root):
    """
    Find tempo in the project using tag-based navigation.
    Works with both Ableton 10 (MasterTrack) and 12 (MainTrack).
    """
    try:
        liveset = root[0]
        
        # Try MainTrack first (Live 12+)
        maintrack = find_element_by_tag(liveset, 'MainTrack')
        
        # Fall back to MasterTrack (Live 10/11)
        if maintrack is None:
            maintrack = find_element_by_tag(liveset, 'MasterTrack')
        
        if maintrack is None:
            logger.warning("Could not find MainTrack or MasterTrack")
            return '120'  # Default tempo
        
        # Navigate: MainTrack -> DeviceChain -> Mixer -> Tempo -> Manual
        device_chain = find_element_by_tag(maintrack, 'DeviceChain')
        if device_chain is None:
            logger.warning("Could not find DeviceChain")
            return '120'
        
        mixer = find_element_by_tag(device_chain, 'Mixer')
        if mixer is None:
            logger.warning("Could not find Mixer")
            return '120'
        
        tempo_elem = find_element_by_tag(mixer, 'Tempo')
        if tempo_elem is None:
            logger.warning("Could not find Tempo element")
            return '120'
        
        manual = find_element_by_tag(tempo_elem, 'Manual')
        if manual is None or 'Value' not in manual.attrib:
            logger.warning("Could not find Manual tempo value")
            return '120'
        
        tempo = manual.attrib['Value']
        logger.info(f"Found tempo: {tempo} BPM")
        return tempo
        
    except Exception as e:
        logger.warning(f"Error finding tempo: {e}. Using default 120 BPM")
        return '120'


def find_tracks(root):
    """Find the Tracks element in the project."""
    try:
        liveset = root[0]
        tracks = find_element_by_tag(liveset, 'Tracks')
        
        if tracks is None:
            logger.error("Could not find Tracks element")
            return None
        
        logger.info(f"Found {len(tracks)} tracks")
        return tracks
        
    except Exception as e:
        logger.error(f"Error finding tracks: {e}")
        return None


def track_tempo_extractor(root):
    """Extract tracks and tempo from the project."""
    tracks = find_tracks(root)
    tempo = find_tempo(root)
    
    if tracks is None:
        raise ValueError("Could not extract tracks from project")
    
    return tracks, tempo


def device_extract(track, track_count):
    """Extract device information from a track."""
    device_dict = {}
    logger.info(f'Track {track_count}, track type: {track.tag}')
    
    try:
        device_chain = find_element_by_tag(track, 'DeviceChain')
        if device_chain is None:
            return device_dict, track.tag
        
        # Find the nested DeviceChain
        nested_chain = find_element_by_tag(device_chain, 'DeviceChain')
        if nested_chain is None:
            return device_dict, track.tag
        
        # Find Devices element
        devices_elem = find_element_by_tag(nested_chain, 'Devices')
        if devices_elem is None:
            return device_dict, track.tag
        
        # Extract individual devices
        count = 1
        for device in devices_elem:
            logger.info(f'  Device {count}: {device.tag}')
            count += 1
            device_dict[device.tag] = device
            
    except Exception as e:
        logger.warning(f"Error extracting devices from track {track_count}: {e}")
    
    return device_dict, track.tag


def safe_navigate(element, path_description, *indices_or_tags):
    """
    Safely navigate XML tree using indices or tags.
    Returns None if path doesn't exist.
    
    Args:
        element: Starting element
        path_description: Description for error messages
        *indices_or_tags: Mix of integer indices or string tag names
    """
    current = element
    path = []
    
    try:
        for item in indices_or_tags:
            if isinstance(item, int):
                if len(current) <= item:
                    logger.warning(f"Path {path_description}: Index {item} out of range (length {len(current)})")
                    return None
                current = current[item]
                path.append(f"[{item}]")
            elif isinstance(item, str):
                found = find_element_by_tag(current, item)
                if found is None:
                    logger.warning(f"Path {path_description}: Tag '{item}' not found")
                    return None
                current = found
                path.append(f"<{item}>")
        return current
    except Exception as e:
        logger.warning(f"Error navigating {path_description} at {''.join(path)}: {e}")
        return None


def drum_rack_extract(drum_rack_device):
    """
    Extract all Simplers from a DrumGroupDevice.
    Returns a list of pad info: [{'blackbox_pad': 0-15, 'simpler': device, 'midi_note': 36-51, 'choke_group': 0-16, 'name': '...'}, ...]
    """
    pad_list = []
    
    try:
        # Find Branches element
        branches = find_element_by_tag(drum_rack_device, 'Branches')
        if not branches:
            logger.warning("DrumGroupDevice has no Branches element")
            return pad_list
        
        # Extract pads from branches
        # Map branch/chain index to Blackbox pad
        # Default: Use chain order as pad order (Branch 0 = Pad 0, etc.)
        for branch_index in range(min(len(branches), 16)):
            branch = branches[branch_index]
            
            pad_info = {
                'blackbox_pad': branch_index,  # Use chain index as pad index by default
                'simpler': None,
                'midi_note': None,
                'choke_group': 0,
                'name': '',
                'is_empty': True
            }
            
            # Extract BranchInfo for MIDI note and choke group
            branch_info = find_element_by_tag(branch, 'BranchInfo')
            if branch_info:
                receiving_note = find_element_by_tag(branch_info, 'ReceivingNote')
                if receiving_note and 'Value' in receiving_note.attrib:
                    midi_note = int(receiving_note.attrib['Value'])
                    pad_info['midi_note'] = midi_note
                
                choke_group = find_element_by_tag(branch_info, 'ChokeGroup')
                logger.debug(f'  Branch {branch_index}: ChokeGroup element found: {choke_group is not None}')
                if choke_group is not None:
                    logger.debug(f'    ChokeGroup attribs: {choke_group.attrib}')
                    if 'Value' in choke_group.attrib:
                        # Ableton choke group mapping to Blackbox excl groups:
                        # Ableton 0 or -1 (no choke) → Blackbox 0 (excl group X)
                        # Ableton 1-4 → Blackbox 1-4 (excl groups A-D)
                        ableton_choke = int(choke_group.attrib['Value'])
                        logger.debug(f'    Ableton choke value: {ableton_choke}')
                        if ableton_choke <= 0:
                            pad_info['choke_group'] = 0  # No choke / excl group X
                        elif ableton_choke >= 1 and ableton_choke <= 4:
                            pad_info['choke_group'] = ableton_choke  # Direct mapping for groups 1-4 (A-D)
                            logger.debug(f'    → Mapped to Blackbox choke group: {ableton_choke}')
                        else:
                            # If Ableton has choke groups > 4, cap at 4 (excl group D)
                            pad_info['choke_group'] = min(ableton_choke, 4)
                            logger.debug(f'    → Capped to Blackbox choke group: {pad_info["choke_group"]}')
                    else:
                        logger.debug(f'    ChokeGroup has no Value attribute')
                else:
                    logger.debug(f'  Branch {branch_index}: No ChokeGroup element found in BranchInfo')
            
            # Extract Name
            name_elem = find_element_by_tag(branch, 'Name')
            if name_elem and 'Value' in name_elem.attrib:
                pad_info['name'] = name_elem.attrib['Value']
            
            # Extract Simpler device from DeviceChain
            dev_chain = find_element_by_tag(branch, 'DeviceChain')
            if dev_chain:
                # Check for MidiToAudioDeviceChain (Ableton 12.3+)
                midi_to_audio = find_element_by_tag(dev_chain, 'MidiToAudioDeviceChain')
                if midi_to_audio:
                    devices_elem = find_element_by_tag(midi_to_audio, 'Devices')
                else:
                    # Fallback to direct Devices (older structure)
                    devices_elem = find_element_by_tag(dev_chain, 'Devices')
                
                if devices_elem:
                    simpler = find_element_by_tag(devices_elem, 'OriginalSimpler')
                    if simpler:
                        pad_info['simpler'] = simpler
                        pad_info['is_empty'] = False
            
            # Only add pads that have a valid pad number
            if pad_info['blackbox_pad'] is not None:
                pad_list.append(pad_info)
                
                # Log pad mapping
                choke_label = {0: 'X (none)', 1: 'A', 2: 'B', 3: 'C', 4: 'D'}.get(pad_info["choke_group"], str(pad_info["choke_group"]))
                logger.info(f'  Chain {branch_index} → Pad {pad_info["blackbox_pad"]}: MIDI {pad_info["midi_note"]}, Choke: {choke_label}, Has Simpler: {not pad_info["is_empty"]}')
            else:
                logger.debug(f'  Chain {branch_index}: Skipped (no valid pad number)')
        
        # Keep pads in chain order (don't sort - preserve the order they appear in Ableton)
        # This ensures the visual layout matches what the user sees in Ableton
        
        logger.info(f'Extracted {len(pad_list)} drum rack pads')
        return pad_list
        
    except Exception as e:
        logger.error(f"Error extracting drum rack: {e}")
        import traceback
        traceback.print_exc()
        return pad_list


def detect_warped_stem(device):
    """
    Detect if a Simpler contains a warped stem sample.
    Returns dict with {'is_warped': bool, 'beat_count': int, 'loop_length_bars': float, 'trigger_mode': str}
    """
    result = {
        'is_warped': False,
        'beat_count': 0,
        'loop_length_bars': 0.0,
        'trigger_mode': 'gate'  # default
    }
    
    logger.debug('detect_warped_stem: Starting detection')
    try:
        # Extract trigger mode from Simpler (1-shot vs classic)
        # TriggerMode: 0=Gate, 1=Trigger(1-shot), 2=Toggle
        player = find_element_by_tag(device, 'Player')
        if player:
            trigger_mode_elem = find_element_by_tag(player, 'TriggerMode')
            if trigger_mode_elem and 'Value' in trigger_mode_elem.attrib:
                trigger_val = int(trigger_mode_elem.attrib['Value'])
                if trigger_val == 0:
                    result['trigger_mode'] = 'gate'
                elif trigger_val == 1:
                    result['trigger_mode'] = 'trigger'
                elif trigger_val == 2:
                    result['trigger_mode'] = 'toggle'
        
            # Check for warp properties in the sample
            player = safe_navigate(device, "Player", 19)
            if not player:
                player = find_element_by_tag(device, 'Player')
            if not player:
                logger.debug('  detect_warped_stem: No Player found')
                return result
            
            multi_sample_map = find_element_by_tag(player, 'MultiSampleMap')
            if not multi_sample_map:
                logger.debug('  detect_warped_stem: No MultiSampleMap found')
                return result
            
            sample_parts = find_element_by_tag(multi_sample_map, 'SampleParts')
            if not sample_parts or len(sample_parts) == 0:
                logger.debug('  detect_warped_stem: No SampleParts found')
                return result
            
            part = sample_parts[0]
            logger.debug(f'  detect_warped_stem: Found SamplePart')
            
            # Check for SampleWarpProperties
            warp_props = find_element_by_tag(part, 'SampleWarpProperties')
            if warp_props:
                logger.debug('  detect_warped_stem: Found SampleWarpProperties!')
                
                # Check both WarpMode and IsWarped flag
                warp_mode = find_element_by_tag(warp_props, 'WarpMode')
                is_warped_elem = find_element_by_tag(warp_props, 'IsWarped')
                
                warp_mode_val = 0
                is_warped_val = False
                
                if warp_mode and 'Value' in warp_mode.attrib:
                    warp_mode_val = int(warp_mode.attrib['Value'])
                    logger.debug(f'  detect_warped_stem: WarpMode value = {warp_mode_val}')
                
                if is_warped_elem and 'Value' in is_warped_elem.attrib:
                    is_warped_val = is_warped_elem.attrib['Value'].lower() == 'true'
                    logger.debug(f'  detect_warped_stem: IsWarped value = {is_warped_val}')
                
                # Try to extract loop length from LoopLength element
                # First check in SampleWarpProperties
                loop_length_elem = find_element_by_tag(warp_props, 'LoopLength')
                if not loop_length_elem:
                    # Try in part level
                    loop_length_elem = find_element_by_tag(part, 'LoopLength')
                
                if loop_length_elem and 'Value' in loop_length_elem.attrib:
                    loop_length_beats = float(loop_length_elem.attrib['Value'])
                    result['loop_length_bars'] = loop_length_beats / 4.0
                    result['beat_count'] = int(loop_length_beats)
                    logger.debug(f'  detect_warped_stem: Found LoopLength: {loop_length_beats} beats')
                
                # Always extract sample duration from SampleRef (for beat calculation)
                sample_ref = find_element_by_tag(part, 'SampleRef')
                logger.debug(f'  detect_warped_stem: Looking for SampleRef... found: {sample_ref is not None}')
                if sample_ref:
                    default_duration_elem = find_element_by_tag(sample_ref, 'DefaultDuration')
                    default_sample_rate_elem = find_element_by_tag(sample_ref, 'DefaultSampleRate')
                    logger.debug(f'  detect_warped_stem: DefaultDuration: {default_duration_elem is not None}, DefaultSampleRate: {default_sample_rate_elem is not None}')
                    logger.debug(f'  detect_warped_stem: Bool test - dur: {bool(default_duration_elem)}, rate: {bool(default_sample_rate_elem)}, and: {bool(default_duration_elem and default_sample_rate_elem)}')
                    
                    if default_duration_elem is not None and default_sample_rate_elem is not None:
                        logger.debug(f'  detect_warped_stem: About to extract duration values...')
                        try:
                            dur_val = default_duration_elem.attrib.get('Value')
                            rate_val = default_sample_rate_elem.attrib.get('Value')
                            logger.debug(f'  detect_warped_stem: Raw values - Duration: {dur_val}, SampleRate: {rate_val}')
                            
                            duration_samples = float(dur_val) if dur_val else 0
                            sample_rate = float(rate_val) if rate_val else 48000
                            logger.debug(f'  detect_warped_stem: Extracted values: {duration_samples} samples @ {sample_rate}Hz')
                            
                            if duration_samples > 0 and sample_rate > 0:
                                duration_seconds = duration_samples / sample_rate
                                result['sample_duration_seconds'] = duration_seconds
                                logger.info(f'  ✓ Sample duration: {duration_seconds:.2f}s = {duration_samples} samples @ {sample_rate}Hz')
                        except (ValueError, TypeError) as e:
                            logger.warning(f'  detect_warped_stem: Error extracting duration: {e}')
                
                # Sample is warped if WarpMode > 0 OR IsWarped = true
                if warp_mode_val > 0 or is_warped_val:
                    result['is_warped'] = True
                    logger.debug(f'  detect_warped_stem: Sample is warped (mode={warp_mode_val})')
            else:
                logger.debug('  detect_warped_stem: No SampleWarpProperties found')
        
        # If we can't determine from warp properties, check if it's a long sample
        # (stems are typically longer than one-shots)
        # This is a heuristic fallback
        
        return result
        
    except Exception as e:
        logger.warning(f"Error detecting warped stem: {e}")
        return result


def sampler_extract(device):
    """Extract sampler/simpler parameters with robust error handling."""
    params = {}
    
    try:
        # Live 12.2+ structure: Use tag-based navigation for Player element
        # Try Live 12.2+ path first (works for 12.2, 12.3+)
        player = find_element_by_tag(device, 'Player')
        sample_map = None
        
        if player:
            multi_sample_map = find_element_by_tag(player, 'MultiSampleMap')
            if multi_sample_map:
                sample_parts = find_element_by_tag(multi_sample_map, 'SampleParts')
                if sample_parts and len(sample_parts) > 0:
                    # In Live 12.2+, SampleParts contains MultiSamplePart elements
                    # We'll iterate through SampleParts (which is the container)
                    sample_map = sample_parts
                    logger.info("  Found Live 12.2+ structure")
        
        # Fallback to older Live 10/11 structure
        if sample_map is None:
            sample_map = safe_navigate(device, "MultiSampleMap", 15, 0, 0)
            if sample_map:
                logger.info("  Found Live 10/11 structure")
        
        if sample_map is None:
            logger.warning("Could not find sample map in device")
            return None
        
        # Extract multisample parts
        sample_names = []
        filepaths = []
        rootkeys = []
        keyrangemins = []
        keyrangemaxs = []
        
        # Check if this is Live 12.2+ structure (SampleParts contains MultiSamplePart)
        if sample_map.tag == 'SampleParts':
            # Live 12.2+ structure - iterate through all children
            for i in range(len(sample_map)):
                part = sample_map[i]
                
                # Skip if not a MultiSamplePart
                if part.tag != 'MultiSamplePart':
                    continue
                
                # Find SampleRef in this part using tag-based search
                sample_ref = None
                for child in part:
                    if child.tag == 'SampleRef':
                        sample_ref = child
                        logger.info(f'  Found SampleRef in MultiSamplePart[{i}]')
                        break
                
                if sample_ref is None:
                    logger.warning(f'  No SampleRef found in MultiSamplePart[{i}]')
                    continue
                
                # Live 12.2+ uses FileRef with Path element
                file_ref = None
                for child in sample_ref:
                    if child.tag == 'FileRef':
                        file_ref = child
                        logger.info(f'  Found FileRef')
                        break
                
                if file_ref:
                    # Look for Path element using tag-based search (prefer absolute Path over RelativePath)
                    path_elem = None
                    rel_path_elem = None
                    for child in file_ref:
                        if child.tag == 'Path':
                            if 'Value' in child.attrib:
                                path_elem = child
                                logger.info(f'  Found Path element')
                        elif child.tag == 'RelativePath':
                            if 'Value' in child.attrib:
                                rel_path_elem = child
                                logger.info(f'  Found RelativePath element')
                    
                    if path_elem is not None:
                        logger.info(f'  Entering path_elem block')
                        try:
                            full_path = path_elem.attrib['Value']
                            logger.info(f'  Got path value: {full_path[:50]}...')
                            filepaths.append(full_path)
                            sample_name = full_path.split('/')[-1]
                            sample_names.append(sample_name)
                            logger.info(f'  Found sample: {sample_name}')
                            logger.info(f'  Full path: {full_path}')
                        except Exception as e:
                            logger.warning(f'  Error extracting Path value: {e}')
                            import traceback
                            traceback.print_exc()
                            path_elem = None  # Reset so we can try RelativePath
                    
                    if path_elem is None and rel_path_elem is not None:
                        try:
                            rel_path_value = rel_path_elem.attrib['Value']
                            filepaths.append(rel_path_value)
                            sample_name = rel_path_value.split('/')[-1]
                            sample_names.append(sample_name)
                            logger.info(f'  Found sample (relative): {sample_name}')
                            logger.info(f'  Relative path: {rel_path_value}')
                        except Exception as e:
                            logger.warning(f'  Error extracting RelativePath value: {e}')
                    
                    if path_elem is None and rel_path_elem is None:
                        logger.warning(f'  Could not find Path or RelativePath in FileRef')
                        continue
                    
                    if len(filepaths) == 0:
                        continue
                else:
                    logger.warning(f'  No FileRef found in SampleRef')
                    continue
                
                # Get root key for Live 12.2+
                root_key = safe_navigate(part, "RootKey", 8)
                if root_key and 'Value' in root_key.attrib:
                    rootkeys.append(root_key.attrib['Value'])
                    logger.info(f'  Root key: {root_key.attrib["Value"]}')
                else:
                    rootkeys.append('60')  # Default middle C
                
                # Get key range for Live 12.2+
                key_range = safe_navigate(part, "KeyRange", 5)
                if key_range:
                    key_min = safe_navigate(key_range, "KeyRangeMin", 0)
                    key_max = safe_navigate(key_range, "KeyRangeMax", 1)
                    
                    if key_min and 'Value' in key_min.attrib:
                        keyrangemins.append(key_min.attrib['Value'])
                    else:
                        keyrangemins.append('0')
                    
                    if key_max and 'Value' in key_max.attrib:
                        keyrangemaxs.append(key_max.attrib['Value'])
                    else:
                        keyrangemaxs.append('127')
                    
                    logger.info(f'  Key range: {keyrangemins[-1]} - {keyrangemaxs[-1]}')
                else:
                    keyrangemins.append('0')
                    keyrangemaxs.append('127')
        else:
            # Live 10/11 structure (old path)
            for i in range(len(sample_map)):
                part = sample_map[i]
                
                # Try to find sample reference
                sample_ref = safe_navigate(part, "SampleRef", 18, 0)
                if sample_ref is None:
                    continue
                
                # Get file name
                file_ref = safe_navigate(sample_ref, "FileName", 3)
                if file_ref and 'Value' in file_ref.attrib:
                    sample_name = file_ref.attrib['Value']
                    sample_names.append(sample_name)
                else:
                    continue
                
                # Get file path
                path_hint = safe_navigate(sample_ref, "PathHint", 7, 0)
                if path_hint:
                    filepath = ''
                    for k in range(len(path_hint)):
                        if 'Dir' in path_hint[k].attrib:
                            filepath = filepath + '/' + path_hint[k].attrib['Dir']
                    filepaths.append(filepath + '/' + sample_name)
                else:
                    filepaths.append(sample_name)
            
            # Get root key
            root_key = safe_navigate(part, "RootKey", 8)
            if root_key and 'Value' in root_key.attrib:
                rootkeys.append(root_key.attrib['Value'])
                logger.info(f'  Root key: {root_key.attrib["Value"]}')
            else:
                rootkeys.append('60')  # Default middle C
            
            # Get key range
            key_range = safe_navigate(part, "KeyRange", 5)
            if key_range:
                key_min = safe_navigate(key_range, "KeyRangeMin", 0)
                key_max = safe_navigate(key_range, "KeyRangeMax", 1)
                
                if key_min and 'Value' in key_min.attrib:
                    keyrangemins.append(key_min.attrib['Value'])
                else:
                    keyrangemins.append('0')
                
                if key_max and 'Value' in key_max.attrib:
                    keyrangemaxs.append(key_max.attrib['Value'])
                else:
                    keyrangemaxs.append('127')
                
                logger.info(f'  Key range: {keyrangemins[-1]} - {keyrangemaxs[-1]}')
            else:
                keyrangemins.append('0')
                keyrangemaxs.append('127')
        
        if not filepaths:
            logger.warning("No samples found in device")
            return None
        
        params['filepath'] = filepaths
        params['rootkey'] = rootkeys
        params['keyrangemin'] = keyrangemins
        params['keyrangemax'] = keyrangemaxs
        
        if not filepaths:
            logger.warning("No samples found in device")
            return None
        
        params['filepath'] = filepaths
        params['rootkey'] = rootkeys
        params['keyrangemin'] = keyrangemins
        params['keyrangemax'] = keyrangemaxs
        
        logger.info(f'  Sample names: {sample_names}')
        logger.info(f'  Sample filepaths: {filepaths}')
        
        # Store with both key names for compatibility
        params['filepaths'] = filepaths
        params['rootkeys'] = rootkeys
        params['keyrangemins'] = keyrangemins
        params['keyrangemaxs'] = keyrangemaxs
        
        # Find sample start and end points
        if sample_map.tag == 'SampleParts' and len(sample_map) > 0:
            # Live 12.2+ structure
            first_part = sample_map[0]
        else:
            first_part = sample_map[0]
        
        sample_start = None
        sample_end = None
        for child in first_part:
            if child.tag == 'SampleStart' and 'Value' in child.attrib:
                sample_start = child
            if child.tag == 'SampleEnd' and 'Value' in child.attrib:
                sample_end = child
        
        if sample_start:
            params['sample_start'] = sample_start.attrib['Value']
        else:
            params['sample_start'] = '0'
        
        if sample_end:
            params['sample_end'] = sample_end.attrib['Value']
        else:
            params['sample_end'] = '44100'  # Default 1 second at 44.1kHz
        
        logger.info(f'  Play start: {params["sample_start"]}')
        logger.info(f'  Play end: {params["sample_end"]}')
        
        # Find loop settings
        loop_on = None
        loop_start = None
        loop_end = None
        
        for child in first_part:
            if child.tag == 'LoopOn' and 'Value' in child.attrib:
                loop_on = child
            if child.tag == 'LoopStart' and 'Value' in child.attrib:
                loop_start = child
            if child.tag == 'LoopEnd' and 'Value' in child.attrib:
                loop_end = child
        
        if loop_on:
            params['loop_on'] = loop_on.attrib['Value']
        else:
            params['loop_on'] = '0'  # Default off
        
        if loop_start:
            params['loop_start'] = loop_start.attrib['Value']
        else:
            params['loop_start'] = '0'
        
        if loop_end:
            params['loop_end'] = loop_end.attrib['Value']
        else:
            params['loop_end'] = params.get('sample_end', '44100')
        
        logger.info(f'  Loop On: {params["loop_on"]}')
        logger.info(f'  Loop Start: {params["loop_start"]}')
        logger.info(f'  Loop End: {params["loop_end"]}')
        
        # Find envelope settings
        # Try to locate the amplitude envelope
        envelope = safe_navigate(device, "VolumeEnvelope", 19, 8)
        
        if envelope:
            attack = safe_navigate(envelope, "Attack", 0, 1)
            decay = safe_navigate(envelope, "Decay", 3, 1)
            sustain = safe_navigate(envelope, "Sustain", 6, 1)
            release = safe_navigate(envelope, "Release", 7, 1)
            
            params['attack'] = attack.attrib.get('Value', '1') if attack else '1'
            params['decay'] = decay.attrib.get('Value', '300') if decay else '300'
            params['sustain'] = sustain.attrib.get('Value', '1') if sustain else '1'
            params['release'] = release.attrib.get('Value', '200') if release else '200'
        else:
            # Default envelope values
            params['attack'] = '1'
            params['decay'] = '300'
            params['sustain'] = '1'
            params['release'] = '200'
        
        logger.info(f'  Vol Env Attack: {round(float(params["attack"]))} ms')
        logger.info(f'  Vol Env Decay: {round(float(params["decay"]))} ms')
        logger.info(f'  Vol Env Sustain: {round(8.6859*math.log(max(float(params["sustain"]), 0.001)))} dB')
        logger.info(f'  Vol Env Release: {round(float(params["release"]))} ms')
        
        return params
        
    except Exception as e:
        logger.error(f"Error extracting sampler parameters: {e}")
        import traceback
        traceback.print_exc()
        return None


def track_iterator(tracks):
    """
    Extract drum rack and MIDI tracks from Ableton project.
    Returns: (pad_list, midi_tracks)
    
    Expected structure:
    - Track 1: Drum Rack with 16 pads
    - Tracks 2-17: MIDI tracks for sequences
    """
    if len(tracks) == 0:
        logger.error('No tracks found in project')
        return [], []
    
    # First track should contain DrumGroupDevice
    first_track = tracks[0]
    devices, track_type = device_extract(first_track, 1)
    
    if 'DrumGroupDevice' not in devices:
        logger.error('ERROR: No DrumGroupDevice found in first track!')
        logger.error('This script requires a Drum Rack in the first track.')
        logger.error('Please set up your project with:')
        logger.error('  - Track 1: Drum Rack with up to 16 Simplers')
        logger.error('  - Tracks 2-17: MIDI tracks for sequences')
        return [], []
    
    logger.info('='*60)
    logger.info('DRUM RACK DETECTED')
    logger.info('='*60)
    logger.warning('NOTE: Pad mapping uses CHAIN ORDER, not MIDI notes!')
    logger.warning('Ensure chains are ordered correctly in Ableton before converting.')
    logger.warning('Chain 0 → Pad 0, Chain 1 → Pad 1, etc.')
    logger.info('='*60)
    
    # Extract drum rack pads
    drum_rack = devices['DrumGroupDevice']
    pad_list = drum_rack_extract(drum_rack)
    
    # Collect MIDI tracks (tracks 2-17 should be the 16 MIDI tracks)
    midi_tracks = []
    for i in range(1, min(17, len(tracks))):
        track = tracks[i]
        devices_check, track_type_check = device_extract(track, i+1)
        if track_type_check == 'MidiTrack':
            midi_tracks.append(track)
            logger.info(f'  Found MIDI track {i} for sequence')
    
    logger.info(f'Extracted {len(pad_list)} drum pads and {len(midi_tracks)} MIDI tracks')
    return pad_list, midi_tracks


# Helper functions for generating Blackbox XML

def row_column(pad):
    rc_dict = {0:[0,0], 1:[0,1], 2:[0,2], 3:[0,3],
               4:[1,0], 5:[1,1], 6:[1,2], 7:[1,3],
               8:[2,0], 9:[2,1], 10:[2,2], 11:[2,3],
               12:[3,0], 13:[3,1], 14:[3,2], 15:[3,3],
               16:[0,4], 17:[1,4], 18:[2,4], 19:[3,4]}
    rc = rc_dict[int(pad)]
    row = rc[0]
    column = rc[1]
    return(row, column)

def pad_dicter(row, column, filename, type):
    cell_dict = {'row':str(row), 'column':str(column), 'layer':"0", 'filename':filename, 'type':type}
    return(cell_dict)

def pad_params_dicter(envattack, envdecay, envsus, envrel, samstart, samlen, multisammode, loopmode, loopstart, loopend, beatcount, samtrigtype, cellmode, polymode):
    params_dict = {'gaindb': '0', 'pitch': '0', 'panpos': '0', 'samtrigtype': str(samtrigtype), 'loopmode': str(loopmode), 
                    'loopmodes': '0', 'midimode': '0', 'midioutchan': '0', 'reverse': '0', 'cellmode': str(cellmode), 
                    'envattack': str(envattack), 'envdecay': str(envdecay), 'envsus': str(envsus), 
                    'envrel': str(envrel), 'samstart': str(samstart), 'samlen': str(samlen), 'loopstart': str(loopstart), 
                    'loopend': str(loopend), 'quantsize': '3', 'synctype': '5', 'actslice': '1', 'outputbus': '0', 
                    'polymode': str(polymode), 'polymodeslice': '0', 'slicestepmode': '0', 'chokegrp': '0', 'dualfilcutoff': '0', 
                    'res': '500', 'rootnote': '0', 'beatcount': str(beatcount), 'fx1send': '0', 'fx2send': '0', 'multisammode': multisammode, 
                    'interpqual': '0', 'playthru': '0', 'slicerquantsize': '13', 'slicersync': '0', 'padnote': '0', 
                    'loopfadeamt': '0', 'lfowave': '0', 'lforate': '100', 'lfoamount': '1000', 'lfokeytrig': '0', 'lfobeatsync': '0', 
                    'lforatebeatsync': '0', 'grainsizeperc': '300', 'grainscat': '0', 'grainpanrnd': '0', 'graindensity': '600', 
                    'slicemode': '0', 'legatomode': '0', 'gainssrcwin': '0', 'grainreadspeed': '1000', 'recpresetlen': '0', 
                    'recquant': '3', 'recinput': '0', 'recinputmulti': '0', 'recusethres': '0', 'recthresh': '-20000', 'recmonoutbus': '0'}
    return(params_dict)

def make_drum_rack_pads(session, pad_list, tempo):
    """
    Create Blackbox pads from Drum Rack pad list.
    Each pad in pad_list contains: {'blackbox_pad': 0-15, 'simpler': device, 'choke_group': 0-16, ...}
    """
    # Convert tempo to float (it comes as a string from track_tempo_extractor)
    try:
        tempo = float(tempo)
    except (ValueError, TypeError):
        logger.warning(f'Invalid tempo value: {tempo}, using 120 BPM')
        tempo = 120.0
    
    assets = []
    
    for pad_info in pad_list:
        pad_num = pad_info['blackbox_pad']
        row, column = row_column(pad_num)
        
        if not pad_info['is_empty'] and pad_info['simpler']:
            # Extract sample parameters from Simpler
            params = sampler_extract(pad_info['simpler'])
            
            if params is None:
                # Sample extraction failed, treat as empty pad
                logger.warning(f'  Pad {pad_num}: Sample extraction failed, creating empty pad')
                cell = ET.SubElement(session, 'cell')
                cell.attrib = pad_dicter(row, column, '', 'samtempl')
                param_elem = ET.SubElement(cell, 'params')
                param_elem.attrib = pad_params_dicter('0', '0', '1000', '4', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0')
                param_elem.attrib['chokegrp'] = '0'
            else:
                # Get sample filename and create proper cell
                sample_filename = params.get('filepaths', [''])[0].split('/')[-1] if params.get('filepaths') else ''
                logger.info(f'  Pad {pad_num}: {sample_filename}')
                
                # Create cell with filename
                filename_path = '.\\' + sample_filename if sample_filename else ''
                cell = ET.SubElement(session, 'cell')
                cell.attrib = pad_dicter(row, column, filename_path, 'sample')
                
                # Get WAV file info for sample length
                filepath = params.get('filepaths', [''])[0] if params.get('filepaths') else ''
                wav_info = get_wav_info(filepath) if filepath else None
                
                # Set sample length from WAV file
                samlen = '0'
                if wav_info:
                    samlen = str(wav_info['sample_length_samples'])
                    logger.debug(f'    WAV info: {wav_info["sample_length_samples"]} samples, {wav_info["duration_seconds"]:.2f}s @ {wav_info["sample_rate"]}Hz')
                
                # Check if this is a warped stem
                warp_info = detect_warped_stem(pad_info['simpler'])
                
                # Determine loop mode and trigger mode
                loopmode = '0'  # off by default
                loopstart = params.get('loop_start', '0')
                loopend = params.get('loop_end', samlen)
                beatcount = '0'
                samtrigtype = '0'  # Default: gate
                cellmode = '0'  # Default: sampler mode
                
                # Extract trigger mode (1-shot vs classic/gate)
                trigger_mode = warp_info.get('trigger_mode', 'gate')
                if trigger_mode == 'trigger':
                    samtrigtype = '1'  # 1-shot/trigger
                elif trigger_mode == 'toggle':
                    samtrigtype = '2'  # Toggle
                else:
                    samtrigtype = '0'  # Gate (classic mode)
                
                # Check if warp info contains beat count OR calculate from sample duration
                beat_count = warp_info.get('beat_count', 0)
                sample_duration = warp_info.get('sample_duration_seconds', 0)
                
                # If no beat_count but we have duration, calculate it from tempo
                if beat_count == 0 and sample_duration > 0:
                    # Calculate beats from duration and tempo
                    # beats = (duration_seconds * tempo) / 60
                    beats_calculated = (sample_duration * tempo) / 60
                    # Round to nearest beat (not to nearest 4 beats) for accuracy
                    # This matches Ableton's calculation more closely
                    beat_count = int(round(beats_calculated))
                    if beat_count < 1:
                        beat_count = 0
                    logger.debug(f'    Calculated {beat_count} beats from {sample_duration:.2f}s @ {tempo} BPM')
                
                if beat_count > 0:
                    # Sample has beat count (either from warp or calculated)
                    beatcount = str(beat_count)
                    
                    # If it's a long sample (> 8 beats / 2 bars), use clip mode
                    if beat_count >= 8:
                        cellmode = '1'  # Clip mode for longer samples
                        loopmode = '1'  # Loop enabled
                        logger.info(f'    → Sample with warp info: {beat_count} beats ({beat_count/4} bars), clip mode enabled')
                    else:
                        # Short sample - sampler mode with loop
                        loopmode = '1'  # Loop enabled
                        logger.info(f'    → Sample with warp info: {beat_count} beats ({beat_count/4} bars), sampler mode with loop')
                else:
                    # No warp beat info - check if loop is manually enabled
                    loop_on = params.get('loop_on', '0') == '1' or params.get('loop_on', '0') == 'true'
                    
                    if loop_on and wav_info:
                        # Calculate beat count from loop length
                        try:
                            loop_length_samples = float(loopend) - float(loopstart)
                            loop_length_seconds = loop_length_samples / wav_info['sample_rate']
                            
                            # Calculate beats from duration and tempo
                            beats_calculated = (loop_length_seconds * tempo) / 60
                            beats = int(round(beats_calculated))  # Round to nearest beat
                            if beats < 1:
                                beats = 0
                            
                            if beats >= 8:
                                cellmode = '1'  # Clip mode
                                loopmode = '1'  # Loop enabled
                                beatcount = str(beats)
                                logger.info(f'    → Looped sample: {loop_length_seconds:.1f}s = {beats} beats, clip mode enabled')
                            else:
                                # Short loop - use sampler mode with loop
                                loopmode = '1'  # Loop enabled
                                beatcount = str(beats)
                                logger.info(f'    → Short loop: {loop_length_seconds:.1f}s = {beats} beats, sampler mode with loop')
                        except (ValueError, TypeError, ZeroDivisionError) as e:
                            logger.debug(f'    Could not calculate loop length: {e}')
                            pass
                
                # Add choke group
                choke_group = str(pad_info.get('choke_group', 0))
                
                # Create params element
                param_elem = ET.SubElement(cell, 'params')
                
                # For clip mode samples, use default envelope settings
                # 0% attack, 100% decay, 100% sustain, 20% release
                if cellmode == '1':  # Clip mode
                    env_attack = '0'
                    env_decay = '1000'  # 100% = 1000
                    env_sustain = '1000'  # 100% = 1000
                    env_release = '200'  # 20% = 200
                else:
                    # Use extracted envelope settings for sampler mode
                    env_attack = params.get('attack', '0')
                    env_decay = params.get('decay', '0')
                    env_sustain = params.get('sustain', '1000')
                    env_release = params.get('release', '4')
                
                param_attrib = pad_params_dicter(
                    env_attack,
                    env_decay,
                    env_sustain,
                    env_release,
                    params.get('sample_start', '0'),
                    samlen,  # Use actual sample length from WAV file
                    params.get('multisammode', '0'),
                    loopmode,
                    loopstart,  # From Ableton loop settings
                    loopend,    # From Ableton loop settings
                    beatcount,
                    samtrigtype,  # Use extracted trigger mode
                    cellmode,  # Use clip mode for warped samples
                    '0'   # polymode
                )
                param_attrib['chokegrp'] = choke_group
                param_elem.attrib = param_attrib
                
                # Handle multisample mode
                if params.get('multisammode') == '1':
                    logger.info(f'    → Multisample mode enabled')
                    for i, filepath in enumerate(params.get('filepaths', [])):
                        # Add modsource for multisamples
                        modsource = ET.SubElement(cell, 'modsource')
                        modsource.attrib = {
                            'dest': "samsel",
                            'src': "midipitch",
                            'slot': "0",
                            'amount': "100",
                            'keylo': params.get('keyrangemins', ['0'])[i],
                            'keyhi': params.get('keyrangemaxs', ['127'])[i],
                            'rootkey': params.get('rootkeys', ['60'])[i]
                        }
                        
                        if filepath and filepath not in assets:
                            assets.append(filepath)
                else:
                    # Single sample
                    if params.get('filepaths') and params.get('filepaths')[0]:
                        filepath = params['filepaths'][0]
                        if filepath not in assets:
                            assets.append(filepath)
                        
                        # Add velocity and pan modsources
                        modsource = ET.SubElement(cell, 'modsource')
                        modsource.attrib = {'dest': "gaindb", 'src': "midivol", 'slot': "2", 'amount': "1000"}
                        modsource = ET.SubElement(cell, 'modsource')
                        modsource.attrib = {'dest': "panpos", 'src': "midipan", 'slot': "2", 'amount': "1000"}
        else:
            # Empty pad
            logger.info(f'  Pad {pad_num}: Empty pad')
            cell = ET.SubElement(session, 'cell')
            cell.attrib = pad_dicter(row, column, '', 'samtempl')
            param_elem = ET.SubElement(cell, 'params')
            param_elem.attrib = pad_params_dicter('0', '0', '1000', '4', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0')
            param_elem.attrib['chokegrp'] = '0'
        
        slices = ET.SubElement(cell, 'slices')
    
    logger.info(f'Created {len(pad_list)} drum rack pads')
    return session, assets


def make_drum_rack_sequences(session, midi_tracks, pad_list, unquantised=False):
    """
    Create Blackbox sequences from MIDI tracks using firmware 2.3+ format.
    Each MIDI track can have up to 4 clips mapped to sub-layers A/B/C/D.
    Each sublayer is created as a separate cell element with type="noteseq".
    
    Args:
        session: The Blackbox session element
        midi_tracks: List of MIDI track elements
        pad_list: List of pad info dictionaries
        unquantised: If True, use precise timing (960 ticks per 16th note) instead of quantizing to steps
    """
    if unquantised:
        logger.info(f'Processing {len(midi_tracks)} MIDI tracks for sequences (UNQUANTISED mode, firmware 2.3+ format)...')
    else:
        logger.info(f'Processing {len(midi_tracks)} MIDI tracks for sequences (quantised to 16th notes, firmware 2.3+ format)...')
    
    # Create MIDI note to pad number mapping for pads mode
    # In pads mode, each seqevent's pitch value (0-15) determines which pad gets triggered
    midi_to_pad = {}
    for pad in pad_list:
        if pad.get('midi_note') is not None:
            midi_to_pad[pad['midi_note']] = pad['blackbox_pad']
    
    # Fallback: If no MIDI notes found in pad_list, use standard mapping
    # Standard drum rack convention: MIDI note 36 (C1) = pad 0, 37 (C#1) = pad 1, etc.
    if not midi_to_pad:
        logger.warning('No MIDI notes found in pad_list, using standard mapping (36-51 → 0-15)')
        for pad in pad_list:
            pad_num = pad.get('blackbox_pad')
            if pad_num is not None:
                # Map pad number to MIDI note (36 + pad_num)
                midi_to_pad[36 + pad_num] = pad_num
    
    logger.debug(f'Created MIDI note to pad mapping: {midi_to_pad}')
    
    for track_idx, track in enumerate(midi_tracks[:16]):
        if track_idx >= len(pad_list):
            break
        
        # Detect sequence mode for this track
        seq_mode, mode_target = detect_sequence_mode(track)
        
        pad_num = track_idx  # Direct mapping: MIDI track 1 -> Pad 0, etc.
        row, column = row_column(pad_num)
        
        # For Keys mode, override pad_num with the target pad
        target_pad = mode_target if seq_mode == 'Keys' else pad_num
        
        logger.info(f'Track {track_idx}: Mode={seq_mode}, Target={mode_target}, Sequence Pad={pad_num}, Target Pad={target_pad}')
        
        # Extract up to 4 MIDI clips as sub-layers
        sub_layers = []
        
        try:
            device_chain = find_element_by_tag(track, 'DeviceChain')
            if not device_chain:
                logger.debug(f'  Track {track_idx}: No DeviceChain found')
                continue
            
            # In Ableton 12+, MIDI clips are in MainSequencer, not ClipTimeable
            main_sequencer = find_element_by_tag(device_chain, 'MainSequencer')
            if not main_sequencer:
                logger.debug(f'  Track {track_idx}: No MainSequencer found')
                continue
            
            clip_slot_list = find_element_by_tag(main_sequencer, 'ClipSlotList')
            if not clip_slot_list:
                logger.debug(f'  Track {track_idx}: No ClipSlotList found')
                continue
            
            # Extract up to 4 clips
            for clip_idx, clip_slot_container in enumerate(clip_slot_list[:4]):
                # Structure: clip_slot_container[1] = ClipSlot element
                if len(clip_slot_container) > 1:
                    clip_slot = clip_slot_container[1]  # The ClipSlot element
                    if clip_slot.tag == 'ClipSlot' and len(clip_slot) > 0:
                        value_elem = clip_slot[0]  # The Value element
                        if value_elem.tag == 'Value' and len(value_elem) > 0:
                            if value_elem[0].tag == 'MidiClip':
                                midi_clip = value_elem[0]
                                sub_layers.append(midi_clip)
                                logger.info(f'  Track {track_idx}, Clip {clip_idx}: Found MIDI clip for sub-layer {chr(65+clip_idx)}')
        
        except Exception as e:
            logger.warning(f"Error extracting MIDI clips from track {track_idx}: {e}")
            continue
        
        # Create sequence cells for each sublayer (firmware 2.3+ format)
        # Create all 4 sublayers (A/B/C/D) as separate cell elements
        total_notes_all_layers = 0
        first_layer_with_notes = -1
        
        for sublayer_idx in range(4):
            # Get the MIDI clip for this sublayer if it exists
            midi_clip = sub_layers[sublayer_idx] if sublayer_idx < len(sub_layers) else None
            
            # Extract all notes for this sublayer first (to check if we have events)
            sublayer_events = []
            
            if midi_clip:
                notes = find_element_by_tag(midi_clip, 'Notes')
                if notes:
                    key_tracks = find_element_by_tag(notes, 'KeyTracks')
                    if key_tracks:
                        # Extract ALL KeyTracks and ALL notes
                        for key_track in key_tracks:
                            midi_key = find_element_by_tag(key_track, 'MidiKey')
                            notes_elem = find_element_by_tag(key_track, 'Notes')
                            
                            if midi_key is not None and 'Value' in midi_key.attrib and notes_elem is not None and len(notes_elem) > 0:
                                midi_note = int(midi_key.attrib['Value'])
                                
                                # Determine chan and pitch based on sequence mode
                                if seq_mode == 'Pads':
                                    # Pads mode: chan determines pad, pitch is always 0
                                    pad_number = midi_to_pad.get(midi_note, 0)
                                    event_chan = 256 + pad_number
                                    event_pitch = 0
                                elif seq_mode == 'Keys':
                                    # Keys mode: pitch is the MIDI note, chan is standard
                                    event_chan = 256
                                    event_pitch = midi_note
                                elif seq_mode == 'MIDI':
                                    # MIDI mode: pitch is MIDI note, chan is MIDI channel
                                    event_chan = mode_target  # MIDI channel (0-15)
                                    event_pitch = midi_note
                                
                                # Extract note events
                                for note_event in notes_elem:
                                    # Handle both Ableton 12.3+ (attributes) and older (elements) formats
                                    if 'Time' in note_event.attrib:
                                        time_val = float(note_event.attrib.get('Time', 0))
                                        dur_val = float(note_event.attrib.get('Duration', 0))
                                        vel_val = int(float(note_event.attrib.get('Velocity', 100)))
                                    else:
                                        time = find_element_by_tag(note_event, 'Time')
                                        duration = find_element_by_tag(note_event, 'Duration')
                                        velocity = find_element_by_tag(note_event, 'Velocity')
                                        
                                        if not (time and duration and velocity):
                                            continue
                                            
                                        time_val = float(time.attrib.get('Value', 0))
                                        dur_val = float(duration.attrib.get('Value', 0))
                                        vel_val = int(float(velocity.attrib.get('Value', 100)))
                                    
                                    # Calculate timing (always use tick-based format for firmware 2.3+)
                                    step = int(time_val * 4)  # 4 steps per beat
                                    strtks = int(time_val * 3840)  # 1 beat = 3840 ticks
                                    lencount = max(1, int(dur_val * 4))
                                    lentks = int(dur_val * 3840)
                                    
                                    # Store event data
                                    sublayer_events.append({
                                        'step': step,
                                        'chan': str(event_chan),
                                        'type': 'note',
                                        'strtks': strtks,
                                        'pitch': event_pitch,
                                        'lencount': lencount,
                                        'lentks': lentks,
                                        'velocity': vel_val
                                    })
            
            # Extract clip length from MIDI clip to calculate step_count
            # Try multiple methods: LoopEnd, CurrentEnd, or calculate from note positions
            clip_length_beats = 1.0  # Default to 1 beat
            if midi_clip:
                # Method 1: Try LoopStart/LoopEnd
                loop_start_elem = find_element_by_tag(midi_clip, 'LoopStart')
                loop_end_elem = find_element_by_tag(midi_clip, 'LoopEnd')
                
                if loop_start_elem is not None and 'Value' in loop_start_elem.attrib and \
                   loop_end_elem is not None and 'Value' in loop_end_elem.attrib:
                    try:
                        loop_start = float(loop_start_elem.attrib['Value'])
                        loop_end = float(loop_end_elem.attrib['Value'])
                        clip_length_beats = loop_end - loop_start
                        if clip_length_beats <= 0:
                            clip_length_beats = loop_end  # Use LoopEnd directly if difference is 0
                        logger.debug(f'    Sub-layer {chr(65+sublayer_idx)}: Clip length from LoopStart/LoopEnd = {clip_length_beats} beats')
                    except (ValueError, TypeError) as e:
                        logger.debug(f'    Sub-layer {chr(65+sublayer_idx)}: Error extracting LoopStart/LoopEnd: {e}')
                
                # Method 2: If LoopEnd not found, try CurrentEnd
                if clip_length_beats <= 1.0:
                    current_end_elem = find_element_by_tag(midi_clip, 'CurrentEnd')
                    if current_end_elem is not None and 'Value' in current_end_elem.attrib:
                        try:
                            clip_length_beats = float(current_end_elem.attrib['Value'])
                            logger.debug(f'    Sub-layer {chr(65+sublayer_idx)}: Clip length from CurrentEnd = {clip_length_beats} beats')
                        except (ValueError, TypeError):
                            pass
                
                # Method 3: Calculate from note positions (use latest note end time)
                if clip_length_beats <= 1.0 and len(sublayer_events) > 0:
                    max_time = 0.0
                    for event in sublayer_events:
                        # Calculate note end time from step and duration
                        # step is in 16th notes, so divide by 4 to get beats
                        note_start_beats = event['step'] / 4.0
                        note_duration_beats = event['lencount'] / 4.0
                        note_end_beats = note_start_beats + note_duration_beats
                        max_time = max(max_time, note_end_beats)
                    
                    if max_time > 0:
                        # Round up to nearest bar (4 beats) for sequence length
                        clip_length_beats = int((max_time + 3) // 4) * 4
                        if clip_length_beats < 4:
                            clip_length_beats = max(4.0, max_time)  # At least 1 bar
                        logger.debug(f'    Sub-layer {chr(65+sublayer_idx)}: Clip length calculated from notes = {clip_length_beats} beats (max note end: {max_time})')
                
                # If still no length found, use default
                if clip_length_beats <= 1.0:
                    logger.debug(f'    Sub-layer {chr(65+sublayer_idx)}: Using default clip length = 1.0 beat')
                    clip_length_beats = 1.0
            
            # Calculate step_len and step_count from clip length
            # Step length values (non-triplet only):
            # 14 = 1/64, 12 = 1/32, 10 = 1/16, 8 = 1/8, 6 = 1/4, 4 = 1/2, 3 = 1 Bar, 2 = 2 Bars, 1 = 4 Bars, 0 = 8 Bars
            # Triplet values (odd numbers, not used): 13 = 1/32T, 11 = 1/16T, 9 = 1/8T, 7 = 1/4T, 5 = 1/2T
            # 1 bar = 4 beats
            # If no clip and no notes, use minimum length
            if not midi_clip and len(sublayer_events) == 0:
                step_len = 10  # 1/16 notes
                step_count = 1  # Minimum length for empty sublayer
            else:
                # Start with 1/16 notes (most common resolution) and go coarser only if needed
                # At 1/16: 1 beat = 4 steps, 1 bar (4 beats) = 16 steps
                step_count = int(clip_length_beats * 4)
                step_len = 10  # 1/16 notes (default)
                
                # If step_count exceeds 256, use coarser resolution
                if step_count > 256:
                    # Try 1/8 notes: 1 beat = 2 steps, 1 bar = 8 steps
                    step_count = int(clip_length_beats * 2)
                    step_len = 8
                    
                if step_count > 256:
                    # Try 1/4 notes: 1 beat = 1 step, 1 bar = 4 steps
                    step_count = int(clip_length_beats * 1)
                    step_len = 6
                    
                if step_count > 256:
                    # Try 1/2 notes: 2 beats = 1 step, 1 bar = 2 steps
                    step_count = int(clip_length_beats * 0.5)
                    step_len = 4
                    
                if step_count > 256:
                    # Try 1 Bar: 4 beats = 1 step
                    step_count = int(clip_length_beats * 0.25)
                    step_len = 3
                    
                if step_count > 256:
                    # Try 2 Bars: 8 beats = 1 step
                    step_count = int(clip_length_beats * 0.125)
                    step_len = 2
                    
                if step_count > 256:
                    # Try 4 Bars: 16 beats = 1 step
                    step_count = int(clip_length_beats * 0.0625)
                    step_len = 1
                    
                if step_count > 256:
                    # Max: 8 Bars: 32 beats = 1 step
                    step_count = max(1, int(clip_length_beats * 0.03125))
                    step_len = 0
                
                # Ensure step_count is at least 1
                if step_count < 1:
                    step_count = 1
                
                logger.debug(f'    Sub-layer {chr(65+sublayer_idx)}: {clip_length_beats} beats → step_count={step_count}, step_len={step_len}')
            
            # Track first layer with notes for activeseqlayer
            if sublayer_events and first_layer_with_notes == -1:
                first_layer_with_notes = sublayer_idx
            
            total_notes_all_layers += len(sublayer_events)
            
            # Create cell element for this sublayer
            cell = ET.SubElement(session, 'cell')
            cell.attrib = {
                'row': str(row),
                'column': str(column),
                'layer': '1',
                'seqsublayer': str(sublayer_idx),
                'type': 'noteseq'
            }
            
            # Add params with calculated step_len and step_count
            params = ET.SubElement(cell, 'params')
            
            # Set parameters based on sequence mode
            if seq_mode == 'Pads':
                seqstepmode_val = '1'  # Pads mode
                seqpadmapdest_val = str(pad_num)  # Sequence location
                midioutchan_val = '0'
            elif seq_mode == 'Keys':
                seqstepmode_val = '0'  # Keys mode
                seqpadmapdest_val = str(target_pad)  # Target pad to play
                midioutchan_val = '0'
            elif seq_mode == 'MIDI':
                seqstepmode_val = '0'  # MIDI mode
                seqpadmapdest_val = '0'
                midioutchan_val = str(mode_target)  # MIDI channel (0-15)
            
            params.attrib = {
                'notesteplen': str(step_len),  # Calculated based on clip length
                'notestepcount': str(step_count),  # Calculated from clip length
                'dutycyc': '1000',
                'quantsizeseq': '1',
                'dispmode': '1' if sublayer_idx == 0 else '0',  # Only first layer visible by default
                'seqpadmapdest': seqpadmapdest_val,
                'seqplayenable': '1' if sublayer_events else '0',  # Enable if has notes
                'activeseqlayer': str(first_layer_with_notes if first_layer_with_notes >= 0 else 0),
                'midioutchan': midioutchan_val,
                'seqstepmode': seqstepmode_val,
                'midiseqcellchan': '0'
            }
            
            # Add sequence element with events
            sequence = ET.SubElement(cell, 'sequence')
            for event_data in sublayer_events:
                seqevent = ET.SubElement(sequence, 'seqevent')
                seqevent.attrib = {
                    'step': str(event_data['step']),
                    'chan': str(event_data['chan']),
                    'type': event_data['type'],
                    'strtks': str(event_data['strtks']),
                    'lencount': str(event_data['lencount']),
                    'lentks': str(event_data['lentks'])
                }
                # In pads mode (seqstepmode=1), pitch should be the pad number (0-15)
                # This tells Blackbox which pad to trigger: pitch=0 → pad 0, pitch=1 → pad 1, etc.
                seqevent.attrib['pitch'] = str(event_data['pitch'])
                if event_data['velocity'] != 100:
                    seqevent.attrib['velocity'] = str(event_data['velocity'])
            
            if sublayer_events:
                logger.info(f'    Sub-layer {chr(65+sublayer_idx)}: {len(sublayer_events)} notes')
        
        if total_notes_all_layers > 0:
            logger.info(f'  Sequence {pad_num}: Created 4 sub-layers ({total_notes_all_layers} total notes)')
        else:
            logger.debug(f'  Sequence {pad_num}: No MIDI clips found')
    
    logger.info(f'Sequence extraction complete')
    return session


def sequence_dicter(row, column, type):
    cell_dict = {'row':str(row), 'column':str(column), 'layer':"1", 'type':type}
    return(cell_dict)

def find_division(steps):
    smallest_step = False
    for_divisions = []
    for step in steps:
        if float(step['Start'])*4%1:
            smallest_step = True
            for_divisions.append(float(step['Start'])*4%1)
        if float(step['Duration'])*4%1:
            smallest_step = True
            for_divisions.append(float(step['Duration'])*4%1)
    divisions = []
    if smallest_step:
        for i in for_divisions:
            if not i%0.5:
                divisions.append(12)
            elif not i%0.25:
                divisions.append(14)
    if len(divisions)>0:
        division = max(divisions)
    else:
        division = 10                
    return(division)

def sequence_params_dicter(type, notestepcount, notesteplen, enable=False):
    div_dict = {10:4, 12:8, 14:16}
    notestepcount = notestepcount*div_dict[notesteplen]
    if type == 'MIDI':
        dispmode = '2'
    else:
        dispmode = '1'
    possible_divisions = [1, 2, 4, 8, 16]
    quantsizes = {16:1, 8:2, 4:4, 2:6, 1:8}
    for i in possible_divisions:
        if not notestepcount%i:
            quantsize = quantsizes[i] 

    # Enable sequence if it has notes
    seqplayenable = '1' if enable else '0'
    params = {'notesteplen': str(notesteplen), 'notestepcount': str(notestepcount), 'dutycyc': '1000', 'midioutchan': '0', 'quantsize': str(quantsize), 'padnote': '0', 'dispmode': dispmode, 'seqplayenable': seqplayenable}
    return(params)

def sequence_step_dicter(step_info, track, type, division):
    div_dict = {10:4, 12:8, 14:16}
    division = div_dict[division]
    if type == 'MIDI':
        chan = 256
    else:
        chan = int(track) + 255
    step = round(float(step_info['Start'])*division)
    strtks = step*960
    length = round(float(step_info['Duration'])*division)
    lentks = length*960
    pitch = step_info['Note']
    seqevent = {'step': str(step), 'chan': str(chan), 'type': 'note', 'strtks': str(strtks), 'pitch': str(pitch), 'lencount': str(length), 'lentks': str(lentks)}
    if step_info['Velocity'] != '100':
        seqevent['velocity'] = step_info['Velocity']
    return(seqevent)

def empty_sequence():
    params = {'notesteplen': '10', 'notestepcount': '16', 'dutycyc': '1000', 'midioutchan': '0', 'quantsize': '1', 'padnote': '0', 'dispmode': '1', 'seqplayenable': '0', 'seqstepmode': '1'}
    return(params)

def make_song(root):
    session = root.find('session')
    for i in range(16):
        cell = ET.SubElement(session, 'cell')
        cell.attrib = {'row':str(i), 'column':'0', 'layer':'2', 'name':'', 'type':'section'}
        params = ET.SubElement(cell, 'params')
        params.attrib = {'sectionlenbars':'8'}
        sequence = ET.SubElement(cell, 'sequence')
    return(root)
   
def make_fx(root):
    session = root.find('session')

    cell = ET.SubElement(session, 'cell')
    cell.attrib = {'row':'0', 'layer':'3', 'type':'delay'}
    params = ET.SubElement(cell, 'params')
    params.attrib = {'delay': '400', 'delaymustime': '6', 'feedback': '400', 'cutoff': '120', 'filtquality': '1000', 'dealybeatsync': '1', 'filtenable': '1', 'delaypingpong': '1'}

    cell = ET.SubElement(session, 'cell')
    cell.attrib = {'row':'1', 'layer':'3', 'type':'reverb'}
    params = ET.SubElement(cell, 'params')
    params.attrib = {'decay': '600', 'predelay': '40', 'damping': '500'}

    cell = ET.SubElement(session, 'cell')
    cell.attrib = {'row':'2', 'layer':'3', 'type':'eq'}
    params = ET.SubElement(cell, 'params')
    params.attrib = {'eqactband': '0', 'eqgain': '0', 'eqcutoff': '200', 'eqres': '400', 'eqenable': '1', 'eqtype': '0', 
                     'eqgain2': '0', 'eqcutoff2': '400', 'eqres2': '400', 'eqenable2': '1', 'eqtype2': '0', 'eqgain3': '0', 
                     'eqcutoff3': '600', 'eqres3': '400', 'eqenable3': '1', 'eqtype3': '0', 'eqgain4': '0', 'eqcutoff4': '800', 
                     'eqres4': '400', 'eqenable4': '1', 'eqtype4': '0'}

    cell = ET.SubElement(session, 'cell')
    cell.attrib = {'row':'4', 'layer':'3', 'type':'null'}
    params = ET.SubElement(cell, 'params')

    return(root)

def make_master(root, tempo):
    session = root.find('session')
    
    cell = ET.SubElement(session, 'cell')
    cell.attrib = {'type':'song'}
    params = ET.SubElement(cell, 'params')
    params.attrib = {'globtempo': str(tempo), 'songmode': '0', 'sectcount': '1', 'sectloop': '1', 'swing': '50', 'keymode': '1', 'keyroot': '3'}

    return(root)

def indent_xml(elem, level=0):
    """
    Indent XML elements for pretty printing.
    Compatible with Python 3.7+
    """
    i = "\n" + level * "    "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "    "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for child in elem:
            indent_xml(child, level+1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def save_xml(root, preset_filepath):
    tree = ET.ElementTree(root)
    # Use custom indent function for Python 3.7 compatibility
    indent_xml(root)
    tree.write(preset_filepath, encoding="utf-8", xml_declaration=True)
    logger.info(f"Saved preset to: {preset_filepath}")


def main(args):
    logger.info('=== Ableton to Blackbox Converter v0.3 (Drum Rack Edition) ===')
    logger.info('Reading Ableton project...')
    
    try:
        root = read_project(args.Input)
        tracks, tempo = track_tempo_extractor(root)
        logger.info(f'The project tempo is: {tempo} bpm')
        
        logger.info('Extracting track data...')
        pad_list, midi_tracks = track_iterator(tracks)
        
        if not pad_list:
            logger.error('Failed to extract drum rack. Aborting.')
            sys.exit(1)
        
        logger.info('________________\n')
        logger.info('Building Blackbox preset...')
        
        # Create base document structure (firmware 3.1.2 format)
        bb_root = ET.Element('document')
        # No attributes on document element for firmware 3.x
        session = ET.SubElement(bb_root, 'session')
        session.attrib = {'version': '2'}
        
        # Create pads from drum rack
        session, assets = make_drum_rack_pads(session, pad_list, tempo)
        
        # Create sequences from MIDI tracks
        session = make_drum_rack_sequences(session, midi_tracks, pad_list, unquantised=args.unquantised)
        
        # Add song, FX, and master sections
        bb_root = make_song(bb_root)
        bb_root = make_fx(bb_root)
        bb_root = make_master(bb_root, tempo)
        
        # Create output directory
        try:
            os.makedirs(args.Output, exist_ok=True)
        except Exception as e:
            logger.warning(f'Could not create output directory: {e}')
        
        # Handle assets (sample files)
        if assets:
            logger.info(f'Processing {len(assets)} sample files...')
            
            # Copy samples if not using -m flag
            if not args.Manual:
                for asset_path in assets:
                    if asset_path and os.path.exists(asset_path):
                        sample_name = os.path.basename(asset_path)
                        dest_path = os.path.join(args.Output, sample_name)
                        try:
                            shutil.copy2(asset_path, dest_path)
                            logger.info(f'  Copied: {sample_name}')
                        except Exception as e:
                            logger.warning(f'  Could not copy {sample_name}: {e}')
        
        preset_filepath = os.path.join(args.Output, 'preset.xml')
        
        logger.info('Saving preset XML...')
        save_xml(bb_root, preset_filepath)
        
        logger.info('=== Conversion complete! ===')
        logger.info(f'Output saved to: {args.Output}')
        
    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    prog = "Ableton Drum Rack to Blackbox Converter"
    description = """Version 0.3 - Drum Rack Workflow
    
    Converts Ableton Live Drum Rack projects to 1010music Blackbox presets
    
    REQUIREMENTS:
    - Track 1: Drum Rack with up to 16 Simplers
    - Tracks 2-17: MIDI tracks for sequences (optional)
    
    FEATURES:
    - 16-pad drum rack mapping (1:1)
    - Choke group extraction
    - Warped stem detection and loop mode
    - Multi-layer sequences (A/B/C/D sub-layers)
    - Compatible with Ableton Live 10, 11, and 12
    """
    epilog = "For more info, see DRUM_RACK_WORKFLOW.md"
    parser = argparse.ArgumentParser(prog=prog, 
                                     description=description, 
                                     epilog=epilog,
                                     formatter_class=RawTextHelpFormatter)
    parser.add_argument("-i", "--Input", help="Ableton live project input (.als file)", type=str, required=True)
    parser.add_argument("-o", "--Output", help="BB project name and location (directory path)", type=str, required=True)
    parser.add_argument("-m", "--Manual", help="Manual sample extraction (don't copy samples)", action='store_true')
    parser.add_argument("-u", "--unquantised", help="Unquantised MIDI timing (precise timing, not grid-locked)", action='store_true')
    parser.add_argument("-v", "--verbose", help="Verbose output", action='store_true')
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    main(args)

