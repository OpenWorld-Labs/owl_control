import asyncio
import json
import sys
import logging

from vg_control.constants import FPS, POLLS_PER_FRAME
from .recorder import SimpleRecorder, main as recorder_main
from .input_tracking.rawinputlib import HotkeyManager, InputData, KeyboardData, RawInputReader, open_raw_input_dll
from .input_tracking.keybinds import CODE_TO_KEY

logger = logging.getLogger(__name__)

class RecorderBridge:
    def __init__(self, start_key, stop_key, raw_input: RawInputReader):
        self.recorder = SimpleRecorder()
        self.hotkeys = HotkeyManager()
        self.raw_input = raw_input
        
        # Register the custom hotkeys
        self.hotkeys.add_callback(start_key, self.recorder.start_recording)
        self.hotkeys.add_callback(stop_key, self.recorder.stop_recording)
    
    async def run(self):
        try:
            # Print ready status for Node
            print(json.dumps({"status": "ready"}))
            sys.stdout.flush()
            
            await self.raw_input.run(1. / FPS / POLLS_PER_FRAME, self.recv_input)
        except Exception as e:
            logger.exception("Error in RecorderBridge run loop")
            print(json.dumps({"status": "error", "error": str(e)}))
            sys.stdout.flush()
    
    async def recv_input(self, input: InputData):
        if isinstance(input, KeyboardData):
            await self.hotkeys.on_keypress(input)
        self.recorder.saw_user_input()
        self.recorder.client.writer.tracker.recv_input(input)
        
def init_logger():
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

async def bridge_main():
    import argparse

    init_logger()
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Recording Bridge')
    parser.add_argument('--start-key', type=str, default='F4', help='Start recording hotkey')
    parser.add_argument('--stop-key', type=str, default='F5', help='Stop recording hotkey')
    
    # Parse args (skip the first arg which is the script name)
    args = parser.parse_args()
    
    start_key = args.start_key
    stop_key = args.stop_key
    
    # Print detected keys
    logger.info(f"Recording bridge using hotkeys: Start={start_key}, Stop={stop_key}")
    sys.stdout.flush()
    
    with open_raw_input_dll() as rawinput_lib:
        raw_input = RawInputReader(rawinput_lib)
        while True:
            try:
                bridge = RecorderBridge(start_key, stop_key, raw_input)
                await bridge.run()
            except Exception as e:
                print(json.dumps({"status": "error", "error": str(e)}))
                sys.stdout.flush()
                # Clean up the bridge if it exists
                if 'bridge' in locals():
                    del bridge
                await asyncio.sleep(1)  # Brief pause before restarting
                continue

if __name__ == "__main__":
    asyncio.run(bridge_main())