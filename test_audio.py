import asyncio
import os
import pyaudio
from google import genai
from google.genai import types

# Audio settings perfectly matching Gemini's strict requirements
FORMAT = pyaudio.paInt16
CHANNELS = 1
INPUT_RATE = 16000  # Gemini expects 16kHz input
OUTPUT_RATE = 24000 # Gemini outputs 24kHz
CHUNK = 512

async def main():
    # Grabs your key from the environment
    client = genai.Client(api_key=os.environ.get("AIzaSyAzejHbUNP9THHYn9d7vPjJp04nLXyet50"))
    audio = pyaudio.PyAudio()
    
    # 1. Open Microphone Stream
    mic_stream = audio.open(format=FORMAT, channels=CHANNELS, rate=INPUT_RATE, 
                            input=True, frames_per_buffer=CHUNK)
    
    # 2. Open Speaker Stream
    speaker_stream = audio.open(format=FORMAT, channels=CHANNELS, rate=OUTPUT_RATE, 
                                output=True, frames_per_buffer=CHUNK)

    # 3. Diagnostic System Instruction
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part.from_text(
            text="You are a diagnostic tool. When the user speaks, reply immediately with: 'Audio uplink confirmed. I read you loud and clear.' Keep it extremely brief."
        )])
    )

    print(">>> INITIATING AUDIO DIAGNOSTIC...")
    
    try:
        async with client.aio.live.connect(model="gemini-2.5-flash-native-audio-preview-12-2025", config=config) as session:
            print(">>> UPLINK SECURED. Say something into your mic...")

            async def send_audio():
                while True:
                    # Read mic data and fire it to Gemini
                    data = mic_stream.read(CHUNK, exception_on_overflow=False)
                    await session.send(input={"mime_type": "audio/pcm;rate=16000", "data": data}, end_of_turn=False)
                    await asyncio.sleep(0.001)

            async def receive_audio():
                # Catch Gemini's audio and push it to the speaker
                async for response in session.receive():
                    server_content = response.server_content
                    if server_content and server_content.model_turn:
                        for part in server_content.model_turn.parts:
                            if part.inline_data:
                                speaker_stream.write(part.inline_data.data)

            # Run both streams concurrently
            await asyncio.gather(send_audio(), receive_audio())

    except Exception as e:
        print(f">>> CRITICAL ERROR: {e}")
    finally:
        print(">>> CLOSING STREAMS...")
        mic_stream.stop_stream()
        mic_stream.close()
        speaker_stream.stop_stream()
        speaker_stream.close()
        audio.terminate()

if __name__ == "__main__":
    asyncio.run(main())