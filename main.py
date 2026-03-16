import asyncio
import os
import base64
import re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

app = FastAPI()

SYSTEM_INSTRUCTION = """You are Ghost Debugger, an elite real-time pair-programming AI embedded in a compact HUD overlay.

VISUAL ACCESS:
- You have live access to the user's screen via a continuous frame stream.
- CRITICAL: ALWAYS base your visual answers on the MOST RECENTLY received frame ONLY. Ignore all previous frames entirely — they are outdated.
- Every time you receive a [SCREEN UPDATED] marker, the previous screen context is stale. Only describe what is in the frame that arrived with or after that marker.
- When asked "what do you see?", "what's on screen?", or anything visual — describe ONLY the current frame, never blend with past frames.

RESPONSE STYLE — CRITICAL:
- ALWAYS respond in English only, regardless of what language the user speaks.
- Be extremely concise. One short sentence or a code block. No preamble, no explanation unless asked.
- Never narrate what you're about to do. Just do it.
- No bullet-point essays. If it fits in under 2 sentences, keep it there.
- If the user asks a yes/no question, answer yes or no first.
- Only elaborate when the user explicitly asks for an explanation.

FORMATTING:
- Always use triple-backtick markdown for code and commands so the HUD renders them correctly.
- Label terminal commands as `bash` or `cmd`.

Bad: "Sure! I can help with that. Let me take a look at your screen and analyze the error you're seeing..."
Good: "Missing closing bracket on line 12."
"""

@app.get("/")
async def get():
    with open("index.html", "r") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Model 1: gemini-2.5-flash-native-audio — voice I/O + screen vision
    live_config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        system_instruction=types.Content(parts=[types.Part.from_text(text=SYSTEM_INSTRUCTION)])
    )

    # Model 2: gemini-2.5-flash — typed text + voice transcript → HUD text
    chat_history = []
    # Latest screen frame — passed to gemini-2.5-flash so it can answer visual questions
    latest_frame_b64 = {"data": None}

    # DEFINED FIRST so receive_from_gemini can reference it
    async def handle_text_input(user_text: str):
        print(f"\n>>> [CHAT] {user_text}")
        try:
            # Build the message parts — always include the latest frame so
            # gemini-2.5-flash has real screen context instead of hallucinating
            parts = []
            if latest_frame_b64["data"]:
                parts.append(types.Part.from_bytes(
                    data=base64.b64decode(latest_frame_b64["data"]),
                    mime_type="image/jpeg"
                ))
            parts.append(types.Part.from_text(text=user_text))

            chat_history.append(types.Content(role="user", parts=parts))
            full_response = ""
            async for chunk in await client.aio.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=chat_history,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.7,
                )
            ):
                if chunk.text:
                    full_response += chunk.text
                    clean = re.sub(r'\*\*[^*]+\*\*\n?', '', chunk.text).strip()
                    if clean:
                        await websocket.send_json({"text": clean})
            if full_response:
                chat_history.append(
                    types.Content(role="model", parts=[types.Part.from_text(text=full_response)])
                )
        except Exception as e:
            print(f">>> [ERROR] Chat model: {type(e).__name__}: {e}")
            if "429" not in str(e) and "RESOURCE_EXHAUSTED" not in str(e):
                await websocket.send_json({"text": f"[Error: {type(e).__name__}]"})

    try:
        async with client.aio.live.connect(
            model="gemini-2.5-flash-native-audio-preview-12-2025",
            config=live_config
        ) as session:
            print(">>> LIVE API ONLINE:  gemini-2.5-flash-native-audio ready.")
            print(">>> CHAT API READY:   gemini-2.5-flash ready.")

            async def receive_from_browser():
                try:
                    while True:
                        data = await websocket.receive_json()

                        if "execute_command" in data:
                            cmd = data["execute_command"]
                            print(f"\n>>> [HUD TRIGGER] Executing: {cmd}")
                            process = await asyncio.create_subprocess_shell(
                                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                            )
                            stdout, stderr = await process.communicate()
                            output = stdout.decode() if stdout else ""
                            error_output = stderr.decode() if stderr else ""
                            full_result = (output + "\n" + error_output).strip() or "Success: No output."
                            await websocket.send_json({"text": f"[LOG] Command result:\n{full_result}"})
                            await session.send(
                                input=f"SYSTEM NOTIFICATION: User executed `{cmd}`. Result:\n{full_result}",
                                end_of_turn=False
                            )

                        elif "text_input" in data:
                            user_text = data["text_input"].strip()
                            if user_text:
                                asyncio.create_task(handle_text_input(user_text))

                        elif "image" in data:
                            raw_image_bytes = base64.b64decode(data["image"])
                            latest_frame_b64["data"] = data["image"]  # store for gemini-2.5-flash
                            await session.send(
                                input=types.LiveClientRealtimeInput(media_chunks=[
                                    types.Blob(mime_type="image/jpeg", data=raw_image_bytes)
                                ])
                            )
                            await session.send(input="[SCREEN UPDATED]", end_of_turn=False)

                        elif "audio" in data:
                            raw_audio_bytes = base64.b64decode(data["audio"])
                            await session.send(
                                input=types.LiveClientRealtimeInput(media_chunks=[
                                    types.Blob(mime_type="audio/pcm;rate=16000", data=raw_audio_bytes)
                                ])
                            )

                except WebSocketDisconnect:
                    print(">>> Client disconnected.")
                except Exception as e:
                    print(f">>> [ERROR] receive_from_browser: {type(e).__name__}: {e}")

            # Buffer for accumulating transcript words across chunks.
            # Only fires handle_text_input once turn_complete arrives.
            transcript_buffer = []

            async def receive_from_gemini():
                try:
                    while True:
                        async for response in session.receive():

                            # Accumulate transcript words into buffer
                            if response.server_content and response.server_content.input_transcription:
                                word = response.server_content.input_transcription.text
                                if word and word.strip():
                                    transcript_buffer.append(word.strip())

                            # turn_complete = user finished speaking, sentence is whole
                            # Fire ONE request to gemini-2.5-flash with the full sentence
                            if response.server_content and response.server_content.turn_complete:
                                if transcript_buffer:
                                    full_transcript = " ".join(transcript_buffer).strip()
                                    transcript_buffer.clear()
                                    print(f"\n>>> [TRANSCRIPT] {full_transcript}")
                                    asyncio.create_task(handle_text_input(full_transcript))

                            server_content = response.server_content
                            if server_content and server_content.model_turn:
                                for part in server_content.model_turn.parts:
                                    if part.text:
                                        if getattr(part, 'thought', False):
                                            continue
                                        text = re.sub(r'\*\*[^*]+\*\*\n?', '', part.text).strip()
                                        if text:
                                            print(f"{text}", end="", flush=True)
                                            await websocket.send_json({"text": text})
                                    if part.inline_data:
                                        audio_b64 = base64.b64encode(part.inline_data.data).decode("utf-8")
                                        await websocket.send_json({"audio": audio_b64})

                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f">>> [ERROR] receive_from_gemini: {type(e).__name__}: {e}")

            receive_task = asyncio.create_task(receive_from_browser())
            gemini_task = asyncio.create_task(receive_from_gemini())
            await asyncio.wait([receive_task, gemini_task], return_when=asyncio.FIRST_COMPLETED)
            receive_task.cancel()
            gemini_task.cancel()

    except Exception as e:
        print(f">>> [ERROR] Session crashed: {type(e).__name__}: {e}")
        await websocket.close()